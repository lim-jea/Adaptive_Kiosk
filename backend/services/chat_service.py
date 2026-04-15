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
from models.session import KioskSession
from schemas.chat import AIChatResponse, CartItemSnapshot, SpeakAction
from services.chat_prompts import (
    build_stage_context,
    build_system_prompt,
    check_jailbreak,
    match_menu_name,
    match_pattern,
    sanitize_input,
    JailbreakDetectedError,
)
from crud.menu import get_menus
from services.canned_responses import (
    all_canned_texts,
    get_cached_wav,
    get_canned_phrases_for_prompt,
    match_canned,
    save_cached_wav,
)

logger = logging.getLogger(__name__)


# ─── Gemini 클라이언트 (지연 초기화) ─────────────────────────────────────────

_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
_client = None


# ─── TTS — 디스크 캐시 전용 (Gemini 라이브 합성 비활성) ────────────────────
# Gemini TTS preview는 일일 100회 한도(티어 무관)라 현재 비활성.
# 디스크 캐시(data/tts_cache/)에 있으면 즉시 반환, 없으면 None → 브라우저 TTS 폴백.
# 추후 한도가 늘어나면 docs/음성 조합 합성 재활성화 가이드.md 참고.

from collections import OrderedDict
_TTS_MEM_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_TTS_MEM_MAX = 64


async def synthesize_speech(text: str) -> Optional[bytes]:
    """디스크 캐시에서 WAV 로드. 없으면 None (프런트가 브라우저 TTS로 폴백)."""
    if not text:
        return None
    # 메모리 LRU
    wav = _TTS_MEM_CACHE.get(text)
    if wav is not None:
        _TTS_MEM_CACHE.move_to_end(text)
        return wav
    # 디스크
    wav = get_cached_wav(text)
    if wav is not None:
        _TTS_MEM_CACHE[text] = wav
        _TTS_MEM_CACHE.move_to_end(text)
        while len(_TTS_MEM_CACHE) > _TTS_MEM_MAX:
            _TTS_MEM_CACHE.popitem(last=False)
        return wav
    return None


async def prewarm_tts_cache(db_factory=None) -> int:
    """
    서버 부팅 시 호출 — 시나리오 매뉴얼의 response_text만 합성해 디스크 캐시에 적재.
    조합 합성(템플릿/조각)은 현재 비활성. 이미 캐시된 항목은 자동으로 건너뛴다.
    db_factory 인자는 호환성을 위해 남겨두지만 사용하지 않는다.
    """
    if _get_client() is None:
        return 0

    phrases = list(dict.fromkeys(p for p in all_canned_texts() if p))

    n = 0
    for phrase in phrases:
        try:
            if await synthesize_speech(phrase):
                n += 1
        except Exception:
            pass
    logger.info("[chat_service] TTS 프리워밍 완료: %d/%d", n, len(phrases))
    return n


_JSON_FORMAT_INSTRUCTION = """[JSON 스키마]
{
  "intent": "사용자 의도 분류 키 (예: greet, select_menu, add_to_cart, cancel 등)",
  "response_text": "손님에게 음성으로 들려줄 한국어 문장",
  "next_stage": "다음 단계. greeting|category_browse|menu_browse|menu_select|option_select|cart_review|payment_confirm|farewell 중 하나. 변경 없으면 null",
  "actions": [],
  "requires_user_input": "사용자 응답이 필요하면 true",
  "end_conversation": "대화를 종료하려면 true"
}

actions 종류와 용도:
- speak: 손님에게 음성 안내. {"type":"speak","text":"안내 문장"}
- navigate: 키오스크 화면 이동.
  {"type":"navigate","target":"...","category_name":"...","menu_name":"..."}
  · target=category → 해당 카테고리의 메뉴 목록 화면으로 이동
  · target=menu_detail → 해당 메뉴의 옵션 선택 화면으로 이동
  · target=menu_list → 전체 메뉴 목록으로 이동
  · target=cart → 장바구니 화면 열기
  · target=payment → 결제 화면으로 이동
- scroll: 메뉴 목록 스크롤. {"type":"scroll","direction":"up|down"}
- option_preview: 옵션을 화면에 시각적으로 표시 (장바구니에는 안 담김).
  {"type":"option_preview","menu_name":"...","option_item_ids":[정수]}
- cart_add: 장바구니에 메뉴 추가. 모든 필수 옵션이 결정된 후에만 사용.
  {"type":"cart_add","menu_name":"...","quantity":정수,"option_item_ids":[정수]}
- cart_remove: 장바구니에서 메뉴 제거. {"type":"cart_remove","menu_name":"..."}
- cart_update: 장바구니 메뉴 수량 변경. {"type":"cart_update","menu_name":"...","quantity":정수}
- place_order: 주문 확정/결제 진행. {"type":"place_order"}
- end_conversation: 대화 종료. {"type":"end_conversation"}

JSON 객체 하나만 출력. 다른 텍스트 금지."""


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


# ─── Gemini 호출용 단순화 스키마 ──────────────────────────────────────────────
# AIChatResponse의 actions는 Annotated[Union, discriminator]라 response_schema에
# 직접 넣으면 깨진다. 액션을 평탄한 dict으로 받는 스키마를 따로 정의해서
# response_schema로 보내고, 응답은 파싱 없이 바로 사용한다.

