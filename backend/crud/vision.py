from sqlalchemy.ext.asyncio import AsyncSession

from models.vision_event import VisionEvent
from schemas.vision import VisionEventCreate


async def create_vision_event(db: AsyncSession, session_id: int, data: VisionEventCreate) -> VisionEvent:
    event = VisionEvent(session_id=session_id, **data.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
