from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class KioskCreateRequest(BaseModel):
    """키오스크 생성 요청 (관리자)"""
    name: str = Field(..., min_length=1, max_length=100, examples=["1층 로비 키오스크"])
    location: Optional[str] = Field(None, max_length=200, examples=["서울 강남점 1층 입구"])


class KioskListRequest(BaseModel):
    """키오스크 목록 조회 요청"""
    is_active: Optional[bool] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class KioskResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    is_active: bool
    registered_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KioskCreateResponse(KioskResponse):
    """등록 시에만 API 키 반환"""
    api_key: str
