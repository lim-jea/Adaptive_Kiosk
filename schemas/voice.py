from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class VoiceInput(BaseModel):
    """STT 결과를 백엔드로 전송"""
    session_id: int
    stt_text: str


class VoiceResponse(BaseModel):
    """AI 응답 + TTS용 텍스트 반환"""
    intent: str                          # order, cancel, help, confirm, unknown 등
    matched_by: str                      # "pattern" / "gemini"
    response_text: str                   # TTS로 읽어줄 응답 텍스트
    menu_ids: Optional[List[int]] = None # 주문 관련 시 해당 메뉴 ID 목록
    requires_followup: bool = False      # 추가 대화가 필요한지


class VoiceStartResponse(BaseModel):
    """음성 주문 세션 시작 시 TTS 안내 텍스트"""
    tts_text: str
    turn: int


class VoiceConversationRecord(BaseModel):
    id: int
    session_id: int
    created_at: datetime
    turn: int
    speaker: str
    tts_text: Optional[str] = None
    stt_text: Optional[str] = None
    intent: Optional[str] = None
    matched_by: Optional[str] = None
    ai_response: Optional[str] = None
    resolved: bool

    model_config = {"from_attributes": True}


class VoiceHistoryResponse(BaseModel):
    session_id: int
    conversations: List[VoiceConversationRecord]
