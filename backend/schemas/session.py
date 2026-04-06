from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from core.enums import SessionStatus, SessionEndReason


# ─── Request ───

class SessionListRequest(BaseModel):
    """세션 목록 조회 요청"""
    status: Optional[SessionStatus] = None
    kiosk_id: Optional[int] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class SessionUpdateRequest(BaseModel):
    """세션 상태 갱신 (PATCH).
    종료 시: { status: ended, end_reason: completed }
    간편모드 전환: { is_simple_mode: true, estimated_age_group: ... }
    """
    status: Optional[SessionStatus] = None
    end_reason: Optional[SessionEndReason] = None
    is_simple_mode: Optional[bool] = None
    estimated_age_group: Optional[str] = Field(None, max_length=20)
    estimated_gender: Optional[str] = Field(None, max_length=10)
    help_triggered: Optional[bool] = None


# ─── Response ───

class SessionResponse(BaseModel):
    session_uuid: str
    kiosk_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    end_reason: Optional[str] = None
    is_simple_mode: bool
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    help_triggered: bool
    status: str

    model_config = {"from_attributes": True}
