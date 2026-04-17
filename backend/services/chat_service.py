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
import logging
import re
import time
from datetime import datetime
from typing import List, Optional

import base64
import io
import wave

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from crud import chat as chat_crud
from model import KioskSession
from schemas import AIChatResponse, CartAddAction, OptionPreviewAction, SpeakAction
from services.voice_matching import (
    JailbreakDetectedError,
    check_jailbreak,
    match_menu_name,
    match_pattern,
    sanitize_input,
)
from services.voice_prompting import (
    build_stage_context,
    build_system_prompt,
)
from crud.menu import get_menu_detail, get_menus
from services.cart_service import get_voice_cart_snapshot
from services.canned_responses import (
    compose_template,
    get_canned_phrases_for_prompt,
    match_canned,
)

logger = logging.getLogger(__name__)


# ─── 메뉴 이름 캐시 (menu_name fast path용) ─────────────────────────────────

_MENU_CACHE_TTL_SEC = 300
_menu_names_cache: dict = {"names": None, "expires_at": 0.0}


async def _get_cached_menu_names(db: AsyncSession) -> list[str]:
    now = time.time()
    cached = _menu_names_cache.get("names")
    if cached is not None and _menu_names_cache.get("expires_at", 0.0) > now:
        return cached
    rows, _ = await get_menus(db, limit=500)
    names = [r["name"] for r in rows if r.get("name")]
    _menu_names_cache["names"] = names
    _menu_names_cache["expires_at"] = now + _MENU_CACHE_TTL_SEC
    return names


# ─── Gemini 클라이언트 (지연 초기화) ─────────────────────────────────────────

_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
_client = None


# ─── TTS — 인메모리 캐시 + 라이브 합성 ─────────────────────────────────────
# 복잡한 디스크 캐시/프리워밍/조각 합성은 제거했다.
# 현재는 짧은 메모리 캐시만 유지하고, 미스 시 라이브 TTS를 시도한 뒤
# 실패하면 프런트가 브라우저 TTS로 폴백한다.

from collections import OrderedDict
_TTS_MEM_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_TTS_MEM_MAX = 64


async def synthesize_speech(text: str) -> Optional[bytes]:
    """텍스트 → WAV.

    우선순위:
    1) 메모리 LRU 캐시
    2) (선택) Gemini TTS 라이브 합성

    캐시 미스 & 라이브 합성 비활성 시 None (프런트가 브라우저 TTS로 폴백).
    """
    if not text:
        return None
    wav = _TTS_MEM_CACHE.get(text)
    if wav is not None:
        _TTS_MEM_CACHE.move_to_end(text)
        return wav

    if not getattr(settings, "GENAI_TTS_ENABLED", False):
        return None

    wav = await _synthesize_speech_live(text)
    if wav:
        _TTS_MEM_CACHE[text] = wav
        _TTS_MEM_CACHE.move_to_end(text)
        while len(_TTS_MEM_CACHE) > _TTS_MEM_MAX:
            _TTS_MEM_CACHE.popitem(last=False)
        return wav

    return None


