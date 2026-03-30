from typing import List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.voice_conversation import VoiceConversation


async def get_next_turn(db: AsyncSession, session_id: int) -> int:
    """세션 내 다음 대화 턴 번호를 반환합니다."""
    result = await db.execute(
        select(func.coalesce(func.max(VoiceConversation.turn), 0))
        .where(VoiceConversation.session_id == session_id)
    )
    return (result.scalar() or 0) + 1


async def save_system_turn(
    db: AsyncSession, session_id: int, turn: int, tts_text: str
) -> VoiceConversation:
    """시스템(TTS) 발화를 저장합니다."""
    record = VoiceConversation(
        session_id=session_id,
        turn=turn,
        speaker="system",
        tts_text=tts_text,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def save_user_turn(
    db: AsyncSession,
    session_id: int,
    turn: int,
    stt_text: str,
    intent: str,
    matched_by: str,
    ai_response: str,
    resolved: bool,
) -> VoiceConversation:
    """사용자 발화 + AI 응답을 저장합니다."""
    record = VoiceConversation(
        session_id=session_id,
        turn=turn,
        speaker="user",
        stt_text=stt_text,
        intent=intent,
        matched_by=matched_by,
        ai_response=ai_response,
        resolved=resolved,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_conversation_history(db: AsyncSession, session_id: int) -> List[VoiceConversation]:
    """세션의 전체 대화 이력을 반환합니다."""
    result = await db.execute(
        select(VoiceConversation)
        .where(VoiceConversation.session_id == session_id)
        .order_by(VoiceConversation.turn)
    )
    return list(result.scalars().all())


def format_history_for_prompt(records: List[VoiceConversation]) -> str:
    """대화 이력을 Gemini 프롬프트용 텍스트로 변환합니다."""
    lines = []
    for r in records:
        if r.speaker == "system" and r.tts_text:
            lines.append(f"시스템: {r.tts_text}")
        elif r.speaker == "user":
            if r.stt_text:
                lines.append(f"사용자: {r.stt_text}")
            if r.ai_response:
                lines.append(f"시스템: {r.ai_response}")
    return "\n".join(lines)
