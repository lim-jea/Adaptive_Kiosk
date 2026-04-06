from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.session import get_session_by_uuid, update_session
from crud.vision import create_vision_event
from services.face_service import face_service
from services.vision_service import SIMPLE_MODE_AGE_GROUPS
from schemas.face import FaceAnalyzeRequest, FaceAnalyzeResponse
from schemas.vision import VisionEventCreate
from schemas.common import make_error

router = APIRouter(prefix="/face", tags=["Face"])


@router.post("/analyze", response_model=FaceAnalyzeResponse)
async def analyze_face(
    req: FaceAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """카메라 프레임 분석 + 세션 업데이트 + vision_event 저장."""
    # 1. 세션 검증
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error(
                "SESSION_NOT_FOUND", "Session not found", session_uuid=req.session_uuid
            ),
        )

    # 2. 얼굴 분석
    result = await face_service.analyze(req.frames)

    # 3. 간편모드 판단
    should_simple = (
        result.age_group in SIMPLE_MODE_AGE_GROUPS and result.confidence >= 0.7
    )

    # 4. vision_event 저장
    vision_data = VisionEventCreate(
        low_light_corrected=False,
        detected_people_count=1 if result.confidence > 0 else 0,
        masked_faces_count=0,
        estimated_age_group=result.age_group,
        estimated_gender=result.gender,
        age_confidence=result.confidence,
        confusion_detected=False,
    )
    await create_vision_event(db, session.id, vision_data)

    # 5. 세션 업데이트
    await update_session(
        db,
        req.session_uuid,
        {
            "estimated_age_group": result.age_group,
            "estimated_gender": result.gender,
            "is_simple_mode": should_simple,
        },
    )

    return FaceAnalyzeResponse(
        session_uuid=req.session_uuid,
        age_group=result.age_group,
        gender=result.gender,
        age_est=result.age_est,
        confidence=result.confidence,
        should_use_simple_mode=should_simple,
        analyzed_at=datetime.now(timezone.utc),
    )
