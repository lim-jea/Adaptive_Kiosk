from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FaceAnalyzeRequest(BaseModel):
    """얼굴 분석 요청 (평문 모드)"""
    session_uuid: str = Field(..., min_length=32, max_length=32)
    frames: List[str] = Field(..., min_length=1, description="Base64 인코딩된 JPEG 프레임 목록")


class FaceAnalyzeResponse(BaseModel):
    session_uuid: str
    age_group: str
    gender: str
    age_est: int
    confidence: float
    should_use_simple_mode: bool
    analyzed_at: datetime
