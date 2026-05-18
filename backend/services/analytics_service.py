from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Literal, Optional

from sqlalchemy import Column, case, func, literal, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from model import (
    Cart,
    ChatMessage,
    KioskSession,
    Menu,
    Order,
    OrderItem,
    RecommendationEvent,
    SessionActivityLog,
    SurveyResponse,
    VisionEvent,
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
    UsabilityAbandonStep,
    UsabilityAgeRow,
    UsabilityAnalyticsResponse,
    UsabilityDurationBucket,
    UsabilityFunnelStep,
    UsabilityInsight,
    UsabilityMenuFrictionItem,
    UsabilityMetricCard,
    UsabilitySessionRow,
    UsabilitySessionTimelineResponse,
    UsabilityTimelineEvent,
    UsabilityVoiceStats,
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


# ============================================================================
# Usability analytics from activity logs
# ============================================================================


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    if (start.tzinfo is None) != (end.tzinfo is None):
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)
    return max(0.0, (end - start).total_seconds())


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _median(values: list[float]) -> float:
    return round(float(median(values)), 1) if values else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _bucket_seconds(value: float | None) -> str | None:
    if value is None:
        return None
    if value < 15:
        return "0-15s"
    if value < 30:
        return "15-30s"
    if value < 60:
        return "30-60s"
    if value < 120:
        return "1-2m"
    if value < 300:
        return "2-5m"
    return "5m+"


_DURATION_BUCKET_ORDER = ["0-15s", "15-30s", "30-60s", "1-2m", "2-5m", "5m+"]


def _duration_buckets(values: list[float]) -> list[UsabilityDurationBucket]:
    counts = Counter(_bucket_seconds(v) for v in values)
    return [
        UsabilityDurationBucket(label=label, count=int(counts.get(label, 0)))
        for label in _DURATION_BUCKET_ORDER
    ]


def _is_menu_click(log: SessionActivityLog) -> bool:
    return (
        log.target_type == "menu"
        and log.action_name in {"menu_click", "recommendation_click"}
    )


def _is_cart_add(log: SessionActivityLog) -> bool:
    return log.action_name == "cart_add"


def _is_payment_start(log: SessionActivityLog) -> bool:
    return log.action_name in {"payment_start", "payment_method_select"}


_SCREEN_LABELS = {
    "landing": "시작",
    "camera": "카메라",
    "analyzing": "얼굴 분석",
    "result": "분석 결과",
    "kiosk": "메뉴",
    "child_kiosk": "어린이 메뉴",
    "cart_review": "장바구니 확인",
    "discount": "할인",
    "payment": "결제",
    "child_payment": "어린이 결제",
    "completion": "완료",
    "child_complete": "어린이 완료",
    "survey": "설문",
}

_ACTION_LABELS = {
    "enter": "화면 진입",
    "exit": "화면 이탈",
    "session_start": "세션 시작",
    "age_group_select": "연령대 선택",
    "face_recognition_click": "얼굴 인식 선택",
    "face_analysis_start": "얼굴 분석 시작",
    "face_analysis_complete": "얼굴 분석 완료",
    "face_analysis_error": "얼굴 분석 실패",
    "category_tab_click": "카테고리 선택",
    "menu_click": "메뉴 선택",
    "recommendation_click": "추천 메뉴 선택",
    "option_select": "옵션 선택",
    "option_deselect": "옵션 해제",
    "option_confirm": "옵션 확정",
    "menu_detail_close": "메뉴 상세 닫기",
    "cart_add": "장바구니 추가",
    "cart_remove": "장바구니 제거",
    "cart_qty_change": "장바구니 수량 변경",
    "go_to_payment": "결제 이동",
    "payment_method_select": "결제수단 선택",
    "payment_start": "결제 시작",
    "order_submit_success": "주문 성공",
    "order_submit_error": "주문 실패",
    "session_complete": "세션 완료",
    "voice_action_applied": "음성 동작 적용",
    "voice_action_failed": "음성 동작 실패",
    "transcript_submitted": "음성 발화 제출",
    "response_received": "음성 응답 수신",
}


def _screen_label(value: str | None) -> str | None:
    return _SCREEN_LABELS.get(value or "", value)


def _action_label(value: str | None) -> str:
    if not value:
        return "-"
    return _ACTION_LABELS.get(value, value)


