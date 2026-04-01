from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, func
from core.database import Base


class VisionEvent(Base):
    __tablename__ = "vision_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    low_light_corrected = Column(Boolean, default=False, nullable=False)
    detected_people_count = Column(Integer, default=0, nullable=False)
    masked_faces_count = Column(Integer, default=0, nullable=False)     # 비사용자 블러 처리 수
    estimated_age_group = Column(String(20), nullable=True)
    estimated_gender = Column(String(10), nullable=True)
    age_confidence = Column(Float, nullable=True)
    confusion_detected = Column(Boolean, default=False, nullable=False)  # 혼란 감지 여부
