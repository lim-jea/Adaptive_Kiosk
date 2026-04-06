import secrets
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.kiosk import Kiosk


def _generate_api_key() -> str:
    return secrets.token_hex(32)


async def create_kiosk(db: AsyncSession, name: str, location: Optional[str] = None) -> Kiosk:
    kiosk = Kiosk(
        name=name,
        location=location,
        api_key=_generate_api_key(),
    )
    db.add(kiosk)
    await db.commit()
    await db.refresh(kiosk)
    return kiosk


async def get_kiosk_by_api_key(db: AsyncSession, api_key: str) -> Optional[Kiosk]:
    result = await db.execute(select(Kiosk).where(Kiosk.api_key == api_key))
    return result.scalar_one_or_none()


async def get_kiosk_by_id(db: AsyncSession, kiosk_id: int) -> Optional[Kiosk]:
    result = await db.execute(select(Kiosk).where(Kiosk.id == kiosk_id))
    return result.scalar_one_or_none()


async def list_kiosks(
    db: AsyncSession,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[Kiosk], int]:
    base = select(Kiosk)
    count_q = select(func.count(Kiosk.id))
    if is_active is not None:
        base = base.where(Kiosk.is_active == is_active)
        count_q = count_q.where(Kiosk.is_active == is_active)
    base = base.order_by(Kiosk.id).offset(skip).limit(limit)
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base)).scalars().all()
    return list(rows), total


async def update_last_seen(db: AsyncSession, kiosk: Kiosk) -> None:
    kiosk.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
