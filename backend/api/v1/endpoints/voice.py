"""
[보류] 음성 주문 엔드포인트.
2단계 음성 주문 활성화 시 다시 구현. crud/voice.py와 함께 사용.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/voice", tags=["Voice (deprecated)"])
