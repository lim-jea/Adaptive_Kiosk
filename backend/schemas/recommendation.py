"""추천 시스템 Pydantic 스키마."""

from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendationItemResponse(BaseModel):
    """상황 기반 추천 또는 보완 추천 아이템."""

    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    count: Optional[int] = Field(None, description="주문 횟수")
    popularity: Optional[float] = Field(None, description="인기도(0~1)")
    trend_weight: Optional[float] = Field(None, description="트렌드 가중치")
    final_score: Optional[float] = Field(None, description="최종 점수")
    copurchase_count: Optional[int] = Field(None, description="함께 구매된 횟수")
    strength: Optional[float] = Field(None, description="추천 강도")
    frequency: Optional[str] = Field(None, description="비율 문자열")


class SelectedMenuResponse(BaseModel):
    """선택된 메뉴 정보."""

    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")


class ModeAResponse(BaseModel):
    """상황 기반 추천 응답."""

    mode: str = Field(default="A", description="추천 모드")
    situation: str = Field(..., description="상황 설명")
    recommendations: List[RecommendationItemResponse] = Field(..., description="추천 목록")
    total_orders: int = Field(..., description="해당 상황의 주문 수")
    total_items: Optional[int] = Field(None, description="해당 상황의 아이템 수")
    cache_hit: Optional[bool] = Field(None, description="캐시 적중 여부")


class CFScoreBreakdown(BaseModel):
    """CF 점수 분해 결과."""

    profile_popularity: float = Field(..., description="프로필 인기도")
    global_popularity: float = Field(..., description="전체 평균 인기도")
    cart_cf_score: Optional[float] = Field(None, description="장바구니 기반 협업 필터링 점수")
    cf_score: float = Field(..., description="CF 점수")


class IntegratedRecommendationItem(BaseModel):
    """통합 추천 아이템."""

    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    cf_breakdown: CFScoreBreakdown = Field(..., description="CF 점수 분해")
    trend_score: float = Field(..., description="트렌드 가중치")
    final_score: float = Field(..., description="최종 점수")
    reasoning: str = Field(..., description="추천 이유")


class SuggestRequest(BaseModel):
    """통합 추천 요청."""

    gender: str = Field(..., description="M 또는 F")
    age: int = Field(..., ge=15, le=100, description="사용자 나이")
    cart_items: List[int] = Field(default_factory=list, description="장바구니 메뉴 ID 목록")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")
    include_trend: Optional[bool] = Field(True, description="트렌드 반영 여부")


class SuggestResponse(BaseModel):
    """통합 추천 응답."""

    mode: str = Field(default="CF", description="추천 모드")
    user_context: dict = Field(..., description="사용자 문맥")
    cart_items: List[SelectedMenuResponse] = Field(..., description="장바구니 메뉴 목록")
    recommendations: List[IntegratedRecommendationItem] = Field(..., description="추천 목록")
    cache_hit: Optional[bool] = Field(None, description="캐시 적중 여부")
