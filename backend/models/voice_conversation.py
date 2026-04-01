from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from core.database import Base


class VoiceConversation(Base):
    __tablename__ = "voice_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    turn = Column(Integer, nullable=False)                         # 대화 순서 (1, 2, 3...)
    speaker = Column(String(10), nullable=False)                   # "system" / "user"
    tts_text = Column(Text, nullable=True)                         # TTS로 출력한 텍스트
    stt_text = Column(Text, nullable=True)                         # STT로 인식된 텍스트
    intent = Column(String(50), nullable=True)                     # 파싱된 의도 (order, cancel, help, unknown 등)
    matched_by = Column(String(20), nullable=True)                 # "pattern" / "gemini" / None
    ai_response = Column(Text, nullable=True)                      # AI가 생성한 응답 텍스트
    resolved = Column(Boolean, default=False, nullable=False)      # 이 턴에서 요청이 해결되었는지
