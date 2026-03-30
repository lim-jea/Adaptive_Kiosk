from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from core.database import Base


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    preferred_category = Column(String(50), nullable=False)           # 선호 계열 (커피, 라떼, 에이드 등)
    recommendation_type = Column(String(20), nullable=False)          # "your_picks" / "discovery"
    recommended_menu_id = Column(Integer, ForeignKey("menus.id"), nullable=True)
    was_clicked = Column(Boolean, default=False, nullable=False)
    led_to_order = Column(Boolean, default=False, nullable=False)     # 실제 주문으로 이어졌는지
