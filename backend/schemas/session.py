from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ─── Request ───

class SessionGetRequest(BaseModel):
    """세션 조회 요청"""
    session_uuid: str = Field(..., min_length=32, max_length=32)


class SessionListRequest(BaseModel):
    """세션 목록 조회 요청"""
    active_only: bool = True
    as_list: bool = False  # 단일 조회 vs 목록 조회 구분 (내부용)


class SessionEndRequest(BaseModel):
    """세션 종료 요청"""
    reason: Literal["completed", "timeout", "cancelled"] = Field(
        default="completed",
        examples=["completed"],
    )


class SessionUpdate(BaseModel):
    """세션 상태 갱신 (2단계: 간편모드 전환 등)"""
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
