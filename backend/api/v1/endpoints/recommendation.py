from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.recommendation import create_recommendation_events, mark_clicked
from schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedMenuItem,
    RecommendationClickLog,
)
from services.recommendation_service import get_recommendations

router = APIRouter(prefix="/recommendations", tags=["Recommendation"])


@router.post("/request", response_model=RecommendationResponse)
async def request_recommendation(data: RecommendationRequest, db: AsyncSession = Depends(get_db)):
    """
    선호 카테고리를 입력받아 추천 결과를 반환합니다.
    - your_picks: 선호 계열 중심 추천
    - discovery: CF 기반 다른 계열 추천
    """
    result = await get_recommendations(
        db=db,
        preferred_category=data.preferred_category,
        estimated_gender=data.estimated_gender,
        estimated_age_group=data.estimated_age_group,
    )

    all_recs = result["your_picks"] + result["discovery"]
    if all_recs:
        await create_recommendation_events(
            db=db,
            session_id=data.session_id,
            preferred_category=data.preferred_category,
            recommendations=all_recs,
        )

    return RecommendationResponse(
        your_picks=[RecommendedMenuItem(**r) for r in result["your_picks"]],
        discovery=[RecommendedMenuItem(**r) for r in result["discovery"]],
    )


@router.post("/click")
async def log_recommendation_click(data: RecommendationClickLog, db: AsyncSession = Depends(get_db)):
    """추천 메뉴 클릭 이벤트를 기록합니다."""
    await mark_clicked(db, data.recommendation_event_id)
    return {"status": "ok"}
