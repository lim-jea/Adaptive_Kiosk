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


async def get_session(db: AsyncSession, session_id: int) -> Optional[KioskSession]:
    result = await db.execute(select(KioskSession).where(KioskSession.id == session_id))
    return result.scalar_one_or_none()


async def update_session(db: AsyncSession, session_id: int, data: SessionUpdate) -> Optional[KioskSession]:
    session = await get_session(db, session_id)
    if not session:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


async def end_session(db: AsyncSession, session_id: int) -> Optional[KioskSession]:
    session = await get_session(db, session_id)
    if not session:
        return None
    session.ended_at = datetime.now(timezone.utc)
    session.status = "ended"
    await db.commit()
    await db.refresh(session)
    return session
