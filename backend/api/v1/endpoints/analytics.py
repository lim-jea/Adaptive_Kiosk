from typing import Literal, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from schemas import (
    AnalyticsRangeRequest,
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
from services.analytics_service import (
    get_category_breakdown,
    get_demographics_breakdown,
    get_menu_rankings,
    get_option_usage,
    get_order_analytics,
    get_orders_by_hour_of_day,
    get_orders_timeseries,
    get_recommendation_analytics,
    get_recommendation_breakdown,
    get_recommendation_funnel,
    get_session_analytics,
    get_session_duration,
    get_session_funnel,
    get_sessions_timeseries,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/sessions", response_model=SessionAnalytics)
async def session_stats(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """세션 통계. 기간/키오스크 필터 가능. 관리자 인증 필요."""
    return await get_session_analytics(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/recommendations", response_model=RecommendationAnalytics)
async def recommendation_stats(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """추천 통계. 기간 필터 가능. 관리자 인증 필요."""
    return await get_recommendation_analytics(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/orders", response_model=OrderAnalytics)
async def order_stats(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """주문 통계. 기간/키오스크 필터 가능. 관리자 인증 필요."""
    return await get_order_analytics(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


# --- Time series & breakdowns ---------------------------------------------------


@router.get("/orders/timeseries", response_model=list[TimeseriesBucket])
async def orders_timeseries(
    bucket: Literal["hour", "day"] = Query("day"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    kiosk_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_orders_timeseries(
        db, bucket=bucket, start_date=start_date, end_date=end_date, kiosk_id=kiosk_id
    )


@router.get("/sessions/timeseries", response_model=list[TimeseriesBucket])
async def sessions_timeseries(
    bucket: Literal["hour", "day"] = Query("day"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    kiosk_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_sessions_timeseries(
        db, bucket=bucket, start_date=start_date, end_date=end_date, kiosk_id=kiosk_id
    )


@router.get("/orders/by-hour-of-day", response_model=list[HourOfDayPoint])
async def orders_by_hour_of_day(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_orders_by_hour_of_day(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/menus/top", response_model=list[MenuRankingItem])
async def menus_top(
    limit: int = Query(10, ge=1, le=100),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    kiosk_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_menu_rankings(
        db, start_date=start_date, end_date=end_date, kiosk_id=kiosk_id, limit=limit
    )


@router.get("/menus/by-category", response_model=list[CategoryBreakdownItem])
async def menus_by_category(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_category_breakdown(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/menus/options", response_model=list[OptionUsageItem])
async def menus_option_usage(
    menu_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    kiosk_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_option_usage(
        db, menu_id=menu_id, start_date=start_date, end_date=end_date, kiosk_id=kiosk_id
    )


@router.get("/sessions/demographics", response_model=list[DemographicsCell])
async def sessions_demographics(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_demographics_breakdown(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/sessions/funnel", response_model=FunnelResponse)
async def sessions_funnel(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_session_funnel(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/sessions/duration", response_model=SessionDurationStats)
async def sessions_duration(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """완료된 세션의 평균 체류시간(초) + 연령대별 분해."""
    return await get_session_duration(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/recommendations/funnel", response_model=RecommendationFunnel)
async def recommendations_funnel(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_recommendation_funnel(
        db, start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id
    )


@router.get("/recommendations/by-category", response_model=list[RecommendationBreakdownItem])
async def recommendations_by_category(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_recommendation_breakdown(
        db, by="preferred_category",
        start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id,
    )


@router.get("/recommendations/by-type", response_model=list[RecommendationBreakdownItem])
async def recommendations_by_type(
    req: AnalyticsRangeRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_recommendation_breakdown(
        db, by="recommendation_type",
        start_date=req.start_date, end_date=req.end_date, kiosk_id=req.kiosk_id,
    )
