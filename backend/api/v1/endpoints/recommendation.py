"""
추천 API 엔드포인트.

- GET /api/v1/recommendations/situation
- POST /api/v1/recommendations/suggest
"""

from datetime import datetime
import logging

from fastapi import APIRouter, Body, HTTPException, Query

from schemas import ModeAResponse, SuggestRequest, SuggestResponse
from services.recommendation_service import get_recommendation_engine
from utils.recommendation_utils import age_to_age_group, normalize_age_group, normalize_gender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendation"])


@router.get("/situation", response_model=ModeAResponse)
async def get_situation_based_recommendations(
    gender: str = Query(..., description="M or F"),
    age: int | None = Query(None, ge=15, le=100, description="사용자 나이"),
    age_group: str | None = Query(None, description="20~29, 30~39, 40~49, 50+"),
    top_n: int = Query(5, ge=1, le=10, description="추천 개수"),
) -> ModeAResponse:
    """
    상황 기반 추천.

    - 신규 경로: `age` 전달
    - 호환 경로: `age_group` 전달
    """
    try:
        try:
            gender = normalize_gender(gender)
        except ValueError as exc:
            logger.warning("Gender validation failed: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc))

        if age is None and age_group is None:
            raise HTTPException(status_code=400, detail="age 또는 age_group 중 하나는 필수입니다.")

        if age is not None:
            try:
                age_group = age_to_age_group(age)
            except ValueError as exc:
                logger.warning("Age validation failed: %s", exc)
                raise HTTPException(status_code=400, detail=str(exc))
        else:
            try:
                age_group = normalize_age_group(age_group)
            except ValueError as exc:
                logger.warning("Age group validation failed: %s", exc)
                raise HTTPException(status_code=400, detail=str(exc))

        current_hour = datetime.now().hour
        engine = get_recommendation_engine()

        if not engine.is_loaded:
            logger.error("Recommendation engine not loaded")
            raise HTTPException(status_code=503, detail="Recommendation engine not initialized")

        result = engine.get_mode_a_recommendations(
            gender=gender,
            age_group=age_group,
            hour=current_hour,
            top_n=top_n,
            include_trend=True,
        )

        if "error" in result:
            logger.error("Mode A engine error: %s", result["error"])
            raise HTTPException(status_code=500, detail=result["error"])

        return ModeAResponse(**result)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Mode A recommendation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/suggest", response_model=SuggestResponse)
async def get_integrated_recommendations(
    request: SuggestRequest = Body(
        ...,
        example={
            "gender": "M",
            "age": 35,
            "cart_items": [3, 10],
            "top_n": 5,
            "include_trend": True,
        },
    )
) -> SuggestResponse:
    """협업 필터링 기반 통합 추천."""
    try:
        engine = get_recommendation_engine()

        if not engine.is_loaded:
            logger.error("Recommendation engine not loaded")
            raise HTTPException(status_code=503, detail="Recommendation engine not initialized")

        try:
            gender = normalize_gender(request.gender)
        except ValueError as exc:
            logger.warning("Gender validation failed: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc))

        result = engine.get_integrated_recommendations(
            gender=gender,
            age=request.age,
            cart_items=request.cart_items,
            top_n=request.top_n,
            include_trend=request.include_trend,
        )

        if "error" in result:
            logger.error("CF engine error: %s", result["error"])
            status_code = 404 if result["error"].startswith("No data for profile:") else 400
            raise HTTPException(status_code=status_code, detail=result["error"])

        return SuggestResponse(**result)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("CF recommendation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
