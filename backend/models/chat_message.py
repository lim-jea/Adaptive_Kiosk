from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index, func
from core.database import Base


class ChatMessage(Base):
    """
    범용 채팅 메시지 테이블.

    하나의 kiosk_session 안에서 여러 번의 채팅 시도(attempt)를 지원하기 위해
    `attempt_started_at`으로 같은 세션 내 여러 대화를 구분한다.
    현재는 음성 주문(purpose='voice_order')만 사용하지만,
    추후 텍스트 챗 등 다른 purpose도 동일 테이블에 저장할 수 있다.
    """

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    attempt_started_at = Column(DateTime, nullable=False)
    purpose = Column(String(30), nullable=False, default="voice_order")
    role = Column(String(10), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    intent = Column(String(30), nullable=True)
    matched_by = Column(String(20), nullable=True)  # pattern / gemini / cached
    response_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_chat_session_attempt",
            "session_id",
            "attempt_started_at",
            "created_at",
        ),
    )
