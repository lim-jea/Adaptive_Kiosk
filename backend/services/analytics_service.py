from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import Column, case, func, literal, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from model import (
    Cart,
    KioskSession,
    Menu,
    Order,
    OrderItem,
    RecommendationEvent,
)
from schemas import (
    CategoryBreakdownItem,
    DemographicsCell,
    FunnelResponse,
    HourOfDayPoint,
    MenuRankingItem,
    OptionUsageItem,
    OrderAnalytics,
    RecommendationAnalytics,
    RecommendationBreakdownItem,
    RecommendationFunnel,
    SessionAnalytics,
    SessionDurationStats,
    TimeseriesBucket,
)


Bucket = Literal["hour", "day"]

# DB는 UTC 저장이라는 가정. 모든 시간대 그루핑/HOUR()는 KST로 보정한다.
DISPLAY_TZ_OFFSET = "+09:00"


def _to_display_tz(column: Column):
    """UTC 저장 컬럼을 KST(+9h) wall-clock으로 시프트.
    CONVERT_TZ 대신 DATE_ADD(INTERVAL 9 HOUR)를 사용 — 타임존 테이블 의존 제거,
    한국은 DST가 없어 항상 +9 고정이라 의미상 동등."""
    return func.date_add(column, text("INTERVAL 9 HOUR"))


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


# ============================================================================
# Time series / breakdowns
# ============================================================================


def _truncate(column: Column, bucket: Bucket):
    """KST 보정 후 시간 버킷 절단. 결과는 KST wall-clock 문자열."""
    converted = _to_display_tz(column)
    if bucket == "hour":
        return func.date_format(converted, literal("%Y-%m-%d %H:00:00"))
    return func.date_format(converted, literal("%Y-%m-%d 00:00:00"))


def _parse_bucket_value(raw) -> datetime:
    """`_truncate` 결과 문자열(KST wall-clock)을 KST aware datetime으로 환원."""
    text = str(raw).replace(" ", "T")
    return datetime.fromisoformat(f"{text}+09:00")


