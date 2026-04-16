"""
추천 API 엔드포인트

GET /api/v1/recommendations/situation - Mode A: 상황 기반
POST /api/v1/recommendations/complementary - Mode B: 주문 이력 기반
"""

from fastapi import APIRouter, Query, Body, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
from datetime import datetime

from core.database import get_session_factory
from services.recommendation_service import get_recommendation_engine
from schemas.recommendation import (
    ModeANewRequest,
    ModeAResponse,
    ModeBRequest,
    ModeBResponse,
    RecommendationHealthResponse,
    SuggestRequest,
    SuggestResponse,
)
from utils.recommendation_utils import age_to_age_group

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendation"])

@router.get("/situation", response_model=ModeAResponse)
async def get_situation_based_recommendations(
    gender: str = Query(..., description="M (남성) or F (여성)"),
    age: int = Query(..., ge=15, le=100, description="사용자 나이 (세)"),
    top_n: int = Query(5, ge=1, le=10, description="추천 개수"),
) -> ModeAResponse:
    """
    **Mode A: 상황 기반 추천**

    성별 + 나이 + 현재 시간에 따른 인기 음료 추천

    - Gender: M (남성), F (여성)
    - Age: 15 ~ 100 (세) - 자동으로 나이대(20~29, 30~39 등)로 변환됨

    Note:
    - **시간대**: 서버에서 현재 시간 자동 감지 (클라이언트 입력 불필요)
    - **Naver 트렌드**: 유사어 포함하여 검색 (예: 아메리카노 → 아아, 아메리카노, 에스프레소)
    - **나이대 변환**: 20세 이상만 지원 (15~19세는 불가)

    Example:
    ```
    GET /api/v1/recommendations/situation?gender=M&age=35&top_n=5
    ```
    """
    try:
        # 나이 → 나이대 변환
        try:
            age_group = age_to_age_group(age)
        except ValueError as e:
            logger.warning(f"Age validation failed: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        # 현재 시간 자동 감지
        current_hour = datetime.now().hour
        logger.debug(f"📥 API 요청 (Mode A): gender={gender}, age={age} → age_group={age_group}, current_hour={current_hour}, top_n={top_n}")

        engine = get_recommendation_engine()

        if not engine.is_loaded:
            logger.error("Recommendation engine not loaded")
            raise HTTPException(
                status_code=503,
                detail="Recommendation engine not initialized"
            )

        result = engine.get_mode_a_recommendations(
            gender=gender,
            age_group=age_group,
            hour=current_hour,
            top_n=top_n,
            include_trend=True
        )

        if 'error' in result:
            logger.error(f"Engine error: {result['error']}")
            raise HTTPException(status_code=500, detail=result['error'])

        logger.info(
            f"📤 API 응답 (Mode A): {result['situation']} "
            f"→ {len(result['recommendations'])}개 추천 "
            f"({result['total_orders']}개 주문 / {result['total_items']}개 아이템 기반)"
        )
        rec_list = ', '.join([f"{r['menu_name']}({r['final_score']:.3f})" for r in result['recommendations']])
        logger.debug(f"  추천 목록: {rec_list}")

        return ModeAResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Mode A 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complementary", response_model=ModeBResponse)
async def get_complementary_recommendations(
    request: ModeBRequest = Body(..., example={
        "selected_menu_ids": [3, 10],
        "top_n": 5
    })
) -> ModeBResponse:
    """
    **Mode B: 주문 이력 기반 추천**
    
    선택한 음료들과 함께 자주 구매되는 음료 추천
    
    Example:
    ```json
    {
        "selected_menu_ids": [3, 10],
        "top_n": 5
    }
    ```
    
    Response:
    - `ordered_with`: 해당 음료들이 함께 주문된 사례 수
    - `strength`: 보완 음료의 추천 강도 (0~1)
    - `frequency`: 추천 강도의 백분율 표현
    """
    try:
        logger.debug(f"📥 API 요청 (Mode B): selected_menu_ids={request.selected_menu_ids}, top_n={request.top_n}")
        
        engine = get_recommendation_engine()
        
        if not engine.is_loaded:
            logger.error("Recommendation engine not loaded")
            raise HTTPException(
                status_code=503,
                detail="Recommendation engine not initialized"
            )
        
        # 선택한 메뉴 검증
        if not request.selected_menu_ids:
            logger.warning("Empty selected_menu_ids")
            raise HTTPException(
                status_code=400,
                detail="selected_menu_ids cannot be empty"
            )
        
        result = engine.get_mode_b_recommendations(
            selected_menu_ids=request.selected_menu_ids,
            top_n=request.top_n,
            include_trend=False
        )
        
        if 'error' in result:
            logger.error(f"Engine error: {result['error']}")
            raise HTTPException(status_code=500, detail=result['error'])
        
        logger.info(
            f"📤 API 응답 (Mode B): 선택 {len(result['selected'])}개 음료 "
            f"→ {len(result['recommendations'])}개 보완 추천 "
            f"({result['ordered_with']}개 함께 주문된 사례)"
        )
        selected_list = ', '.join([m['menu_name'] for m in result['selected']])
        rec_list = ', '.join([f"{r['menu_name']}({r['strength']:.1%})" for r in result['recommendations']])
        logger.debug(f"  선택 음료: {selected_list}")
        logger.debug(f"  추천 음료: {rec_list}")
        
        return ModeBResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Mode B recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest", response_model=SuggestResponse)
async def get_integrated_recommendations(
    request: SuggestRequest = Body(..., example={
        "gender": "M",
        "age": 35,
        "cart_items": [3, 10],
        "top_n": 5,
        "include_trend": True
    })
) -> SuggestResponse:
    """
    **협업 필터링(CF) 중심 통합 추천**

    성별×나이×시간대 기반 협업 필터링 + 트렌드 가중치

    **알고리즘**:
    - CF_Score = 0.6 × 프로필인기도 + 0.4 × 전체평균인기도
    - Final_Score = CF_Score + (트렌드가중치 × 0.15)

    **특징**:
    - 같은 프로필(성별/나이/시간대) 사용자 선호도 60% 반영
    - 전체 보편적 인기도 40% 반영 (다양성 보장)
    - 트렌드 신호 추가 반영 (기본 활성화)
    - 장바구니 음료는 자동 제외

    **요청 예시**:
    ```json
    {
        "gender": "M",
        "age": 35,
        "cart_items": [3, 10],
        "top_n": 5,
        "include_trend": true
    }
    ```

    **응답 필드**:
    - `user_context`: 사용자 프로필 {gender, age_group, period, current_hour}
    - `cart_items`: 장바구니 음료 목록
    - `recommendations`: CF 기반 추천 음료
        - `cf_breakdown`: {profile_popularity, global_popularity, cf_score}
        - `trend_score`: 트렌드 가중치
        - `final_score`: 최종 점수
        - `reasoning`: 추천 이유
    - `cache_hit`: 캐시 사용 여부
    """
    try:
        logger.debug(
            f"📥 CF 통합 추천 API 요청: "
            f"gender={request.gender}, age={request.age}, "
            f"cart={request.cart_items}, top_n={request.top_n}"
        )

        engine = get_recommendation_engine()

        if not engine.is_loaded:
            logger.error("Recommendation engine not loaded")
            raise HTTPException(
                status_code=503,
                detail="Recommendation engine not initialized"
            )

        # CF 추천 메서드 호출
        result = engine.get_integrated_recommendations(
            gender=request.gender,
            age=request.age,
            cart_items=request.cart_items,
            top_n=request.top_n,
            include_trend=request.include_trend
        )

        if 'error' in result:
            logger.error(f"Engine error: {result['error']}")
            raise HTTPException(status_code=500, detail=result['error'])

        logger.info(
            f"📤 CF 추천 API 응답: "
            f"{result['user_context']['age_group']}/{result['user_context']['period']} "
            f"→ {len(result['recommendations'])}개 추천"
        )

        rec_list = ', '.join([f"{r['menu_name']}({r['final_score']:.4f})" for r in result['recommendations']])
        logger.debug(f"  추천 목록: {rec_list}")

        return SuggestResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in CF recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def health_check():
    """추천 시스템 상태 확인"""
    engine = get_recommendation_engine()
    
    return {
        "status": "healthy" if engine.is_loaded else "not_loaded",
        "engine_loaded": engine.is_loaded,
        "data_available": {
            "sessions": len(engine.sessions_df) if engine.sessions_df is not None else 0,
            "orders": len(engine.orders_df) if engine.orders_df is not None else 0,
            "items": len(engine.order_items_df) if engine.order_items_df is not None else 0,
        }
    }
