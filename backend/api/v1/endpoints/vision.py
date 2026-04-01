from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.vision import create_vision_event
from crud.session import get_session, update_session
from schemas.vision import VisionEventCreate, SimpleModeDecision
from schemas.session import SessionUpdate
from services.vision_service import should_use_simple_mode

router = APIRouter(prefix="/vision", tags=["Vision"])


@router.post("/{session_id}", response_model=SimpleModeDecision)
async def receive_vision_result(
    session_id: int,
    data: VisionEventCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    비전 모듈의 분석 결과를 수신하고 저장합니다.
    간편모드 전환 여부를 판단하여 세션을 업데이트하고, 결과를 반환합니다.
    """
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await create_vision_event(db, session_id, data)

    simple_mode = should_use_simple_mode(data)

    await update_session(db, session_id, SessionUpdate(
        is_simple_mode=simple_mode,
        estimated_age_group=data.estimated_age_group,
        estimated_gender=data.estimated_gender,
    ))

    return SimpleModeDecision(
        should_use_simple_mode=simple_mode,
        estimated_age_group=data.estimated_age_group,
        estimated_gender=data.estimated_gender,
    )
