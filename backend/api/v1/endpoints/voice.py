"""
음성 주문 REST 엔드포인트.

POST /voice/start      한 세션 안에서 새로운 음성 시도(attempt)를 시작
POST /voice/messages   사용자 발화 → AI 응답 (패턴/메뉴/Gemini)
GET  /voice/messages   특정 세션의 메시지 이력 (페이지네이션)
POST /voice/end        진행 중인 음성 시도 종료
"""
import base64
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from crud import chat as chat_crud
from crud.session import get_session_by_uuid
from schemas.chat import (
    AIChatResponse,
    ChatMessageItem,
    SpeakAction,
    VoiceEndRequest,
    VoiceEndResponse,
    VoiceMessageRequest,
    VoiceMessageResponse,
    VoiceStartRequest,
    VoiceStartResponse,
)
from schemas.common import PaginatedResponse, make_error
from services.canned_responses import compose_audio_from_segments
from services.chat_prompts import GREETING_BY_PERSONA, decide_persona
from services.chat_service import process_voice_message, synthesize_speech

logger = logging.getLogger(__name__)


async def _audio_b64_for(response) -> tuple[str | None, str]:
    """응답에 대한 WAV를 base64로 변환.

    - response.audio_segments가 있으면 조각 WAV를 이어붙여 즉시 반환
    - 없거나 조각 캐시 미스면 response_text 전체 WAV를 시도

    실패/캐시 미스 시 None (프런트는 브라우저 TTS로 폴백).

    Returns:
      (audio_b64_or_none, source)
      - source: segments|tts|none|error
    """
    t0 = time.perf_counter()
    try:
        if getattr(response, "audio_segments", None):
            composed = compose_audio_from_segments(response.audio_segments)  # type: ignore[arg-type]
            if composed is not None:
                b64 = base64.b64encode(composed).decode("ascii")
                logger.info("[voice-metrics] audio_source=segments ms=%.1f segs=%d", (time.perf_counter() - t0) * 1000, len(response.audio_segments))
                return b64, "segments"

        # 조각 합성만 사용(segments-only) 모드: 조각 캐시 미스면 즉시 브라우저 TTS로 폴백
        if getattr(settings, "VOICE_AUDIO_SEGMENTS_ONLY", False):
            logger.info("[voice-metrics] audio_source=none ms=%.1f", (time.perf_counter() - t0) * 1000)
            return None, "none"

        wav = await synthesize_speech(response.response_text)
        if wav:
            b64 = base64.b64encode(wav).decode("ascii")
            logger.info("[voice-metrics] audio_source=tts ms=%.1f", (time.perf_counter() - t0) * 1000)
            return b64, "tts"
        logger.info("[voice-metrics] audio_source=none ms=%.1f", (time.perf_counter() - t0) * 1000)
        return None, "none"
    except Exception:  # noqa: BLE001
        logger.info("[voice-metrics] audio_source=error ms=%.1f", (time.perf_counter() - t0) * 1000)
        return None, "error"

router = APIRouter(prefix="/voice", tags=["Voice"])


async def _get_session_or_404(db: AsyncSession, session_uuid: str):
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
    return session


