from datetime import datetime
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import KioskSession
from models.recommendation_event import RecommendationEvent
from models.order import Order
from schemas.analytics import SessionAnalytics, RecommendationAnalytics, OrderAnalytics


def _apply_session_filters(query, start_date, end_date, kiosk_id):
    if start_date:
        query = query.where(KioskSession.started_at >= start_date)
    if end_date:
        query = query.where(KioskSession.started_at < end_date)
    if kiosk_id:
        query = query.where(KioskSession.kiosk_id == kiosk_id)
    return query


def _apply_order_filters(query, start_date, end_date, kiosk_id):
    if start_date:
        query = query.where(Order.created_at >= start_date)
    if end_date:
        query = query.where(Order.created_at < end_date)
    if kiosk_id:
        query = query.join(KioskSession, Order.session_id == KioskSession.id).where(
            KioskSession.kiosk_id == kiosk_id
        )
    return query


async def get_session_analytics(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> SessionAnalytics:
    total_q = _apply_session_filters(
        select(func.count(KioskSession.id)), start_date, end_date, kiosk_id
    )
    simple_q = _apply_session_filters(
        select(func.count(KioskSession.id)).where(KioskSession.is_simple_mode == True),
        start_date, end_date, kiosk_id,
    )
    help_q = _apply_session_filters(
        select(func.count(KioskSession.id)).where(KioskSession.help_triggered == True),
        start_date, end_date, kiosk_id,
    )

    total = (await db.execute(total_q)).scalar() or 0
    simple = (await db.execute(simple_q)).scalar() or 0
    help_count = (await db.execute(help_q)).scalar() or 0

    return SessionAnalytics(
        total_sessions=total,
        simple_mode_sessions=simple,
        simple_mode_rate=round(simple / total, 4) if total > 0 else 0.0,
        help_triggered_count=help_count,
    )


async def get_recommendation_analytics(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> RecommendationAnalytics:
    base = select(RecommendationEvent.id)
    if start_date:
        base = base.where(RecommendationEvent.created_at >= start_date)
    if end_date:
        base = base.where(RecommendationEvent.created_at < end_date)
    if kiosk_id:
        base = base.join(
            KioskSession, RecommendationEvent.session_id == KioskSession.id
        ).where(KioskSession.kiosk_id == kiosk_id)

    total_shown = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    clicked_q = base.where(RecommendationEvent.was_clicked == True)
    total_clicked = (await db.execute(select(func.count()).select_from(clicked_q.subquery()))).scalar() or 0
    led_q = base.where(RecommendationEvent.led_to_order == True)
    led_to_order = (await db.execute(select(func.count()).select_from(led_q.subquery()))).scalar() or 0

    return RecommendationAnalytics(
        total_shown=total_shown,
        total_clicked=total_clicked,
        click_through_rate=round(total_clicked / total_shown, 4) if total_shown > 0 else 0.0,
        led_to_order_count=led_to_order,
        order_conversion_rate=round(led_to_order / total_shown, 4) if total_shown > 0 else 0.0,
    )


async def get_order_analytics(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> OrderAnalytics:
    total_q = _apply_order_filters(select(func.count(Order.id)), start_date, end_date, kiosk_id)
    revenue_q = _apply_order_filters(
        select(func.coalesce(func.sum(Order.total_price), 0)), start_date, end_date, kiosk_id
    )
    avg_q = _apply_order_filters(select(func.avg(Order.total_price)), start_date, end_date, kiosk_id)
    rec_q = _apply_order_filters(
        select(func.count(Order.id)).where(Order.used_recommendation == True),
        start_date, end_date, kiosk_id,
    )

    total = (await db.execute(total_q)).scalar() or 0
    revenue = (await db.execute(revenue_q)).scalar() or 0
    avg_price = (await db.execute(avg_q)).scalar() or 0.0
    rec_used = (await db.execute(rec_q)).scalar() or 0

    return OrderAnalytics(
        total_orders=total,
        total_revenue=int(revenue),
        avg_order_price=round(float(avg_price), 0),
        recommendation_used_count=rec_used,
        recommendation_used_rate=round(rec_used / total, 4) if total > 0 else 0.0,
    )
