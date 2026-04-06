from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.session import create_session, get_session_by_uuid, list_sessions, update_session
from schemas.session import SessionListRequest, SessionUpdateRequest, SessionResponse
from schemas.common import PaginatedResponse, make_error
from models.kiosk import Kiosk
from api.v1.endpoints.kiosk import get_current_kiosk

router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session_endpoint(
    kiosk: Kiosk = Depends(get_current_kiosk),
    db: AsyncSession = Depends(get_db),
):
    """세션 생성. X-API-Key 헤더 필수."""
    return await create_session(db, kiosk_id=kiosk.id)


@router.get("", response_model=PaginatedResponse[SessionResponse])
async def list_sessions_endpoint(
    req: SessionListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """세션 목록. 관리자 인증 필요."""
    items, total = await list_sessions(
        db, status=req.status, kiosk_id=req.kiosk_id, skip=req.skip, limit=req.limit
    )
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.get("/{session_uuid}", response_model=SessionResponse)
async def read_session(session_uuid: str, db: AsyncSession = Depends(get_db)):
    """세션 단건 조회."""
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
    return session


@router.patch("/{session_uuid}", response_model=SessionResponse)
async def update_session_endpoint(
    session_uuid: str,
    req: SessionUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """세션 상태 갱신.
    종료: { "status": "ended", "end_reason": "completed" }
    간편모드 전환: { "is_simple_mode": true, "estimated_age_group": "60대" }
    """
    updates = req.model_dump(exclude_unset=True, exclude_none=True)
    # enum → str 변환
    if "status" in updates and hasattr(updates["status"], "value"):
        updates["status"] = updates["status"].value
    if "end_reason" in updates and hasattr(updates["end_reason"], "value"):
        updates["end_reason"] = updates["end_reason"].value

    session = await update_session(db, session_uuid, updates)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=session_uuid),
        )
    return session
