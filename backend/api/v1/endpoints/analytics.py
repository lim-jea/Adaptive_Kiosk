from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from schemas.analytics import (
    AnalyticsRangeRequest,
    SessionAnalytics,
    RecommendationAnalytics,
    OrderAnalytics,
)
from services.analytics_service import (
    get_session_analytics,
    get_recommendation_analytics,
    get_order_analytics,
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
