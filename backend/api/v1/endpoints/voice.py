from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.session import get_session
from crud.voice import (
    get_next_turn,
    save_system_turn,
    save_user_turn,
    get_conversation_history,
    format_history_for_prompt,
)
from schemas.voice import (
    VoiceInput,
    VoiceResponse,
    VoiceStartResponse,
    VoiceHistoryResponse,
    VoiceConversationRecord,
)
from services.voice_service import process_voice_input

router = APIRouter(prefix="/voice", tags=["Voice"])

GREETING_TTS = "주문을 도와드리겠습니다. 주문하시겠습니까?"


@router.post("/{session_id}/start", response_model=VoiceStartResponse)
async def start_voice_order(session_id: int, db: AsyncSession = Depends(get_db)):
    """
    음성 주문을 시작합니다.
    간편모드 진입 후 호출 → TTS 안내 텍스트를 반환하고 대화 기록을 저장합니다.
    """
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    turn = await get_next_turn(db, session_id)
    await save_system_turn(db, session_id, turn, GREETING_TTS)

    return VoiceStartResponse(tts_text=GREETING_TTS, turn=turn)


@router.post("/process", response_model=VoiceResponse)
async def process_voice(data: VoiceInput, db: AsyncSession = Depends(get_db)):
    """
    STT 결과를 받아 처리합니다.
    1. 패턴 매칭 → 즉시 응답
    2. 매칭 실패 → Gemini Flash Lite로 시나리오 기반 응답
    대화 이력을 DB에 저장합니다.
    """
    session = await get_session(db, data.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 이전 대화 이력 조회 (Gemini에 컨텍스트로 전달)
    history = await get_conversation_history(db, data.session_id)
    history_text = format_history_for_prompt(history)

    # 음성 처리 (패턴 매칭 → Gemini)
    result = await process_voice_input(data.stt_text, history_text)

    # 대화 기록 저장
    turn = await get_next_turn(db, data.session_id)
    resolved = not result["requires_followup"]
    await save_user_turn(
        db=db,
        session_id=data.session_id,
        turn=turn,
        stt_text=data.stt_text,
        intent=result["intent"],
        matched_by=result["matched_by"],
        ai_response=result["response_text"],
        resolved=resolved,
    )

    # AI 응답도 시스템 턴으로 저장 (TTS 재생용)
    next_turn = await get_next_turn(db, data.session_id)
    await save_system_turn(db, data.session_id, next_turn, result["response_text"])

    return VoiceResponse(
        intent=result["intent"],
        matched_by=result["matched_by"],
        response_text=result["response_text"],
        requires_followup=result["requires_followup"],
    )


@router.get("/{session_id}/history", response_model=VoiceHistoryResponse)
async def get_voice_history(session_id: int, db: AsyncSession = Depends(get_db)):
    """세션의 음성 대화 이력을 조회합니다."""
    records = await get_conversation_history(db, session_id)
    return VoiceHistoryResponse(
        session_id=session_id,
        conversations=[VoiceConversationRecord.model_validate(r) for r in records],
    )
