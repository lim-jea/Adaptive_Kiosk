from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VisionEventCreate(BaseModel):
    """비전 모듈이 보내는 분석 결과"""
    low_light_corrected: bool = False
    detected_people_count: int = 0
    masked_faces_count: int = 0
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    age_confidence: Optional[float] = None
    confusion_detected: bool = False


class VisionEventResponse(BaseModel):
    id: int
    session_id: int
    created_at: datetime
    low_light_corrected: bool
    detected_people_count: int
    masked_faces_count: int
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    age_confidence: Optional[float] = None
    confusion_detected: bool

    model_config = {"from_attributes": True}


class SimpleModeDecision(BaseModel):
    """비전 결과 저장 후 반환되는 간편모드 판단 결과"""
    should_use_simple_mode: bool
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
