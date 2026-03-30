from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from schemas.analytics import SessionAnalytics, RecommendationAnalytics, OrderAnalytics
from services.analytics_service import (
    get_session_analytics,
    get_recommendation_analytics,
    get_order_analytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/sessions", response_model=SessionAnalytics)
async def session_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """세션 통계 (총 세션 수, 간편모드 전환율, 도움 트리거 수). 관리자 인증 필요."""
    return await get_session_analytics(db)


@router.get("/recommendations", response_model=RecommendationAnalytics)
async def recommendation_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """추천 통계 (노출 수, 클릭률, 주문 전환율). 관리자 인증 필요."""
    return await get_recommendation_analytics(db)


@router.get("/orders", response_model=OrderAnalytics)
async def order_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """주문 통계 (총 주문 수, 평균 주문 시간, 추천 경유 비율). 관리자 인증 필요."""
    return await get_order_analytics(db)