async def get_orders_timeseries(
    db: AsyncSession,
    *,
    bucket: Bucket = "day",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[TimeseriesBucket]:
    bucket_col = _truncate(Order.created_at, bucket).label("b")
    query = _apply_order_filters(
        select(
            bucket_col,
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
        ).group_by(bucket_col).order_by(bucket_col),
        start_date, end_date, kiosk_id,
    )
    rows = (await db.execute(query)).all()
    return [
        TimeseriesBucket(
            bucket=_parse_bucket_value(r.b),
            orders=int(r.orders or 0),
            revenue=int(r.revenue or 0),
        )
        for r in rows
    ]


async def get_sessions_timeseries(
    db: AsyncSession,
    *,
    bucket: Bucket = "day",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[TimeseriesBucket]:
    bucket_col = _truncate(KioskSession.started_at, bucket).label("b")
    simple_expr = func.sum(case((KioskSession.is_simple_mode == True, 1), else_=0))
    help_expr = func.sum(case((KioskSession.help_triggered == True, 1), else_=0))
    query = _apply_session_filters(
        select(
            bucket_col,
            func.count(KioskSession.id).label("sessions"),
            simple_expr.label("simple"),
            help_expr.label("help_count"),
        ).group_by(bucket_col).order_by(bucket_col),
        start_date, end_date, kiosk_id,
    )
    rows = (await db.execute(query)).all()
    return [
        TimeseriesBucket(
            bucket=_parse_bucket_value(r.b),
            sessions=int(r.sessions or 0),
            simple_mode_sessions=int(r.simple or 0),
            help_triggered=int(r.help_count or 0),
        )
        for r in rows
    ]


async def get_orders_by_hour_of_day(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[HourOfDayPoint]:
    hour_col = func.hour(_to_display_tz(Order.created_at)).label("h")
    query = _apply_order_filters(
        select(
            hour_col,
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
        ).group_by(hour_col).order_by(hour_col),
        start_date, end_date, kiosk_id,
    )
    rows = (await db.execute(query)).all()
    by_hour = {int(r.h): (int(r.orders), int(r.revenue or 0)) for r in rows}

    sess_hour_col = func.hour(_to_display_tz(KioskSession.started_at)).label("h")
    sess_q = _apply_session_filters(
        select(sess_hour_col, func.count(KioskSession.id).label("sessions"))
        .group_by(sess_hour_col),
        start_date, end_date, kiosk_id,
    )
    sess_rows = (await db.execute(sess_q)).all()
    sess_by_hour = {int(r.h): int(r.sessions) for r in sess_rows}

    return [
        HourOfDayPoint(
            hour=h,
            orders=by_hour.get(h, (0, 0))[0],
            revenue=by_hour.get(h, (0, 0))[1],
            sessions=sess_by_hour.get(h, 0),
        )
        for h in range(24)
    ]


async def get_menu_rankings(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
    limit: int = 10,
) -> list[MenuRankingItem]:
    qty_col = func.coalesce(func.sum(OrderItem.quantity), 0).label("qty")
    rev_col = func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label("rev")
    query = (
        select(
            OrderItem.menu_id,
            func.coalesce(OrderItem.menu_name_snapshot, Menu.name).label("name"),
            qty_col,
            rev_col,
        )
        .join(Order, Order.id == OrderItem.order_id)
        .outerjoin(Menu, Menu.id == OrderItem.menu_id)
    )
    query = _apply_order_filters(query, start_date, end_date, kiosk_id)
    query = query.group_by(OrderItem.menu_id, OrderItem.menu_name_snapshot, Menu.name) \
        .order_by(qty_col.desc()).limit(limit)
    rows = (await db.execute(query)).all()
    return [
        MenuRankingItem(menu_id=r.menu_id, name=r.name or "(unknown)", quantity=int(r.qty), revenue=int(r.rev))
        for r in rows
    ]


async def get_category_breakdown(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[CategoryBreakdownItem]:
    qty_col = func.coalesce(func.sum(OrderItem.quantity), 0).label("qty")
    rev_col = func.coalesce(func.sum(OrderItem.unit_price * OrderItem.quantity), 0).label("rev")
    query = (
        select(Menu.category.label("category"), qty_col, rev_col)
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Menu, Menu.id == OrderItem.menu_id)
    )
    query = _apply_order_filters(query, start_date, end_date, kiosk_id)
    query = query.group_by(Menu.category)
    rows = (await db.execute(query)).all()

    total_rev = sum(int(r.rev or 0) for r in rows) or 1
    return [
        CategoryBreakdownItem(
            category=r.category or "기타",
            quantity=int(r.qty or 0),
            revenue=int(r.rev or 0),
            share=round(int(r.rev or 0) / total_rev, 4),
        )
        for r in rows
    ]


async def get_option_usage(
    db: AsyncSession,
    *,
    menu_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[OptionUsageItem]:
    """selected_options_json을 Python 측에서 집계 (DB 종속성 최소화)."""
    query = (
        select(OrderItem.selected_options_json)
        .join(Order, Order.id == OrderItem.order_id)
    )
    query = _apply_order_filters(query, start_date, end_date, kiosk_id)
    if menu_id is not None:
        query = query.where(OrderItem.menu_id == menu_id)

    rows = (await db.execute(query)).all()
    counter: dict[tuple[str, str], int] = {}
    group_totals: dict[str, int] = {}
    for (raw,) in rows:
        if not raw:
            continue
        for opt in raw:
            group = (opt.get("group_name") or opt.get("group") or "기타").strip()
            name = (opt.get("option_name") or opt.get("name") or "").strip()
            if not name:
                continue
            key = (group, name)
            counter[key] = counter.get(key, 0) + 1
            group_totals[group] = group_totals.get(group, 0) + 1

    items = []
    for (group, name), cnt in counter.items():
        share = round(cnt / group_totals[group], 4) if group_totals.get(group) else 0.0
        items.append(OptionUsageItem(group_name=group, option_name=name, count=cnt, share=share))
    items.sort(key=lambda x: (x.group_name, -x.count))
    return items


async def get_demographics_breakdown(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[DemographicsCell]:
    sess_q = _apply_session_filters(
        select(
            KioskSession.estimated_age_group.label("age"),
            KioskSession.estimated_gender.label("gender"),
            func.count(KioskSession.id).label("sessions"),
        ).group_by(KioskSession.estimated_age_group, KioskSession.estimated_gender),
        start_date, end_date, kiosk_id,
    )
    sess_rows = (await db.execute(sess_q)).all()

    order_q = (
        select(
            KioskSession.estimated_age_group.label("age"),
            KioskSession.estimated_gender.label("gender"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
        )
        .select_from(Order)
        .join(KioskSession, KioskSession.id == Order.session_id)
        .group_by(KioskSession.estimated_age_group, KioskSession.estimated_gender)
    )
    order_q = _apply_order_filters(order_q, start_date, end_date, kiosk_id)
    order_rows = (await db.execute(order_q)).all()
    order_map = {(r.age, r.gender): (int(r.orders), int(r.revenue or 0)) for r in order_rows}

    cells = []
    for r in sess_rows:
        orders, revenue = order_map.get((r.age, r.gender), (0, 0))
        cells.append(DemographicsCell(
            age_group=r.age, gender=r.gender,
            sessions=int(r.sessions), orders=orders, revenue=revenue,
        ))
    return cells


async def get_session_duration(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> SessionDurationStats:
    """완료된 세션의 평균 체류시간(초) 및 연령대별 분해."""
    # TIMESTAMPDIFF의 첫 인자는 따옴표 없는 키워드여야 한다. text() 사용.
    duration_sec = func.timestampdiff(text("SECOND"), KioskSession.started_at, KioskSession.ended_at)

    avg_q = _apply_session_filters(
        select(func.avg(duration_sec)).where(KioskSession.ended_at.isnot(None)),
        start_date, end_date, kiosk_id,
    )
    count_q = _apply_session_filters(
        select(func.count(KioskSession.id)).where(KioskSession.ended_at.isnot(None)),
        start_date, end_date, kiosk_id,
    )
    by_age_q = _apply_session_filters(
        select(
            KioskSession.estimated_age_group.label("age"),
            func.avg(duration_sec).label("avg"),
            func.count(KioskSession.id).label("cnt"),
        )
        .where(KioskSession.ended_at.isnot(None))
        .group_by(KioskSession.estimated_age_group),
        start_date, end_date, kiosk_id,
    )

    avg_value = (await db.execute(avg_q)).scalar()
    sample = (await db.execute(count_q)).scalar() or 0
    by_age_rows = (await db.execute(by_age_q)).all()

    return SessionDurationStats(
        sample=int(sample),
        avg_seconds=round(float(avg_value), 1) if avg_value is not None else 0.0,
        by_age_group=[
            {
                "age_group": r.age,
                "avg_seconds": round(float(r.avg), 1) if r.avg is not None else 0.0,
                "sample": int(r.cnt),
            }
            for r in by_age_rows
        ],
    )


async def get_session_funnel(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> FunnelResponse:
    sess_q = _apply_session_filters(
        select(func.count(KioskSession.id)), start_date, end_date, kiosk_id,
    )
    cart_q = _apply_session_filters(
        select(func.count(func.distinct(Cart.session_id)))
        .select_from(Cart).join(KioskSession, KioskSession.id == Cart.session_id),
        start_date, end_date, kiosk_id,
    )
    order_q = _apply_session_filters(
        select(func.count(func.distinct(Order.session_id)))
        .select_from(Order).join(KioskSession, KioskSession.id == Order.session_id),
        start_date, end_date, kiosk_id,
    )
    sessions = (await db.execute(sess_q)).scalar() or 0
    with_cart = (await db.execute(cart_q)).scalar() or 0
    with_order = (await db.execute(order_q)).scalar() or 0
    return FunnelResponse(
        sessions=sessions,
        sessions_with_cart=with_cart,
        sessions_with_order=with_order,
        cart_conversion=round(with_cart / sessions, 4) if sessions else 0.0,
        order_conversion=round(with_order / sessions, 4) if sessions else 0.0,
    )


# ============================================================================
# Recommendation breakdowns
# ============================================================================


def _apply_rec_filters(query, start_date, end_date, kiosk_id):
    if start_date:
        query = query.where(RecommendationEvent.created_at >= start_date)
    if end_date:
        query = query.where(RecommendationEvent.created_at < end_date)
    if kiosk_id:
        query = query.join(
            KioskSession, RecommendationEvent.session_id == KioskSession.id
        ).where(KioskSession.kiosk_id == kiosk_id)
    return query


async def get_recommendation_funnel(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> RecommendationFunnel:
    base = _apply_rec_filters(select(RecommendationEvent.id), start_date, end_date, kiosk_id)
    shown = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    clicked_q = _apply_rec_filters(
        select(RecommendationEvent.id).where(RecommendationEvent.was_clicked == True),
        start_date, end_date, kiosk_id,
    )
    clicked = (await db.execute(select(func.count()).select_from(clicked_q.subquery()))).scalar() or 0

    led_q = _apply_rec_filters(
        select(RecommendationEvent.id).where(RecommendationEvent.led_to_order == True),
        start_date, end_date, kiosk_id,
    )
    led = (await db.execute(select(func.count()).select_from(led_q.subquery()))).scalar() or 0

    return RecommendationFunnel(
        shown=shown, clicked=clicked, led_to_order=led,
        ctr=round(clicked / shown, 4) if shown else 0.0,
        cvr=round(led / shown, 4) if shown else 0.0,
    )


_REC_BREAKDOWN_COLUMNS = {
    "preferred_category": RecommendationEvent.preferred_category,
    "recommendation_type": RecommendationEvent.recommendation_type,
}


async def get_recommendation_breakdown(
    db: AsyncSession,
    *,
    by: Literal["preferred_category", "recommendation_type"],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> list[RecommendationBreakdownItem]:
    column = _REC_BREAKDOWN_COLUMNS.get(by)
    if column is None:
        raise ValueError(f"Unsupported breakdown key: {by}")
    key_col = column.label("k")
    clicked_expr = func.sum(case((RecommendationEvent.was_clicked == True, 1), else_=0))
    led_expr = func.sum(case((RecommendationEvent.led_to_order == True, 1), else_=0))
    query = _apply_rec_filters(
        select(
            key_col,
            func.count(RecommendationEvent.id).label("shown"),
            clicked_expr.label("clicked"),
            led_expr.label("led"),
        ).group_by(key_col),
        start_date, end_date, kiosk_id,
    )
    rows = (await db.execute(query)).all()
    items = []
    for r in rows:
        shown = int(r.shown or 0)
        clicked = int(r.clicked or 0)
        led = int(r.led or 0)
        items.append(RecommendationBreakdownItem(
            key=str(r.k or "(unknown)"),
            shown=shown, clicked=clicked, led_to_order=led,
            ctr=round(clicked / shown, 4) if shown else 0.0,
            cvr=round(led / shown, 4) if shown else 0.0,
        ))
    items.sort(key=lambda x: -x.shown)
    return items
