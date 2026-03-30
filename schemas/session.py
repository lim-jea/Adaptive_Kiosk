from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SessionCreate(BaseModel):
    """세션 시작 시 프런트에서 보내는 데이터 (비전 결과 수신 전이므로 최소한)"""
    pass


class SessionUpdate(BaseModel):
    """세션 상태 업데이트 (간편모드 전환 등)"""
    is_simple_mode: Optional[bool] = None
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    help_triggered: Optional[bool] = None


class SessionResponse(BaseModel):
    id: int
    kiosk_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    is_simple_mode: bool
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    help_triggered: bool
    status: str

    model_config = {"from_attributes": True}
