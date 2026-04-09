"""
음성 주문 REST 엔드포인트.

POST /voice/start      한 세션 안에서 새로운 음성 시도(attempt)를 시작
POST /voice/messages   사용자 발화 → AI 응답 (패턴/메뉴/Gemini)
GET  /voice/messages   특정 세션의 메시지 이력 (페이지네이션)
POST /voice/end        진행 중인 음성 시도 종료
"""
import base64

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
from services.chat_prompts import GREETING_BY_PERSONA, decide_persona_from_age_group
from services.chat_service import process_voice_message, synthesize_speech


async def _audio_for_response(response):
    """response_text 전체를 통째로 합성. 디스크 캐시 hit이면 즉시 반환."""
    return await synthesize_speech(response.response_text)

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
    session = await _get_session_or_404(db, req.session_uuid)

    persona = decide_persona_from_age_group(session.estimated_age_group)
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

    audio_bytes = await _audio_for_response(greeting)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else None

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

    persona = session.voice_persona or decide_persona_from_age_group(session.estimated_age_group)
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

    audio_bytes = await _audio_for_response(response)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else None

    return VoiceMessageResponse(
        session_uuid=session.session_uuid,
        persona=persona,  # type: ignore[arg-type]
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
    """텍스트 → Gemini Flash TTS → audio/wav 바이트 반환.
    실패 시 404 → 프런트는 브라우저 speechSynthesis로 폴백."""
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
