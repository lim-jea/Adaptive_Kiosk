from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import KioskSession
from core.enums import SessionStatus


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


async def get_session_by_id(db: AsyncSession, session_id: int) -> Optional[KioskSession]:
    result = await db.execute(select(KioskSession).where(KioskSession.id == session_id))
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    status: Optional[SessionStatus] = None,
    kiosk_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[KioskSession], int]:
    base = select(KioskSession)
    count_q = select(func.count(KioskSession.id))

    if status:
        base = base.where(KioskSession.status == status.value)
        count_q = count_q.where(KioskSession.status == status.value)
    if kiosk_id:
        base = base.where(KioskSession.kiosk_id == kiosk_id)
        count_q = count_q.where(KioskSession.kiosk_id == kiosk_id)

    base = base.order_by(KioskSession.started_at.desc()).offset(skip).limit(limit)
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base)).scalars().all()
    return list(rows), total


async def update_session(
    db: AsyncSession,
    session_uuid: str,
    updates: dict,
) -> Optional[KioskSession]:
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        return None

    # status가 ended로 변경되면 자동으로 ended_at 설정
    if updates.get("status") == SessionStatus.ENDED.value or updates.get("status") == "ended":
        if not session.ended_at:
            session.ended_at = datetime.now(timezone.utc)

    for field, value in updates.items():
        if value is not None:
            setattr(session, field, value)

    await db.commit()
    await db.refresh(session)
    return session
