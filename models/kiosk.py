from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from core.database import Base


class Kiosk(Base):
    __tablename__ = "kiosks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)                    # "1층 로비 키오스크", "2층 매장 A" 등
    location = Column(String(200), nullable=True)                 # 설치 위치 설명
    api_key = Column(String(64), unique=True, nullable=False)     # 키오스크 인증용 API 키
    is_active = Column(Boolean, default=True, nullable=False)     # 활성/비활성
    registered_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)                # 마지막 통신 시각
