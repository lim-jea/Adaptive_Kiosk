"""
범용 채팅 처리 서비스.

핵심 함수:
  - process_chat_message(...): purpose 인자로 다양한 채팅 용도를 지원하는 범용 처리기
  - process_voice_message(...): 음성 주문 전용 얇은 래퍼

처리 흐름:
  1. 입력 정제 + jailbreak 차단
  2. attempt 컨텍스트 이력 로드 (글자 수 기반 5000자 제한)
  3. fast path: 패턴 매칭 → 매칭 시 즉시 반환
  4. fast path: 메뉴 이름 매칭 → 매칭 시 즉시 반환
  5. slow path: Gemini structured output 호출 (response_schema=AIChatResponse)
  6. 사용자/어시스턴트 메시지 저장 + 세션 stage 갱신
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from crud import chat as chat_crud
from crud.menu import get_menus
from models.session import KioskSession
from schemas.chat import AIChatResponse, CartItemSnapshot, SpeakAction
from services.chat_prompts import (
    build_system_prompt,
    check_jailbreak,
    get_cached_menu_catalog_text,
    match_menu_name,
    match_pattern,
    sanitize_input,
    JailbreakDetectedError,
)

logger = logging.getLogger(__name__)


# ─── Gemini 클라이언트 (지연 초기화) ─────────────────────────────────────────

_GEMINI_MODEL = "gemini-2.0-flash-lite"
_client = None


_JSON_FORMAT_INSTRUCTION = """[응답 JSON 스키마 — 이 형식만 사용]
{
  "intent": "string",
  "response_text": "string (사용자에게 들려줄 한국어 문장)",
  "next_stage": "greeting|category_browse|menu_browse|menu_select|option_select|cart_review|payment_confirm|farewell" (생략 가능),
  "actions": [
    {"type": "speak", "text": "..."},
    {"type": "navigate", "target": "menu_list|menu_detail|category|cart|payment|complete", "category_name": "...", "menu_name": "..."},
    {"type": "scroll", "direction": "up|down"},
    {"type": "cart_add", "menu_name": "...", "quantity": 1, "option_item_ids": []},
    {"type": "cart_remove", "menu_name": "..."},
    {"type": "cart_update", "menu_name": "...", "quantity": 2},
    {"type": "place_order"},
    {"type": "end_conversation"}
  ],
  "requires_user_input": true,
  "end_conversation": false
}
- actions는 빈 배열도 허용. 한 액션에 type 필드는 필수.
- 응답은 JSON 객체 하나만 출력하세요. 다른 텍스트 금지."""


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not settings.GENAI_API_KEY:
        return None
    try:
        from google import genai  # type: ignore
        _client = genai.Client(api_key=settings.GENAI_API_KEY)
        return _client
    except Exception as e:
        logger.warning("[chat_service] Gemini 클라이언트 초기화 실패: %s", e)
        return None


# ─── 메뉴 이름 캐시 (matcher용) ─────────────────────────────────────────────

async def _list_menu_names(db: AsyncSession) -> List[str]:
    rows, _ = await get_menus(db, limit=1000)
    return [r["name"] for r in rows]


# ─── Gemini 호출 ─────────────────────────────────────────────────────────────

async def _call_gemini_structured(
    *,
    system_prompt: str,
    history: list[dict],
    user_message: str,
) -> AIChatResponse:
    client = _get_client()
    if client is None:
        # 폴백: Gemini 사용 불가 시 안전한 기본 응답
        text = "죄송해요, 잠시 후 다시 말씀해 주세요."
        return AIChatResponse(
            intent="fallback",
            response_text=text,
            actions=[SpeakAction(text=text)],
            requires_user_input=True,
        )

    try:
        from google.genai import types  # type: ignore

        contents = []
        for row in history:
            role = "model" if row["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": row["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        # 주의: AIChatResponse는 Annotated[Union, discriminator] 액션을 포함하므로
        # google-genai의 response_schema(JSON Schema 변환)에 그대로 넣으면 깨질 수 있다.
        # 시스템 프롬프트로 JSON 형식을 강제하고 직접 파싱한다.
        config = types.GenerateContentConfig(
            system_instruction=system_prompt + "\n\n" + _JSON_FORMAT_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.4,
        )

        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        raw = (getattr(resp, "text", None) or "").strip()
        if not raw:
            raise ValueError("empty response")
        # 일부 응답이 ```json ... ``` 로 감싸지는 경우 제거
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        return AIChatResponse.model_validate_json(raw)
    except Exception as e:
        logger.exception("[chat_service] Gemini 호출 실패: %s", e)
        text = "죄송해요, 다시 한 번 말씀해 주세요."
        return AIChatResponse(
            intent="error",
            response_text=text,
            actions=[SpeakAction(text=text)],
            requires_user_input=True,
        )


# ─── 메인 처리기 ─────────────────────────────────────────────────────────────

async def process_chat_message(
    db: AsyncSession,
    session: KioskSession,
    user_content: str,
    *,
    purpose: str = "voice_order",
    persona: str = "unknown",
    current_stage: str = "greeting",
    cart_snapshot: Optional[List[CartItemSnapshot]] = None,
) -> tuple[AIChatResponse, str]:
    """
    Returns: (response, matched_by)
    """
    if session.voice_attempt_started_at is None:
        # 보호: voice/start 없이 호출되면 즉시 attempt 시작
        await chat_crud.start_new_attempt(db, session, persona=persona, stage=current_stage)

    attempt = session.voice_attempt_started_at
    sanitized = sanitize_input(user_content)
    if not sanitized:
        text = "잘 못 들었어요. 다시 한 번 말씀해 주세요."
        resp = AIChatResponse(
            intent="empty",
            response_text=text,
            actions=[SpeakAction(text=text)],
            requires_user_input=True,
        )
        return resp, "empty"

    try:
        check_jailbreak(sanitized)
    except JailbreakDetectedError:
        text = "그런 요청은 도와드릴 수 없어요. 음료 주문을 도와드릴게요."
        resp = AIChatResponse(
            intent="jailbreak_blocked",
            response_text=text,
            actions=[SpeakAction(text=text)],
            requires_user_input=True,
        )
        await _save_pair(db, session, attempt, sanitized, resp, purpose, "blocked")
        return resp, "blocked"

    # ── fast path 1: 패턴 매칭 ──
    pattern_resp = match_pattern(sanitized, purpose=purpose)
    if pattern_resp is not None:
        await _save_pair(db, session, attempt, sanitized, pattern_resp, purpose, "pattern")
        await _apply_stage_update(db, session, pattern_resp)
        return pattern_resp, "pattern"

    # ── fast path 2: 메뉴 이름 직접 언급 ──
    if purpose == "voice_order":
        menu_names = await _list_menu_names(db)
        menu_resp = match_menu_name(sanitized, menu_names)
        if menu_resp is not None:
            await _save_pair(db, session, attempt, sanitized, menu_resp, purpose, "menu_name")
            await _apply_stage_update(db, session, menu_resp)
            return menu_resp, "menu_name"

    # ── slow path: Gemini ──
    history_rows = await chat_crud.list_messages_for_context(
        db,
        session_id=session.id,
        attempt_started_at=attempt,
        purpose=purpose,
        max_total_chars=5000,
    )
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    menu_catalog_text = ""
    if purpose == "voice_order":
        menu_catalog_text = await get_cached_menu_catalog_text(db)

    system_prompt = build_system_prompt(
        persona=persona,
        stage=current_stage,
        menu_catalog_text=menu_catalog_text,
        cart_snapshot=cart_snapshot,
    )

    resp = await _call_gemini_structured(
        system_prompt=system_prompt,
        history=history,
        user_message=sanitized,
    )
    await _save_pair(db, session, attempt, sanitized, resp, purpose, "gemini")
    await _apply_stage_update(db, session, resp)
    return resp, "gemini"


async def process_voice_message(
    db: AsyncSession,
    session: KioskSession,
    user_content: str,
    *,
    persona: str = "unknown",
    current_stage: str = "greeting",
    cart_snapshot: Optional[List[CartItemSnapshot]] = None,
) -> tuple[AIChatResponse, str]:
    return await process_chat_message(
        db,
        session,
        user_content,
        purpose="voice_order",
        persona=persona,
        current_stage=current_stage,
        cart_snapshot=cart_snapshot,
    )


# ─── 내부 유틸 ───────────────────────────────────────────────────────────────

async def _save_pair(
    db: AsyncSession,
    session: KioskSession,
    attempt: datetime,
    user_content: str,
    response: AIChatResponse,
    purpose: str,
    matched_by: str,
) -> None:
    await chat_crud.insert_message(
        db,
        session_id=session.id,
        attempt_started_at=attempt,
        role="user",
        content=user_content,
        purpose=purpose,
        commit=False,
    )
    await chat_crud.insert_message(
        db,
        session_id=session.id,
        attempt_started_at=attempt,
        role="assistant",
        content=response.response_text,
        purpose=purpose,
        intent=response.intent,
        matched_by=matched_by,
        response_metadata={
            "actions": [a.model_dump() for a in response.actions],
            "next_stage": response.next_stage,
            "end_conversation": response.end_conversation,
        },
        commit=True,
    )


async def _apply_stage_update(
    db: AsyncSession,
    session: KioskSession,
    response: AIChatResponse,
) -> None:
    changed = False
    if response.next_stage and response.next_stage != session.voice_current_stage:
        session.voice_current_stage = response.next_stage
        changed = True
    if response.end_conversation:
        session.voice_attempt_started_at = None
        session.voice_current_stage = None
        changed = True
    if changed:
        await db.commit()
        await db.refresh(session)
