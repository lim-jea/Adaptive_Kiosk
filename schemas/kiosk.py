from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class KioskRegisterRequest(BaseModel):
    """키오스크 등록 요청"""
    name: str = Field(..., min_length=10, max_length=100, examples=["1층 로비 키오스크"])
    location: Optional[str] = Field(None, max_length=200, examples=["서울 강남점 1층 입구"])

class KioskVerifyRequest(BaseModel):
    """키오스크 기기 확인"""
    api_key: str = Field(..., min_length=64, max_length=64, examples=["a1b2c3d4..."])


class KioskResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    is_active: bool
    registered_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
