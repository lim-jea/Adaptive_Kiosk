"""
[보류] 비전 raw 결과 수신 엔드포인트.
현재는 face/analyze로 통합되어 사용하지 않음.
2단계에서 별도 비전 모듈(YOLO/저조도 보정 등) 결과 저장이 필요할 때 다시 활성화.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/vision", tags=["Vision (deprecated)"])
