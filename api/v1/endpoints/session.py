from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.session import create_session, get_session, update_session, end_session
from schemas.session import SessionUpdate, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post("", response_model=SessionResponse)
async def start_session(db: AsyncSession = Depends(get_db)):
    """새 키오스크 세션을 시작합니다 (사용자가 카메라 앞에 접근 시)."""
    return await create_session(db)


@router.get("/{session_id}", response_model=SessionResponse)
async def read_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """세션 상태를 조회합니다."""
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def patch_session(session_id: int, data: SessionUpdate, db: AsyncSession = Depends(get_db)):
    """세션 상태를 업데이트합니다 (간편모드 전환 등)."""
    session = await update_session(db, session_id, data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/end", response_model=SessionResponse)
async def close_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """세션을 종료합니다."""
    session = await end_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
