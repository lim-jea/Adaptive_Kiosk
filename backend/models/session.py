import uuid

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from core.database import Base


def _generate_session_uuid():
    return uuid.uuid4().hex


class KioskSession(Base):
    __tablename__ = "kiosk_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_uuid = Column(String(32), unique=True, nullable=False, default=_generate_session_uuid)
    kiosk_id = Column(Integer, ForeignKey("kiosks.id"), nullable=False)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    end_reason = Column(String(20), nullable=True)    # "completed" / "timeout" / "cancelled"
    is_simple_mode = Column(Boolean, default=False, nullable=False)
    estimated_age_group = Column(String(20), nullable=True)
    estimated_gender = Column(String(10), nullable=True)
    help_triggered = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active / ended / abandoned

    # 음성 주문 관련
    voice_persona = Column(String(20), nullable=True)            # elderly / child / general / unknown
    voice_current_stage = Column(String(30), nullable=True)      # greeting / menu_browse / ...
    voice_attempt_started_at = Column(DateTime, nullable=True)   # 현재 진행 중인 음성 시도의 시작 시각