async def _synthesize_speech_live(text: str) -> Optional[bytes]:
    """Gemini TTS를 호출해 WAV 바이트를 받는다. 실패 시 None."""
    client = _get_client()
    if client is None:
        return None

    from google.genai import types  # type: ignore

    voice_name = (getattr(settings, "GENAI_TTS_VOICE_NAME", "kore") or "kore").lower()
    language_code = getattr(settings, "GENAI_TTS_LANGUAGE_CODE", None)
    if isinstance(language_code, str) and language_code:
        # SpeechConfig는 ISO 639-1(예: 'ko')를 기대하는 경우가 있어 축약한다.
        language_code = language_code.split("-")[0].strip() or None

    # SDK 테스트 예제와 동일한 형태(소문자 'audio', prebuilt voice_name)
    speech_cfg = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
        )
    )
    if language_code:
        speech_cfg.language_code = language_code

    config = types.GenerateContentConfig(
        response_modalities=["audio"],
        speech_config=speech_cfg,
        temperature=0,
    )

    def _looks_like_wav(b: bytes) -> bool:
        return isinstance(b, (bytes, bytearray)) and len(b) >= 12 and b[0:4] == b"RIFF" and b[8:12] == b"WAVE"

    def _parse_audio_params(mime: str) -> dict:
        # 예: "audio/pcm;rate=24000;channels=1"
        out: dict[str, str] = {}
        if not mime:
            return out
        parts = [p.strip() for p in str(mime).split(";")]
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                out[k.strip().lower()] = v.strip()
        return out

    def _pcm16le_to_wav(pcm: bytes, *, rate: int = 24000, channels: int = 1) -> bytes:
        # Gemini TTS preview 예제 기준으로 16-bit little-endian PCM을 WAV로 감싼다.
        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setnchannels(int(channels) if channels else 1)
            wf.setsampwidth(2)
            wf.setframerate(int(rate) if rate else 24000)
            wf.writeframes(pcm or b"")
        return out.getvalue()

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            model_name = getattr(settings, "GENAI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

            resp = await client.aio.models.generate_content(
                model=model_name,
                contents=f'Produce a speech response saying "{text}"',
                config=config,
            )

            candidates = getattr(resp, "candidates", None) or []
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) or []
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if not inline:
                        continue
                    mime = getattr(inline, "mime_type", None) or ""
                    data = getattr(inline, "data", None)
                    if not data or not str(mime).startswith("audio/"):
                        continue

                    # SDK/버전에 따라 data가 bytes 또는 base64 str로 올 수 있다.
                    if isinstance(data, str):
                        try:
                            audio_bytes = base64.b64decode(data)
                        except Exception:
                            audio_bytes = data.encode("utf-8", errors="ignore")
                    else:
                        audio_bytes = bytes(data)

                    m = str(mime).lower()
                    if "wav" in m and _looks_like_wav(audio_bytes):
                        return audio_bytes

                    # PCM이면 WAV로 래핑해서 반환 (현재 파이프라인은 WAV 바이트를 기대)
                    if "pcm" in m or "l16" in m:
                        params = _parse_audio_params(m)
                        rate = int(params.get("rate", "24000")) if params.get("rate") else 24000
                        channels = int(params.get("channels", "1")) if params.get("channels") else 1
                        return _pcm16le_to_wav(audio_bytes, rate=rate, channels=channels)

                    # 기타 포맷은 현재 파이프라인이 WAV만 처리하므로 무시
            return None
        except Exception as e:
            last_error = e
            msg = str(e)
            is_internal = (" 500 " in msg) or ("INTERNAL" in msg)
            if attempt < 2 and is_internal:
                import asyncio
                await asyncio.sleep(0.6 * (attempt + 1))
                continue
            break

    if last_error is not None:
        logger.warning("[chat_service] TTS 라이브 합성 실패: %s", last_error)
    return None

