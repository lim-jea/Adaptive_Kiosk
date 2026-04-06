"""
[보류] 추천 엔드포인트.
3단계에서 CF 추천 모델과 함께 활성화 예정.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/recommendations", tags=["Recommendation (deprecated)"])
