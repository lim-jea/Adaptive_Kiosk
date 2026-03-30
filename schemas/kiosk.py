from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class KioskRegister(BaseModel):
    """키오스크 등록 요청"""
    name: str
    location: Optional[str] = None


class KioskRegisterResponse(BaseModel):
    """등록 후 API 키 반환"""
    id: int
    name: str
    location: Optional[str] = None
    api_key: str


class KioskLoginRequest(BaseModel):
    """키오스크 로그인 (API 키로 인증)"""
    api_key: str


class KioskResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    is_active: bool
    registered_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
