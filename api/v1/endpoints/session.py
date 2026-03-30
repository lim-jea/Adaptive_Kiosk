from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.session import create_session, get_session_by_uuid, end_session_by_uuid
from schemas.session import SessionGetRequest, SessionEndRequest, SessionResponse
from models.kiosk import Kiosk
from api.v1.endpoints.kiosk import get_current_kiosk

router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post("", response_model=SessionResponse)
async def start_session(
    kiosk: Kiosk = Depends(get_current_kiosk),
    db: AsyncSession = Depends(get_db),
):
    """세션 시작. X-API-Key 헤더 필수."""
    return await create_session(db, kiosk_id=kiosk.id)


@router.get("/{session_uuid}", response_model=SessionResponse)
async def read_session(
    req: SessionGetRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """세션 상태 조회."""
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_uuid}/end", response_model=SessionResponse)
async def close_session(
    session_uuid: str,
    req: SessionEndRequest,
    db: AsyncSession = Depends(get_db),
):
    """세션 종료. reason: completed / timeout / cancelled"""
    session = await end_session_by_uuid(db, session_uuid, reason=req.reason)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
