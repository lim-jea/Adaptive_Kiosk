import secrets
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.kiosk import Kiosk


def _generate_api_key() -> str:
    """32바이트 hex API 키 생성 (64자)"""
    return secrets.token_hex(32)


async def register_kiosk(db: AsyncSession, name: str, location: Optional[str] = None) -> Kiosk:
    """새 키오스크를 등록하고 API 키를 발급합니다."""
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


async def get_all_kiosks(db: AsyncSession) -> List[Kiosk]:
    result = await db.execute(select(Kiosk))
    return list(result.scalars().all())


async def update_last_seen(db: AsyncSession, kiosk: Kiosk) -> None:
    """키오스크의 마지막 통신 시각을 갱신합니다."""
    kiosk.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
