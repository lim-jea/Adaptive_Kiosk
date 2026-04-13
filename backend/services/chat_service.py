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
    sanitize_input,
    JailbreakDetectedError,
)
from services.canned_responses import (
    all_canned_texts,
    get_cached_wav,
    get_canned_phrases_for_prompt,
    match_canned,
    save_cached_wav,
)

logger = logging.getLogger(__name__)


# ─── Gemini 클라이언트 (지연 초기화) ─────────────────────────────────────────

_GEMINI_MODEL = "gemini-3.1-flash-preview"
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
{"intent":"string","response_text":"string","next_stage":"string|null","actions":[...],"requires_user_input":bool,"end_conversation":bool}

actions 종류:
- speak: {"type":"speak","text":"..."}
- navigate: {"type":"navigate","target":"menu_list|menu_detail|category|cart|payment","category_name":"...","menu_name":"..."}
- scroll: {"type":"scroll","direction":"up|down"}
- option_preview: {"type":"option_preview","menu_name":"...","option_item_ids":[int]}
- cart_add: {"type":"cart_add","menu_name":"...","quantity":int,"option_item_ids":[int]}
- cart_remove: {"type":"cart_remove","menu_name":"..."}
- cart_update: {"type":"cart_update","menu_name":"...","quantity":int}
- place_order: {"type":"place_order"}
- end_conversation: {"type":"end_conversation"}

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


# ─── 메뉴 이름 캐시 (matcher용) ─────────────────────────────────────────────

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

        # AI가 잘못된 next_stage를 보내면 파싱이 깨지므로 먼저 보정
        import json as _json
        try:
            raw_dict = _json.loads(raw)
        except _json.JSONDecodeError:
            raise ValueError("invalid JSON")

        _VALID_STAGES = {
            "greeting", "category_browse", "menu_browse", "menu_select",
            "option_select", "cart_review", "payment_confirm", "farewell",
        }
        if raw_dict.get("next_stage") not in _VALID_STAGES:
            raw_dict["next_stage"] = None

        parsed = AIChatResponse.model_validate(raw_dict)

        # audio_segments 무결성 체크 — text와 합쳐 본 결과가 너무 다르면 무시
        if parsed.audio_segments:
            joined = "".join(parsed.audio_segments).replace(" ", "")
            target = (parsed.response_text or "").replace(" ", "")
            if joined and target and (
                abs(len(joined) - len(target)) > max(3, len(target) // 4)
            ):
                logger.warning(
                    "[chat_service] audio_segments mismatch — 무시. text=%r segments=%r",
                    parsed.response_text, parsed.audio_segments,
                )
                parsed.audio_segments = None
        return parsed
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

    # ── fast path: 시나리오 매뉴얼 매칭 (디스크 캐시된 응답 즉시 반환) ──
    if purpose == "voice_order":
        canned_resp = match_canned(sanitized, current_stage)
        if canned_resp is not None:
            await _save_pair(db, session, attempt, sanitized, canned_resp, purpose, "canned")
            await _apply_stage_update(db, session, canned_resp)
            return canned_resp, "canned"

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