def _log_summary(log: SessionActivityLog) -> str:
    action = _action_label(log.action_name)
    target = log.target_label or log.target_id
    screen = _screen_label(log.screen_name)
    if log.action_name == "enter":
        return f"{screen or '화면'}에 진입했습니다."
    if log.action_name == "exit":
        if log.duration_ms is not None:
            return f"{screen or '화면'}에서 {round(log.duration_ms / 1000, 1)}초 머문 뒤 이탈했습니다."
        return f"{screen or '화면'}에서 이탈했습니다."
    if target:
        return f"{action}: {target}"
    return action


async def get_usability_session_timeline(
    db: AsyncSession,
    *,
    session_uuid: str,
) -> UsabilitySessionTimelineResponse | None:
    session = (
        await db.execute(select(KioskSession).where(KioskSession.session_uuid == session_uuid))
    ).scalar_one_or_none()
    if not session:
        return None

    logs = list(
        (await db.execute(
            select(SessionActivityLog)
            .where(SessionActivityLog.session_id == session.id)
            .order_by(SessionActivityLog.occurred_at, SessionActivityLog.seq)
        )).scalars().all()
    )
    first_order = (
        await db.execute(
            select(Order).where(Order.session_id == session.id).order_by(Order.created_at)
        )
    ).scalars().first()
    chat_messages = list(
        (await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
        )).scalars().all()
    )

    first_menu_click = next((log for log in logs if _is_menu_click(log)), None)
    kiosk_enter = next(
        (
            log.occurred_at
            for log in logs
            if log.event_type == "screen"
            and log.action_name == "enter"
            and log.screen_name in {"kiosk", "child_kiosk"}
        ),
        None,
    )
    total_seconds = _seconds_between(session.started_at, first_order.created_at if first_order else session.ended_at)
    select_seconds = _seconds_between(kiosk_enter, first_menu_click.occurred_at) if kiosk_enter and first_menu_click else None
    has_voice = bool(chat_messages) or any(log.event_type == "voice" or log.source == "voice" for log in logs)
    last_log = logs[-1] if logs else None

    session_row = UsabilitySessionRow(
        session_uuid=session.session_uuid,
        started_at=session.started_at,
        age_group=session.estimated_age_group,
        gender=session.estimated_gender,
        completed=first_order is not None,
        total_seconds=round(total_seconds, 1) if first_order and total_seconds is not None else None,
        first_menu_select_seconds=round(select_seconds, 1) if select_seconds is not None else None,
        voice_used=has_voice,
        last_screen_name=last_log.screen_name if last_log else None,
        last_action_name=last_log.action_name if last_log else None,
        event_count=len(logs),
    )

    events: list[UsabilityTimelineEvent] = []
    for log in logs:
        elapsed = _seconds_between(session.started_at, log.occurred_at)
        events.append(UsabilityTimelineEvent(
            occurred_at=log.occurred_at,
            elapsed_ms=round(elapsed * 1000) if elapsed is not None else None,
            event_type=log.event_type,
            screen_name=log.screen_name,
            screen_label=_screen_label(log.screen_name),
            action_name=log.action_name,
            action_label=_action_label(log.action_name),
            target_type=log.target_type,
            target_id=log.target_id,
            target_label=log.target_label,
            source=log.source,
            duration_ms=log.duration_ms,
            summary=_log_summary(log),
            payload_json=log.payload_json,
        ))

    for message in chat_messages:
        elapsed = _seconds_between(session.started_at, message.created_at)
        speaker = "사용자" if message.role == "user" else "AI"
        events.append(UsabilityTimelineEvent(
            occurred_at=message.created_at,
            elapsed_ms=round(elapsed * 1000) if elapsed is not None else None,
            event_type="voice_message",
            screen_name=None,
            screen_label="음성 대화",
            action_name=f"voice_{message.role}",
            action_label=f"음성 {speaker} 발화",
            target_type=None,
            target_id=None,
            target_label=None,
            source="voice",
            duration_ms=None,
            summary=f"{speaker}: {message.content}",
            payload_json={
                "intent": message.intent,
                "matched_by": message.matched_by,
            },
        ))

    if first_order:
        elapsed = _seconds_between(session.started_at, first_order.created_at)
        events.append(UsabilityTimelineEvent(
            occurred_at=first_order.created_at,
            elapsed_ms=round(elapsed * 1000) if elapsed is not None else None,
            event_type="order",
            screen_name="payment",
            screen_label="결제",
            action_name="order_created",
            action_label="주문 DB 생성",
            target_type="order",
            target_id=first_order.order_uuid,
            target_label=first_order.order_uuid,
            source="system",
            duration_ms=None,
            summary=f"주문이 생성되었습니다. 총 금액 {first_order.total_price:,}원",
            payload_json={
                "total_price": first_order.total_price,
                "used_recommendation": first_order.used_recommendation,
                "status": first_order.status,
            },
        ))

    events.sort(key=lambda item: item.occurred_at)

    notes = []
    if first_order:
        notes.append("이 세션은 주문 생성까지 도달했습니다.")
    else:
        notes.append("이 세션은 주문 생성 기록이 없습니다. 마지막 행동을 기준으로 이탈 지점을 확인하세요.")
    if select_seconds is not None:
        notes.append(f"메뉴 화면 진입 후 첫 메뉴 선택까지 {round(select_seconds, 1)}초가 걸렸습니다.")
    if has_voice:
        notes.append("음성 주문 또는 음성 보조 사용 기록이 포함되어 있습니다.")

    return UsabilitySessionTimelineResponse(session=session_row, events=events, notes=notes)


