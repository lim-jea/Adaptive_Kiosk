from datetime import datetime, timezone
from typing import Optional, List, Union
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


async def get_session(
    db: AsyncSession,
    session_uuid: Optional[str] = None,
    session_id: Optional[int] = None,
    active_only: bool = True,
    as_list: bool = False,
) -> Union[Optional[KioskSession], List[KioskSession]]:
    """
    세션 조회.
    - session_uuid 지정 시: UUID로 단건 조회
    - session_id 지정 시: 내부 ID로 단건 조회
    - 둘 다 미지정 + as_list=True: 목록 조회
    """
    query = select(KioskSession)

    if session_uuid is not None:
        query = query.where(KioskSession.session_uuid == session_uuid)
    elif session_id is not None:
        query = query.where(KioskSession.id == session_id)
    elif not as_list:
        # 단건 조회(as_list=False) + UUID 미지정이면 최신 세션 1건 조회
        query = query.order_by(KioskSession.started_at.desc()).limit(1)

    status_filter = (KioskSession.status == "active") if active_only else True
    query = query.where(status_filter)

    result = await db.execute(query)
    if as_list:
        return result.scalars().all()
    return result.scalar_one_or_none()

async def get_session_list(db: AsyncSession) -> List[KioskSession]:
    """내부용 (FK 참조 등). 외부 API는 get_session 사용."""
    sessions = await get_session(db, session_uuid=None, active_only=False, as_list=True)
    return sessions if isinstance(sessions, list) else []
    
async def update_session_by_uuid(db: AsyncSession, session_uuid: str, data: SessionUpdate) -> Optional[KioskSession]:
    session = await get_session(db, session_uuid=session_uuid)
    if not session:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


async def end_session_by_uuid(db: AsyncSession, session_uuid: str, reason: str = "completed") -> Optional[KioskSession]:
    session = await get_session(db, session_uuid=session_uuid)
    if not session:
        return None
    session.ended_at = datetime.now(timezone.utc)
    session.end_reason = reason
    session.status = "ended"
    await db.commit()
    await db.refresh(session)
    return session