@router.post("/start", response_model=VoiceStartResponse)
async def voice_start(req: VoiceStartRequest, db: AsyncSession = Depends(get_db)):
    t0 = time.perf_counter()
    session = await _get_session_or_404(db, req.session_uuid)

    # /voice/start는 프런트에서 화면 진입/재진입 시 반복 호출될 수 있다.
    # 이미 진행 중인 attempt가 있으면 새 attempt를 만들지 않고 그대로 재사용해
    # 같은 음성 주문 세션의 대화 이력이 끊기지 않게 한다.
    if session.voice_attempt_started_at is not None:
        persona = session.voice_persona or decide_persona(age_group=session.estimated_age_group)
        attempt = session.voice_attempt_started_at
        current_stage = session.voice_current_stage or "greeting"
        greeting_text = GREETING_BY_PERSONA[persona]
        greeting = AIChatResponse(
            intent="greet",
            response_text=greeting_text,
            next_stage=current_stage,  # type: ignore[arg-type]
            actions=[SpeakAction(text=greeting_text)],
            requires_user_input=True,
            end_conversation=False,
        )

        audio_b64, audio_src = await _audio_b64_for(greeting)
        logger.info(
            "[voice-metrics] endpoint=start reused_attempt=1 stage=%s matched_by=cached audio=%s ms=%.1f",
            current_stage,
            audio_src,
            (time.perf_counter() - t0) * 1000,
        )

        return VoiceStartResponse(
            session_uuid=session.session_uuid,
            persona=persona,  # type: ignore[arg-type]
            current_stage=current_stage,  # type: ignore[arg-type]
            attempt_started_at=attempt,
            greeting=greeting,
            audio_b64=audio_b64,
        )

    persona = decide_persona(age_group=session.estimated_age_group)
    attempt = await chat_crud.start_new_attempt(db, session, persona=persona, stage="greeting")

    greeting_text = GREETING_BY_PERSONA[persona]
    greeting = AIChatResponse(
        intent="greet",
        response_text=greeting_text,
        next_stage="greeting",
        actions=[SpeakAction(text=greeting_text)],
        requires_user_input=True,
        end_conversation=False,
    )

    # 인사말은 어시스턴트 메시지로 이력에 남겨둔다 (다음 turn 컨텍스트용)
    await chat_crud.insert_message(
        db,
        session_id=session.id,
        attempt_started_at=attempt,
        role="assistant",
        content=greeting_text,
        purpose="voice_order",
        intent="greet",
        matched_by="cached",
    )

    audio_b64, audio_src = await _audio_b64_for(greeting)
    logger.info("[voice-metrics] endpoint=start stage=greeting matched_by=cached audio=%s ms=%.1f", audio_src, (time.perf_counter() - t0) * 1000)

    return VoiceStartResponse(
        session_uuid=session.session_uuid,
        persona=persona,  # type: ignore[arg-type]
        current_stage="greeting",
        attempt_started_at=attempt,
        greeting=greeting,
        audio_b64=audio_b64,
    )


@router.post("/messages", response_model=VoiceMessageResponse)
async def voice_message(req: VoiceMessageRequest, db: AsyncSession = Depends(get_db)):
    session = await _get_session_or_404(db, req.session_uuid)

    t0 = time.perf_counter()

    persona = session.voice_persona or decide_persona(age_group=session.estimated_age_group)
    stage = session.voice_current_stage or "greeting"

    response, matched_by = await process_voice_message(
        db,
        session,
        req.content,
        persona=persona,
        current_stage=stage,
        cart_snapshot=req.cart_snapshot,
        selected_category=req.selected_category,
        selected_menu_name=req.selected_menu_name,
    )

    # process_voice_message가 session.voice_current_stage를 갱신했으므로 최신 값 반영
    await db.refresh(session)

    audio_b64, audio_src = await _audio_b64_for(response)
    logger.info(
        "[voice-metrics] endpoint=messages stage=%s matched_by=%s audio=%s ms=%.1f",
        session.voice_current_stage or stage,
        matched_by,
        audio_src,
        (time.perf_counter() - t0) * 1000,
    )

    return VoiceMessageResponse(
        session_uuid=session.session_uuid,
        persona=session.voice_persona or persona,  # type: ignore[arg-type]
        current_stage=session.voice_current_stage or stage,  # type: ignore[arg-type]
        matched_by=matched_by,
        response=response,
        audio_b64=audio_b64,
    )


@router.get("/messages", response_model=PaginatedResponse[ChatMessageItem])
async def voice_messages_history(
    session_uuid: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session_or_404(db, session_uuid)
    items, total = await chat_crud.list_messages_paginated(
        db,
        session_id=session.id,
        attempt_started_at=session.voice_attempt_started_at,
        purpose="voice_order",
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


class VoiceTTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def voice_tts(req: VoiceTTSRequest):
    """텍스트 → (디스크 캐시 또는 설정에 따라 라이브 TTS) → audio/wav 바이트 반환.
    실패/캐시 미스 시 404 → 프런트는 브라우저 speechSynthesis로 폴백."""
    wav = await synthesize_speech(req.text)
    if wav is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("TTS_UNAVAILABLE", "Gemini TTS not available"),
        )
    return Response(content=wav, media_type="audio/wav")


@router.post("/end", response_model=VoiceEndResponse)
async def voice_end(req: VoiceEndRequest, db: AsyncSession = Depends(get_db)):
    session = await _get_session_or_404(db, req.session_uuid)
    session.voice_attempt_started_at = None
    session.voice_current_stage = None
    await db.commit()
    return VoiceEndResponse(session_uuid=session.session_uuid, ended=True)
