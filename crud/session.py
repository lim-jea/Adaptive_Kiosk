from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import KioskSession
from schemas.session import SessionUpdate


async def create_session(db: AsyncSession, kiosk_id: int) -> KioskSession:
    session = KioskSession(kiosk_id=kiosk_id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_uuid(db: AsyncSession, session_uuid: str) -> Optional[KioskSession]:
    result = await db.execute(
        select(KioskSession).where(KioskSession.session_uuid == session_uuid)
    )
    return result.scalar_one_or_none()


async def get_session(db: AsyncSession, session_id: int) -> Optional[KioskSession]:
    """내부용 (FK 참조 등). 외부 API는 get_session_by_uuid 사용."""
    result = await db.execute(select(KioskSession).where(KioskSession.id == session_id))
    return result.scalar_one_or_none()


async def update_session_by_uuid(db: AsyncSession, session_uuid: str, data: SessionUpdate) -> Optional[KioskSession]:
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


async def end_session_by_uuid(db: AsyncSession, session_uuid: str, reason: str = "completed") -> Optional[KioskSession]:
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        return None
    session.ended_at = datetime.now(timezone.utc)
    session.end_reason = reason
    session.status = "ended"
    await db.commit()
    await db.refresh(session)
    return session
