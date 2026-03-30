from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from core.database import Base


class KioskSession(Base):
    __tablename__ = "kiosk_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kiosk_id = Column(Integer, ForeignKey("kiosks.id"), nullable=False)  # 어떤 키오스크에서의 세션인지
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    is_simple_mode = Column(Boolean, default=False, nullable=False)
    estimated_age_group = Column(String(20), nullable=True)   # "20대", "60대" 등
    estimated_gender = Column(String(10), nullable=True)      # "male", "female"
    help_triggered = Column(Boolean, default=False, nullable=False)  # 혼란 감지 도움 여부
    status = Column(String(20), default="active", nullable=False)    # active / ended