from pydantic import BaseModel as _BaseModel


class _GeminiAction(_BaseModel):
    type: str
    text: Optional[str] = None
    target: Optional[str] = None
    category_name: Optional[str] = None
    menu_name: Optional[str] = None
    direction: Optional[str] = None
    quantity: Optional[int] = None
    option_item_ids: Optional[List[int]] = None


class _GeminiResponse(_BaseModel):
    intent: str
    response_text: str
    next_stage: Optional[str] = None
    actions: List[_GeminiAction] = []
    requires_user_input: bool = True
    end_conversation: bool = False


_VALID_STAGES = frozenset({
    "greeting", "category_browse", "menu_browse", "menu_select",
    "option_select", "cart_review", "payment_confirm", "farewell",
})


def _gemini_to_chat_response(g: _GeminiResponse) -> AIChatResponse:
    """Gemini 응답 → AIChatResponse 변환. next_stage 보정 포함."""
    return AIChatResponse(
        intent=g.intent,
        response_text=g.response_text,
        next_stage=g.next_stage if g.next_stage in _VALID_STAGES else None,
        actions=[a.model_dump(exclude_none=True) for a in g.actions],
        requires_user_input=g.requires_user_input,
        end_conversation=g.end_conversation,
    )


# ─── Gemini 호출 ─────────────────────────────────────────────────────────────

async def _call_gemini_structured(
    *,
    system_prompt: str,
    history: list[dict],
    user_message: str,
) -> AIChatResponse:
    client = _get_client()
    if client is None:
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

        config = types.GenerateContentConfig(
            system_instruction=system_prompt + "\n\n" + _JSON_FORMAT_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_GeminiResponse,
            temperature=0.4,
        )

        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        # response_schema를 사용하면 SDK가 자동 파싱해준다
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, _GeminiResponse):
            return _gemini_to_chat_response(parsed)

        # 일부 SDK 버전에서 parsed가 안 채워질 수 있으므로 수동 폴백
        raw = (getattr(resp, "text", None) or "").strip()
        if not raw:
            raise ValueError("empty response")
        g = _GeminiResponse.model_validate_json(raw)
        return _gemini_to_chat_response(g)

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
    selected_category: Optional[str] = None,
    selected_menu_name: Optional[str] = None,
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

    # ── fast path 0: 시나리오 매뉴얼 매칭 (디스크 캐시된 응답 즉시 반환) ──
    if purpose == "voice_order":
        canned_resp = match_canned(sanitized, current_stage)
        if canned_resp is not None:
            await _save_pair(db, session, attempt, sanitized, canned_resp, purpose, "canned")
            await _apply_stage_update(db, session, canned_resp)
            return canned_resp, "canned"

    # ── fast path 1: 코드 패턴 매칭 (인사/취소/긍정/부정/도움) ──
    pattern_resp = match_pattern(sanitized, purpose=purpose)
    if pattern_resp is not None:
        await _save_pair(db, session, attempt, sanitized, pattern_resp, purpose, "pattern")
        await _apply_stage_update(db, session, pattern_resp)
        return pattern_resp, "pattern"

    # ── fast path 2: 메뉴 이름 직접 매칭 (긴 이름 우선) ──
    if purpose == "voice_order":
        menu_rows, _ = await get_menus(db, limit=500)
        menu_names = [r["name"] for r in menu_rows]
        menu_resp = match_menu_name(sanitized, menu_names)
        if menu_resp is not None:
            await _save_pair(db, session, attempt, sanitized, menu_resp, purpose, "menu_name")
            await _apply_stage_update(db, session, menu_resp)
            return menu_resp, "menu_name"

    # ── Gemini 호출 ──
    history_rows = await chat_crud.list_messages_for_context(
        db,
        session_id=session.id,
        attempt_started_at=attempt,
        purpose=purpose,
        max_total_chars=5000,
    )
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    stage_context = ""
    if purpose == "voice_order":
        stage_context = await build_stage_context(
            db,
            stage=current_stage,
            selected_category=selected_category,
            selected_menu_name=selected_menu_name,
        )
        # 권장 응답 매뉴얼 주입 — AI가 매뉴얼 문구를 그대로 복사하면
        # 디스크 캐시 hit으로 TTS가 즉시 재생됨
        canned_block = get_canned_phrases_for_prompt(current_stage)
        if canned_block:
            stage_context = f"{stage_context}\n\n{canned_block}"

    system_prompt = build_system_prompt(
        persona=persona,
        stage=current_stage,
        stage_context=stage_context,
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
    selected_category: Optional[str] = None,
    selected_menu_name: Optional[str] = None,
) -> tuple[AIChatResponse, str]:
    return await process_chat_message(
        db,
        session,
        user_content,
        purpose="voice_order",
        persona=persona,
        current_stage=current_stage,
        cart_snapshot=cart_snapshot,
        selected_category=selected_category,
        selected_menu_name=selected_menu_name,
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
        # 구조화된 응답 전체(actions/next_stage/requires_user_input/end_conversation)를
        # 메타데이터 컬럼에 그대로 저장 — 이력 분석/재현/디버깅에 사용
        response_metadata=response.model_dump(mode="json"),
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