_JSON_FORMAT_INSTRUCTION = """[JSON 스키마]
{
  "intent": "사용자 의도 분류 키 (예: greet, select_menu, add_to_cart, cancel 등)",
  "response_text": "손님에게 음성으로 들려줄 한국어 문장",
  "next_stage": "다음 단계. greeting|category_browse|menu_browse|menu_select|option_select|cart_review|payment_confirm|farewell 중 하나. 변경 없으면 null",
  "actions": [],
  "requires_user_input": true,
  "end_conversation": false
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
- cart_remove: 장바구니에서 메뉴 제거.
  {"type":"cart_remove","menu_name":"...","cart_line_id":"...","option_item_ids":[정수]}
- cart_update: 장바구니 메뉴 수량 변경.
  {"type":"cart_update","menu_name":"...","quantity":정수,"cart_line_id":"...","option_item_ids":[정수]}
- place_order: 주문 확정/결제 진행. {"type":"place_order"}
- end_conversation: 대화 종료. {"type":"end_conversation"}

장바구니 수정 규칙:
- cart_review / payment_confirm에서 같은 menu_name이 여러 줄이면 cart_line_id 또는 option_item_ids를 함께 넣어 정확히 가리킨다.
- 같은 menu_name이 한 줄뿐이면 menu_name만으로도 가능하다.

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
from pydantic import Field as _Field


class _GeminiAction(_BaseModel):
    type: str
    text: Optional[str] = None
    target: Optional[str] = None
    category_name: Optional[str] = None
    menu_name: Optional[str] = None
    direction: Optional[str] = None
    quantity: Optional[int] = None
    cart_line_id: Optional[str] = None
    option_item_ids: Optional[List[int]] = None


class _GeminiResponse(_BaseModel):
    intent: str
    response_text: str
    next_stage: Optional[str] = None
    actions: List[_GeminiAction] = _Field(default_factory=list)
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


def _build_runtime_context(
    *,
    session: KioskSession,
    current_stage: str,
    selected_category: Optional[str],
    selected_menu_name: Optional[str],
    cart_snapshot: Optional[list],
) -> str:
    lines = ["[현재 실행 문맥]"]
    lines.append(f"- current_stage: {current_stage}")
    lines.append(f"- is_simple_mode: {bool(session.is_simple_mode)}")
    lines.append(f"- help_triggered: {bool(session.help_triggered)}")
    if session.estimated_age_group:
        lines.append(f"- estimated_age_group: {session.estimated_age_group}")
    if session.estimated_gender:
        lines.append(f"- estimated_gender: {session.estimated_gender}")
    if selected_category:
        lines.append(f"- selected_category: {selected_category}")
    if selected_menu_name:
        lines.append(f"- selected_menu_name: {selected_menu_name}")
        lines.append("- option_modal_open: true")
    else:
        lines.append("- option_modal_open: false")
    lines.append(f"- cart_item_count: {len(cart_snapshot or [])}")
    if cart_snapshot:
        last_item = cart_snapshot[-1]
        menu_name = last_item.get("menu_name") if isinstance(last_item, dict) else getattr(last_item, "menu_name", None)
        if menu_name:
            lines.append(f"- last_cart_menu_name: {menu_name}")
    return "\n".join(lines)


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
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=500),
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
    cart_snapshot = await get_voice_cart_snapshot(db, session.id) if purpose == "voice_order" else None
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
    pattern_resp = match_pattern(sanitized, purpose=purpose, stage=current_stage)
    if pattern_resp is not None:
        await _save_pair(db, session, attempt, sanitized, pattern_resp, purpose, "pattern")
        await _apply_stage_update(db, session, pattern_resp)
        return pattern_resp, "pattern"

    # ── fast path 2: 메뉴 이름 직접 매칭 (긴 이름 우선) ──
    if purpose == "voice_order":
        menu_names = await _get_cached_menu_names(db)
        menu_resp = match_menu_name(sanitized, menu_names)
        if menu_resp is not None:
            await _save_pair(db, session, attempt, sanitized, menu_resp, purpose, "menu_name")
            await _apply_stage_update(db, session, menu_resp)
            return menu_resp, "menu_name"

    # ── fast path 3: 장바구니 요약/총액 ──
    if purpose == "voice_order" and cart_snapshot and current_stage in ("cart_review", "payment_confirm"):
        total_query = re.search(r"(총액|합계|얼마|가격|금액|계산)", sanitized)
        summary_query = re.search(r"(요약|정리|뭐\s*담겼|뭐\s*있|장바구니\s*뭐)", sanitized)
        if total_query or summary_query:
            total = sum(int(it.unit_price) * int(it.quantity) for it in cart_snapshot)
            menu_names = [it.menu_name for it in cart_snapshot if getattr(it, "menu_name", None)]
            menu_names = list(dict.fromkeys(menu_names))

            if not menu_names:
                text = "장바구니가 비어 있어요."
                resp = AIChatResponse(
                    intent="cart_empty",
                    response_text=text,
                    actions=[SpeakAction(text=text)],
                    requires_user_input=True,
                )
                await _save_pair(db, session, attempt, sanitized, resp, purpose, "cart_empty")
                return resp, "cart_empty"

            if summary_query and len(menu_names) <= 3:
                menus_text = ", ".join(menu_names)
                response_text = compose_template("order_summary_simple", menus=menus_text, price=str(total)) or (
                    f"{menus_text} 주문하셨습니다. 총 {total}원입니다."
                )
            else:
                response_text = compose_template("cart_total", price=str(total)) or f"총 {total}원입니다."

            resp = AIChatResponse(
                intent="cart_summary" if summary_query else "cart_total",
                response_text=response_text,
                actions=[SpeakAction(text=response_text)],
                requires_user_input=True,
            )
            await _save_pair(db, session, attempt, sanitized, resp, purpose, "cart_total")
            return resp, "cart_total"

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
        canned_block = get_canned_phrases_for_prompt(current_stage)
        prefix_blocks = [b for b in (canned_block,) if b]
        if prefix_blocks:
            stage_context = "\n\n".join(prefix_blocks + [stage_context])

    system_prompt = build_system_prompt(
        persona=persona,
        runtime_context=_build_runtime_context(
            session=session,
            current_stage=current_stage,
            selected_category=selected_category,
            selected_menu_name=selected_menu_name,
            cart_snapshot=cart_snapshot,
        ),
        stage=current_stage,
        stage_context=stage_context,
        cart_snapshot=cart_snapshot,
    )

    resp = await _call_gemini_structured(
        system_prompt=system_prompt,
        history=history,
        user_message=sanitized,
    )

    if purpose == "voice_order":
        try:
            await _postprocess_voice_cart_actions(
                db,
                user_message=sanitized,
                current_stage=current_stage,
                selected_menu_name=selected_menu_name,
                response=resp,
            )
        except Exception as e:
            logger.warning("[chat_service] voice action postprocess failed: %s", e)

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


_ADD_TO_CART_KEYWORDS_RE = re.compile(r"(담아|담아줘|담아\s*줘|넣어|추가|장바구니|카트|주문\s*할래|주문\s*해|결제)")


def _extract_quantity_from_text(text: str) -> int:
    """간단 수량 추출 (1~10). 실패 시 1."""
    if not text:
        return 1

    m = re.search(r"(\d+)\s*(잔|개|컵)?", text)
    if m:
        try:
            n = int(m.group(1))
            return max(1, min(10, n))
        except Exception:
            pass

    # 한국어 수량
    mapping = {
        "한": 1, "하나": 1, "1": 1,
        "두": 2, "둘": 2, "2": 2,
        "세": 3, "셋": 3, "3": 3,
        "네": 4, "넷": 4, "4": 4,
        "다섯": 5, "5": 5,
        "여섯": 6, "6": 6,
        "일곱": 7, "7": 7,
        "여덟": 8, "8": 8,
        "아홉": 9, "9": 9,
        "열": 10, "10": 10,
    }
    for k, v in mapping.items():
        if re.search(rf"{re.escape(k)}\s*(잔|개|컵)", text):
            return v

    return 1


def _finalize_option_item_ids(menu_detail: dict, requested_ids: list[int]) -> list[int]:
    """요청 옵션 + 기본 옵션을 합쳐, 가능한 한 필수 옵션을 충족하도록 보정한다."""
    option_groups = menu_detail.get("option_groups") or []
    requested_set = {int(x) for x in (requested_ids or [])}

    # group_id -> selected ids
    selected_by_group: dict[int, list[int]] = {}
    for g in option_groups:
        gid = int(g.get("id"))
        group_items = g.get("items") or []
        group_item_ids = [
            int(getattr(it, "id", None) or (it.get("id") if isinstance(it, dict) else 0))
            for it in group_items
        ]
        group_item_ids = [i for i in group_item_ids if i]
        sel = [i for i in group_item_ids if i in requested_set]
        selected_by_group[gid] = sel

    # fill defaults for required groups if needed
    for g in option_groups:
        gid = int(g.get("id"))
        is_required = bool(g.get("is_required"))
        min_select = int(g.get("min_select") or 0)
        max_select = int(g.get("max_select") or 0)
        current = selected_by_group.get(gid, [])

        if max_select and len(current) > max_select:
            current = current[:max_select]

        if is_required and len(current) < min_select:
            defaults = [
                int(getattr(it, "id", None) or (it.get("id") if isinstance(it, dict) else 0))
                for it in (g.get("items") or [])
                if bool(getattr(it, "is_default", None) if not isinstance(it, dict) else it.get("is_default"))
            ]
            defaults = [i for i in defaults if i]
            for did in defaults:
                if did not in current:
                    current.append(did)
                if len(current) >= min_select:
                    break

        # re-apply max_select guard
        if max_select and len(current) > max_select:
            current = current[:max_select]

        selected_by_group[gid] = current

    # flatten while keeping group order
    out: list[int] = []
    for g in option_groups:
        gid = int(g.get("id"))
        out.extend(selected_by_group.get(gid, []))
    return list(dict.fromkeys(out))


def _required_options_satisfied(menu_detail: dict, option_item_ids: list[int]) -> bool:
    option_groups = menu_detail.get("option_groups") or []
    selected_set = {int(x) for x in (option_item_ids or [])}

    for g in option_groups:
        if not g.get("is_required"):
            continue
        min_select = int(g.get("min_select") or 0)
        max_select = int(g.get("max_select") or 0)
        group_items = g.get("items") or []
        group_item_ids = {
            int(getattr(it, "id", None) or (it.get("id") if isinstance(it, dict) else 0))
            for it in group_items
        }
        group_item_ids.discard(0)
        selected_in_group = [i for i in selected_set if i in group_item_ids]
        if len(selected_in_group) < min_select:
            return False
        if max_select and len(selected_in_group) > max_select:
            return False
    return True


def _action_type(a) -> str | None:
    if a is None:
        return None
    t = getattr(a, "type", None)
    if isinstance(t, str):
        return t
    if isinstance(a, dict):
        return a.get("type")
    return None


async def _postprocess_voice_cart_actions(
    db: AsyncSession,
    *,
    user_message: str,
    current_stage: str,
    selected_menu_name: Optional[str],
    response: AIChatResponse,
) -> None:
    """음성 주문에서 cart_add 누락을 보정한다.

    목표:
    - option_select 단계에서 필수 옵션이 모두 결정되었으면 cart_add가 반드시 발생
    - '담아줘'류 발화인데도 action이 비어 있으면, 필수 옵션이 없거나 기본값으로 충족 가능할 때 cart_add 생성
    """
    if not response or response.end_conversation:
        return

    # 이미 cart_add가 있으면 그대로 둔다.
    if any(_action_type(a) == "cart_add" for a in (response.actions or [])):
        return

    if current_stage != "option_select":
        return

    # menu_name 후보: option_preview.menu_name > selected_menu_name
    preview_action: OptionPreviewAction | None = None
    for a in (response.actions or []):
        if _action_type(a) == "option_preview":
            preview_action = a  # type: ignore[assignment]
            break

    menu_name = None
    preview_ids: list[int] = []
    if preview_action is not None:
        menu_name = getattr(preview_action, "menu_name", None) or (preview_action.get("menu_name") if isinstance(preview_action, dict) else None)
        preview_ids = list(getattr(preview_action, "option_item_ids", None) or (preview_action.get("option_item_ids") if isinstance(preview_action, dict) else []) or [])
    if not menu_name:
        menu_name = selected_menu_name

    if not menu_name:
        return

    menu_detail = await get_menu_detail(db, menu_name)
    if not menu_detail:
        return

    quantity = _extract_quantity_from_text(user_message)

    # 1) option_preview가 있고, 그 조합(+기본값)으로 필수 옵션 충족이면 cart_add로 승격
    if preview_action is not None:
        finalized_ids = _finalize_option_item_ids(menu_detail, preview_ids)
        if _required_options_satisfied(menu_detail, finalized_ids):
            new_actions = []
            replaced = False
            for a in (response.actions or []):
                if (not replaced) and _action_type(a) == "option_preview":
                    new_actions.append(CartAddAction(menu_name=menu_name, quantity=quantity, option_item_ids=finalized_ids))
                    replaced = True
                else:
                    new_actions.append(a)
            response.actions = new_actions  # type: ignore[assignment]
            response.next_stage = "cart_review"  # type: ignore[assignment]
            return

    # 2) '담아줘'류 발화인데도 액션이 없거나 cart_add가 없으면, 필수 옵션이 없/기본값으로 충족 가능할 때 cart_add 생성
    if (response.intent or "") in ("fallback", "error"):
        return
    if not _ADD_TO_CART_KEYWORDS_RE.search(user_message or ""):
        return

    finalized_ids = _finalize_option_item_ids(menu_detail, [])
    if not _required_options_satisfied(menu_detail, finalized_ids):
        return

    response.actions = list(response.actions or []) + [CartAddAction(menu_name=menu_name, quantity=quantity, option_item_ids=finalized_ids)]  # type: ignore[assignment]
    response.next_stage = "cart_review"  # type: ignore[assignment]
