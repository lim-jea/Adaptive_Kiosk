from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.recommendation_event import RecommendationEvent


async def create_recommendation_events(
    db: AsyncSession,
    session_id: int,
    preferred_category: str,
    recommendations: List[dict],
) -> List[RecommendationEvent]:
    """추천 결과를 이벤트로 저장"""
    events = []
    for rec in recommendations:
        event = RecommendationEvent(
            session_id=session_id,
            preferred_category=preferred_category,
            recommendation_type=rec["recommendation_type"],
            recommended_menu_id=rec["menu_id"],
        )
        db.add(event)
        events.append(event)
    await db.commit()
    for event in events:
        await db.refresh(event)
    return events


async def mark_clicked(db: AsyncSession, event_id: int) -> None:
    result = await db.execute(
        select(RecommendationEvent).where(RecommendationEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event:
        event.was_clicked = True
        await db.commit()


async def mark_led_to_order(db: AsyncSession, event_id: int) -> None:
    result = await db.execute(
        select(RecommendationEvent).where(RecommendationEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event:
        event.led_to_order = True
        await db.commit()
