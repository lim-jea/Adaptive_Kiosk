from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from core.database import get_db
from crud.session import create_session, end_session_by_uuid, get_session
from schemas.session import SessionGetRequest, SessionEndRequest, SessionResponse, SessionListRequest
from models.kiosk import Kiosk
from api.v1.endpoints.kiosk import get_current_kiosk

router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post("/start", response_model=SessionResponse)
async def start_session(
    kiosk: Kiosk = Depends(get_current_kiosk),
    db: AsyncSession = Depends(get_db),
):
    """세션 시작. X-API-Key 헤더 필수."""
    return await create_session(db, kiosk_id=kiosk.id)


@router.get("/get", response_model=List[SessionResponse])
async def get_sessions(
    req: SessionListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_db),
):
    """전체 세션 목록. 관리자 인증 필요."""
    sessions = await get_session(db, active_only=req.active_only, as_list=req.as_list)
    return sessions if isinstance(sessions, list) else []


@router.get("/{session_uuid}", response_model=SessionResponse)
async def read_session(
    req: SessionGetRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """세션 상태 조회."""
    session = await get_session(db, session_uuid=req.session_uuid)
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
