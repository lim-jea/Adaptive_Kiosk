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

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rate_limit import make_debounce
from core.session_auth import assert_token_matches_session, require_valid_session_token
from crud import chat as chat_crud
from crud.session import get_session_by_uuid
from schemas import (
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
from schemas import PaginatedResponse, make_error
from services.chat_service import process_voice_message, synthesize_speech
from services.voice_prompting import GREETING_BY_PERSONA, decide_persona

logger = logging.getLogger(__name__)


async def _audio_b64_for(response) -> tuple[str | None, str]:
    """응답에 대한 mp3 (Edge-TTS) 를 base64로 인코딩.

    response_text 전체에 대한 합성(또는 메모리 캐시 hit)을 시도하고,
    실패/캐시 미스+Edge 비활성 시 None 을 반환해 프런트가 브라우저 TTS 로 폴백한다.

    Returns:
      (audio_b64_or_none, source)
      - source: edge | none | error
    """
    t0 = time.perf_counter()
    try:
        audio = await synthesize_speech(response.response_text)
        if audio:
            b64 = base64.b64encode(audio).decode("ascii")
            logger.info("[voice-metrics] audio_source=edge ms=%.1f", (time.perf_counter() - t0) * 1000)
            return b64, "edge"
        logger.info("[voice-metrics] audio_source=none ms=%.1f", (time.perf_counter() - t0) * 1000)
        return None, "none"
    except Exception:  # noqa: BLE001
        logger.info("[voice-metrics] audio_source=error ms=%.1f", (time.perf_counter() - t0) * 1000)
        return None, "error"

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.post("/start", response_model=VoiceStartResponse)
async def voice_start(
    req: VoiceStartRequest,
    db: AsyncSession = Depends(get_db),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    """음성 주문 시작.

    프런트가 화면 진입/재진입 시 반복 호출할 수 있어, 이미 진행 중인 attempt 가 있으면
    새 attempt 를 만들지 않고 그대로 재사용한다 (대화 이력 보존).
    """
    assert_token_matches_session(req.session_uuid, x_session_token)
    t0 = time.perf_counter()
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=req.session_uuid),
        )

    reused = session.voice_attempt_started_at is not None
    if reused:
        persona = session.voice_persona or decide_persona(age_group=session.estimated_age_group)
        attempt = session.voice_attempt_started_at
        current_stage = session.voice_current_stage or "greeting"
    else:
        persona = decide_persona(age_group=session.estimated_age_group)
        attempt = await chat_crud.start_new_attempt(db, session, persona=persona, stage="greeting")
        current_stage = "greeting"

    greeting_text = GREETING_BY_PERSONA[persona]
    greeting = AIChatResponse(
        intent="greet",
        response_text=greeting_text,
        next_stage=current_stage,  # type: ignore[arg-type]
        actions=[SpeakAction(text=greeting_text)],
        requires_user_input=True,
        end_conversation=False,
    )

    # 새 attempt 일 때만 인사말을 어시스턴트 메시지로 이력에 남긴다 (재사용 시 이미 존재)
    if not reused:
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
    logger.info(
        "[voice-metrics] endpoint=start reused_attempt=%d stage=%s matched_by=cached audio=%s ms=%.1f",
        int(reused),
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


@router.post(
    "/messages",
    response_model=VoiceMessageResponse,
    dependencies=[Depends(make_debounce("voice/messages", min_interval=1.0, daily_cap=60))],
)
async def voice_message(
    req: VoiceMessageRequest,
    db: AsyncSession = Depends(get_db),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    assert_token_matches_session(req.session_uuid, x_session_token)
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=req.session_uuid),
        )

    t0 = time.perf_counter()

    persona = session.voice_persona or decide_persona(age_group=session.estimated_age_group)
    stage = session.voice_current_stage or "greeting"

    response, matched_by = await process_voice_message(
        db,
        session,
        req.content,
        persona=persona,
        current_stage=stage,
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
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    assert_token_matches_session(session_uuid, x_session_token)
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
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


@router.post(
    "/tts",
    dependencies=[
        Depends(require_valid_session_token),
        Depends(make_debounce("voice/tts", min_interval=0.3, daily_cap=300)),
    ],
)
async def voice_tts(req: VoiceTTSRequest):
    """텍스트 → Edge-TTS mp3 바이트 반환 (메모리 LRU 캐시).
    실패/캐시 미스 + Edge 비활성 시 404 → 프런트는 브라우저 speechSynthesis 로 폴백.
    유효한 X-Session-Token 필수 + 세션당 0.3 초 debounce + 일일 300회 캡 (외부 API 비용 보호)."""
    audio = await synthesize_speech(req.text)
    if audio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("TTS_UNAVAILABLE", "Edge TTS not available"),
        )
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/end", response_model=VoiceEndResponse)
async def voice_end(
    req: VoiceEndRequest,
    db: AsyncSession = Depends(get_db),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    assert_token_matches_session(req.session_uuid, x_session_token)
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=req.session_uuid),
        )
    session.voice_attempt_started_at = None
    session.voice_current_stage = None
    await db.commit()
    return VoiceEndResponse(session_uuid=session.session_uuid, ended=True)
