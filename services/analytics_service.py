from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import KioskSession
from models.recommendation_event import RecommendationEvent
from models.order import Order
from schemas.analytics import SessionAnalytics, RecommendationAnalytics, OrderAnalytics


async def get_session_analytics(db: AsyncSession) -> SessionAnalytics:
    total = (await db.execute(select(func.count(KioskSession.id)))).scalar() or 0
    simple = (await db.execute(
        select(func.count(KioskSession.id)).where(KioskSession.is_simple_mode == True)
    )).scalar() or 0
    help_count = (await db.execute(
        select(func.count(KioskSession.id)).where(KioskSession.help_triggered == True)
    )).scalar() or 0

    return SessionAnalytics(
        total_sessions=total,
        simple_mode_sessions=simple,
        simple_mode_rate=round(simple / total, 4) if total > 0 else 0.0,
        help_triggered_count=help_count,
    )


async def get_recommendation_analytics(db: AsyncSession) -> RecommendationAnalytics:
    total_shown = (await db.execute(
        select(func.count(RecommendationEvent.id))
    )).scalar() or 0
    total_clicked = (await db.execute(
        select(func.count(RecommendationEvent.id)).where(RecommendationEvent.was_clicked == True)
    )).scalar() or 0
    led_to_order = (await db.execute(
        select(func.count(RecommendationEvent.id)).where(RecommendationEvent.led_to_order == True)
    )).scalar() or 0

    return RecommendationAnalytics(
        total_shown=total_shown,
        total_clicked=total_clicked,
        click_through_rate=round(total_clicked / total_shown, 4) if total_shown > 0 else 0.0,
        led_to_order_count=led_to_order,
        order_conversion_rate=round(led_to_order / total_shown, 4) if total_shown > 0 else 0.0,
    )


async def get_order_analytics(db: AsyncSession) -> OrderAnalytics:
    total = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    avg_time = (await db.execute(
        select(func.avg(Order.total_time_seconds)).where(Order.total_time_seconds.isnot(None))
    )).scalar() or 0.0
    rec_used = (await db.execute(
        select(func.count(Order.id)).where(Order.used_recommendation == True)
    )).scalar() or 0

    return OrderAnalytics(
        total_orders=total,
        avg_order_time_seconds=round(float(avg_time), 2),
        recommendation_used_count=rec_used,
        recommendation_used_rate=round(rec_used / total, 4) if total > 0 else 0.0,
    )
