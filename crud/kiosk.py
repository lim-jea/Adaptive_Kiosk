import secrets
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.kiosk import Kiosk


def _generate_api_key() -> str:
    return secrets.token_hex(32)


async def register_kiosk(db: AsyncSession, name: str, location: Optional[str] = None) -> Kiosk:
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


async def get_kiosk_by_name(db: AsyncSession, name: str) -> Optional[Kiosk]:
    result = await db.execute(select(Kiosk).where(Kiosk.name == name))
    return result.scalar_one_or_none()


async def get_all_kiosks(db: AsyncSession) -> List[Kiosk]:
    result = await db.execute(select(Kiosk))
    return list(result.scalars().all())


async def update_last_seen(db: AsyncSession, kiosk: Kiosk) -> None:
    kiosk.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