async def get_usability_analytics(
    db: AsyncSession,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    kiosk_id: Optional[int] = None,
) -> UsabilityAnalyticsResponse:
    session_q = _apply_session_filters(
        select(KioskSession), start_date, end_date, kiosk_id
    )
    sessions = list((await db.execute(session_q)).scalars().all())
    session_ids = [s.id for s in sessions]
    if not session_ids:
        empty_voice = UsabilityVoiceStats(
            sessions=0,
            completed_sessions=0,
            completion_rate=0.0,
            action_successes=0,
            action_failures=0,
            action_failure_rate=0.0,
            avg_total_seconds=0.0,
        )
        return UsabilityAnalyticsResponse(
            summary=[
                UsabilityMetricCard(key="sessions", label="전체 세션", value=0),
                UsabilityMetricCard(key="completion_rate", label="주문 완료율", value=0.0, unit="%"),
            ],
            funnel=[],
            duration_distribution=[],
            menu_select_distribution=[],
            by_age_group=[],
            menu_friction=[],
            voice=empty_voice,
            touch_only=empty_voice,
            abandon_steps=[],
            sessions=[],
            insights=[],
        )

    logs = list(
        (await db.execute(
            select(SessionActivityLog)
            .where(SessionActivityLog.session_id.in_(session_ids))
            .order_by(SessionActivityLog.session_id, SessionActivityLog.occurred_at, SessionActivityLog.seq)
        )).scalars().all()
    )
    orders = list(
        (await db.execute(
            select(Order).where(Order.session_id.in_(session_ids)).order_by(Order.created_at)
        )).scalars().all()
    )
    chat_session_ids = set(
        (await db.execute(
            select(ChatMessage.session_id).where(ChatMessage.session_id.in_(session_ids)).distinct()
        )).scalars().all()
    )
    vision_session_ids = set(
        (await db.execute(
            select(VisionEvent.session_id).where(VisionEvent.session_id.in_(session_ids)).distinct()
        )).scalars().all()
    )
    survey_session_ids = set(
        (await db.execute(
            select(SurveyResponse.session_id).where(
                SurveyResponse.session_id.in_(session_ids),
                SurveyResponse.status == "completed",
            ).distinct()
        )).scalars().all()
    )

    logs_by_session: dict[int, list[SessionActivityLog]] = defaultdict(list)
    for log in logs:
        logs_by_session[log.session_id].append(log)

    first_order_by_session: dict[int, Order] = {}
    for order in orders:
        first_order_by_session.setdefault(order.session_id, order)

    completed_session_ids = set(first_order_by_session.keys())
    total_sessions = len(sessions)
    completed_count = len(completed_session_ids)

    total_durations: list[float] = []
    menu_select_durations: list[float] = []
    payment_durations: list[float] = []
    menu_events_by_session: set[int] = set()
    cart_session_ids: set[int] = set()
    payment_session_ids: set[int] = set()
    voice_session_ids: set[int] = set(chat_session_ids)
    voice_successes_by_session: Counter[int] = Counter()
    voice_failures_by_session: Counter[int] = Counter()
    abandon_counter: Counter[tuple[str | None, str | None]] = Counter()

    menu_opens: Counter[tuple[str | None, str]] = Counter()
    menu_cart_adds: Counter[tuple[str | None, str]] = Counter()
    menu_abandons: Counter[tuple[str | None, str]] = Counter()
    menu_open_seconds: dict[tuple[str | None, str], list[float]] = defaultdict(list)
    menu_rec_opens: Counter[tuple[str | None, str]] = Counter()

    session_features: dict[int, dict[str, object]] = {}
    session_rows: list[UsabilitySessionRow] = []

    for session in sessions:
        session_logs = logs_by_session.get(session.id, [])
        order = first_order_by_session.get(session.id)
        completed = session.id in completed_session_ids

        total_seconds = _seconds_between(session.started_at, order.created_at if order else session.ended_at)
        if completed and total_seconds is not None:
            total_durations.append(total_seconds)

        kiosk_enter = next(
            (
                log.occurred_at
                for log in session_logs
                if log.event_type == "screen"
                and log.action_name == "enter"
                and log.screen_name in {"kiosk", "child_kiosk"}
            ),
            None,
        )
        first_menu_click = next((log for log in session_logs if _is_menu_click(log)), None)
        if first_menu_click:
            menu_events_by_session.add(session.id)
        if kiosk_enter and first_menu_click:
            select_seconds = _seconds_between(kiosk_enter, first_menu_click.occurred_at)
            if select_seconds is not None:
                menu_select_durations.append(select_seconds)
        else:
            select_seconds = None

        payment_start = next((log for log in session_logs if _is_payment_start(log)), None)
        order_success = next((log for log in session_logs if log.action_name == "order_submit_success"), None)
        if payment_start:
            payment_session_ids.add(session.id)
        if payment_start and order_success:
            pay_seconds = _seconds_between(payment_start.occurred_at, order_success.occurred_at)
            if pay_seconds is not None:
                payment_durations.append(pay_seconds)

        has_voice = session.id in chat_session_ids or any(
            log.event_type == "voice" or log.source == "voice" for log in session_logs
        )
        if has_voice:
            voice_session_ids.add(session.id)
        for log in session_logs:
            if _is_menu_click(log):
                key = (log.target_id, log.target_label or "(unknown)")
                menu_opens[key] += 1
                if log.action_name == "recommendation_click":
                    menu_rec_opens[key] += 1
            if log.action_name == "voice_action_applied":
                voice_successes_by_session[session.id] += 1
            if log.action_name == "voice_action_failed":
                voice_failures_by_session[session.id] += 1
            if _is_cart_add(log):
                cart_session_ids.add(session.id)
                key = (log.target_id, log.target_label or "(unknown)")
                menu_cart_adds[key] += 1
            if log.action_name == "menu_detail_close":
                key = (log.target_id, log.target_label or "(unknown)")
                menu_abandons[key] += 1
                if log.duration_ms is not None:
                    menu_open_seconds[key].append(log.duration_ms / 1000)

        if not completed and session_logs:
            last = session_logs[-1]
            abandon_counter[(last.screen_name, last.action_name)] += 1
        last_log = session_logs[-1] if session_logs else None

        session_features[session.id] = {
            "completed": completed,
            "total_seconds": total_seconds if completed else None,
            "select_seconds": select_seconds,
            "voice": has_voice,
            "age_group": session.estimated_age_group,
        }
        session_rows.append(UsabilitySessionRow(
            session_uuid=session.session_uuid,
            started_at=session.started_at,
            age_group=session.estimated_age_group,
            gender=session.estimated_gender,
            completed=completed,
            total_seconds=round(total_seconds, 1) if completed and total_seconds is not None else None,
            first_menu_select_seconds=round(select_seconds, 1) if select_seconds is not None else None,
            voice_used=has_voice,
            last_screen_name=last_log.screen_name if last_log else None,
            last_action_name=last_log.action_name if last_log else None,
            event_count=len(session_logs),
        ))

    def voice_stats(ids: set[int]) -> UsabilityVoiceStats:
        completed_ids = ids & completed_session_ids
        durations = [
            float(session_features[sid]["total_seconds"])
            for sid in completed_ids
            if session_features.get(sid, {}).get("total_seconds") is not None
        ]
        successes = sum(voice_successes_by_session[sid] for sid in ids)
        failures = sum(voice_failures_by_session[sid] for sid in ids)
        return UsabilityVoiceStats(
            sessions=len(ids),
            completed_sessions=len(completed_ids),
            completion_rate=_rate(len(completed_ids), len(ids)),
            action_successes=int(successes),
            action_failures=int(failures),
            action_failure_rate=_rate(int(failures), int(successes + failures)),
            avg_total_seconds=_avg(durations),
        )

    voice_ids = set(voice_session_ids)
    touch_only_ids = set(session_ids) - voice_ids

    by_age: dict[str | None, list[int]] = defaultdict(list)
    for session in sessions:
        by_age[session.estimated_age_group].append(session.id)

    age_rows: list[UsabilityAgeRow] = []
    for age_group, ids in by_age.items():
        id_set = set(ids)
        completed_ids = id_set & completed_session_ids
        durations = [
            float(session_features[sid]["total_seconds"])
            for sid in completed_ids
            if session_features.get(sid, {}).get("total_seconds") is not None
        ]
        select_values = [
            float(session_features[sid]["select_seconds"])
            for sid in id_set
            if session_features.get(sid, {}).get("select_seconds") is not None
        ]
        age_menu_abandons = 0
        age_menu_cart_adds = 0
        for sid in id_set:
            for log in logs_by_session.get(sid, []):
                if log.action_name == "menu_detail_close":
                    age_menu_abandons += 1
                elif _is_cart_add(log):
                    age_menu_cart_adds += 1
        age_voice_ids = id_set & voice_ids
        age_rows.append(UsabilityAgeRow(
            age_group=age_group,
            sessions=len(ids),
            completed_sessions=len(completed_ids),
            completion_rate=_rate(len(completed_ids), len(ids)),
            avg_total_seconds=_avg(durations),
            median_total_seconds=_median(durations),
            avg_menu_select_seconds=_avg(select_values),
            voice_sessions=len(age_voice_ids),
            voice_completion_rate=_rate(len(age_voice_ids & completed_session_ids), len(age_voice_ids)),
            modal_abandon_rate=_rate(age_menu_abandons, age_menu_abandons + age_menu_cart_adds),
        ))
    age_rows.sort(key=lambda row: (row.age_group or "zz"))

    menu_items: list[UsabilityMenuFrictionItem] = []
    menu_keys = set(menu_opens) | set(menu_cart_adds) | set(menu_abandons)
    for key in menu_keys:
        opens = int(menu_opens[key])
        cart_adds = int(menu_cart_adds[key])
        abandons = int(menu_abandons[key])
        denominator = opens or cart_adds + abandons
        menu_items.append(UsabilityMenuFrictionItem(
            menu_id=key[0],
            menu_name=key[1],
            opens=opens,
            cart_adds=cart_adds,
            abandons=abandons,
            abandon_rate=_rate(abandons, denominator),
            avg_open_seconds=_avg(menu_open_seconds[key]),
            recommendation_opens=int(menu_rec_opens[key]),
        ))
    menu_items.sort(key=lambda item: (item.abandon_rate, item.abandons, item.opens), reverse=True)

    abandon_total = sum(abandon_counter.values())
    abandon_steps = [
        UsabilityAbandonStep(
            screen_name=screen,
            action_name=action,
            count=count,
            rate=_rate(count, abandon_total),
        )
        for (screen, action), count in abandon_counter.most_common(10)
    ]

    funnel = [
        UsabilityFunnelStep(key="sessions", label="세션 시작", count=total_sessions, rate=1.0),
        UsabilityFunnelStep(key="vision", label="얼굴 분석", count=len(vision_session_ids), rate=_rate(len(vision_session_ids), total_sessions)),
        UsabilityFunnelStep(key="menu", label="메뉴 선택", count=len(menu_events_by_session), rate=_rate(len(menu_events_by_session), total_sessions)),
        UsabilityFunnelStep(key="cart", label="장바구니 사용", count=len(cart_session_ids), rate=_rate(len(cart_session_ids), total_sessions)),
        UsabilityFunnelStep(key="payment", label="결제 진입", count=len(payment_session_ids), rate=_rate(len(payment_session_ids), total_sessions)),
        UsabilityFunnelStep(key="order", label="주문 완료", count=completed_count, rate=_rate(completed_count, total_sessions)),
        UsabilityFunnelStep(key="survey", label="설문 완료", count=len(survey_session_ids), rate=_rate(len(survey_session_ids), total_sessions)),
    ]

    voice = voice_stats(voice_ids)
    touch_only = voice_stats(touch_only_ids)
    modal_abandons_total = sum(menu_abandons.values())
    modal_cart_total = sum(menu_cart_adds.values())

    summary = [
        UsabilityMetricCard(key="sessions", label="전체 세션", value=total_sessions),
        UsabilityMetricCard(key="completion_rate", label="주문 완료율", value=round(_rate(completed_count, total_sessions) * 100, 1), unit="%"),
        UsabilityMetricCard(key="avg_total_seconds", label="평균 주문 시간", value=_avg(total_durations), unit="sec", detail=f"중앙값 {_median(total_durations)}초"),
        UsabilityMetricCard(key="avg_menu_select_seconds", label="첫 메뉴 선택 시간", value=_avg(menu_select_durations), unit="sec", detail=f"중앙값 {_median(menu_select_durations)}초"),
        UsabilityMetricCard(key="avg_payment_seconds", label="결제 단계 시간", value=_avg(payment_durations), unit="sec"),
        UsabilityMetricCard(key="voice_completion_rate", label="음성 사용 완료율", value=round(voice.completion_rate * 100, 1), unit="%", detail=f"음성 세션 {voice.sessions}건"),
        UsabilityMetricCard(key="modal_abandon_rate", label="메뉴 상세 이탈률", value=round(_rate(modal_abandons_total, modal_abandons_total + modal_cart_total) * 100, 1), unit="%"),
    ]

    insights: list[UsabilityInsight] = []
    completion_rate = _rate(completed_count, total_sessions)
    if completion_rate >= 0.8:
        insights.append(UsabilityInsight(
            level="good",
            title="주문 완료율이 양호합니다",
            message=f"선택한 기간의 주문 완료율은 {completion_rate * 100:.1f}%입니다. 현재 흐름은 테스트 사용자에게 전반적으로 작동하고 있습니다.",
        ))
    else:
        insights.append(UsabilityInsight(
            level="warning",
            title="주문 완료율 점검이 필요합니다",
            message=f"선택한 기간의 주문 완료율은 {completion_rate * 100:.1f}%입니다. 다음 테스트 전에 미완료 세션의 마지막 행동을 먼저 확인하세요.",
        ))
    if voice.sessions > 0:
        delta = voice.completion_rate - touch_only.completion_rate
        level = "good" if delta >= 0 else "warning"
        insights.append(UsabilityInsight(
            level=level,
            title="음성 지원 효과 비교",
            message=f"음성 사용 세션의 완료율은 {voice.completion_rate * 100:.1f}%로, 터치 전용 세션보다 {abs(delta) * 100:.1f}%p {'높습니다' if delta >= 0 else '낮습니다'}.",
        ))
    if menu_select_durations:
        insights.append(UsabilityInsight(
            level="info",
            title="메뉴 탐색 시간",
            message=f"메뉴 화면 진입 후 첫 메뉴를 선택하기까지의 중앙값은 {_median(menu_select_durations)}초입니다.",
        ))
    if modal_abandons_total > 0:
        top = menu_items[0] if menu_items else None
        if top:
            insights.append(UsabilityInsight(
                level="warning",
                title="메뉴 상세 이탈 신호",
                message=f"'{top.menu_name}' 메뉴에서 장바구니 추가 없이 닫힌 기록이 가장 많습니다. 닫힘 {top.abandons}건이 관찰되었습니다.",
            ))

    return UsabilityAnalyticsResponse(
        summary=summary,
        funnel=funnel,
        duration_distribution=_duration_buckets(total_durations),
        menu_select_distribution=_duration_buckets(menu_select_durations),
        by_age_group=age_rows,
        menu_friction=menu_items[:15],
        voice=voice,
        touch_only=touch_only,
        abandon_steps=abandon_steps,
        sessions=sorted(session_rows, key=lambda row: row.started_at, reverse=True)[:100],
        insights=insights,
    )
