"""
추천 시스템 Pydantic 스키마
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ═══════════════════════════════════════════════════════════════════
# 응답 스키마
# ═══════════════════════════════════════════════════════════════════

class RecommendationItemResponse(BaseModel):
    """추천 음료 아이템"""
    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    count: Optional[int] = Field(None, description="주문 횟수")
    popularity: Optional[float] = Field(None, description="인기도 (0~1)")
    trend_weight: Optional[float] = Field(None, description="트렌드 가중치")
    final_score: Optional[float] = Field(None, description="최종 점수")
    copurchase_count: Optional[int] = Field(None, description="함께 구매된 횟수")
    strength: Optional[float] = Field(None, description="강도 (0~1)")
    frequency: Optional[str] = Field(None, description="빈도 (%)")


class SelectedMenuResponse(BaseModel):
    """선택한 메뉴"""
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")


# ═══════════════════════════════════════════════════════════════════
# Mode A (상황 기반)
# ═══════════════════════════════════════════════════════════════════

class ModeARequest(BaseModel):
    """Mode A 요청 (이전 - 호환성용)"""
    gender: str = Field(..., description="M (남성) or F (여성)")
    age_group: str = Field(..., description="20~29, 30~39, 40~49, 50+")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")


class ModeANewRequest(BaseModel):
    """Mode A 새로운 요청 - 나이 입력"""
    gender: str = Field(..., description="M (남성) or F (여성)")
    age: int = Field(..., ge=15, le=100, description="나이 (세)")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")


class ModeAResponse(BaseModel):
    """Mode A 응답"""
    mode: str = Field(default="A", description="추천 모드")
    situation: str = Field(..., description="상황 설명")
    recommendations: List[RecommendationItemResponse] = Field(..., description="추천 음료 목록")
    total_orders: int = Field(..., description="해당 상황의 총 주문 수")
    total_items: Optional[int] = Field(None, description="해당 상황의 총 아이템 수")
    cache_hit: Optional[bool] = Field(None, description="캐시 히트 여부")


# ═══════════════════════════════════════════════════════════════════
# Mode B (보완 음료)
# ═══════════════════════════════════════════════════════════════════

class ModeBRequest(BaseModel):
    """Mode B 요청"""
    selected_menu_ids: List[int] = Field(..., description="선택한 메뉴 ID 목록")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")


class ModeBResponse(BaseModel):
    """Mode B 응답"""
    mode: str = Field(default="B", description="추천 모드")
    selected: List[SelectedMenuResponse] = Field(..., description="선택한 메뉴 목록")
    recommendations: List[RecommendationItemResponse] = Field(..., description="추천 음료 목록")
    ordered_with: int = Field(..., description="함께 구매된 주문 수")
    cache_hit: Optional[bool] = Field(None, description="캐시 히트 여부")


# ═══════════════════════════════════════════════════════════════════
# 헬스 체크
# ═══════════════════════════════════════════════════════════════════

class RecommendationHealthResponse(BaseModel):
    """추천 시스템 상태"""
    status: str = Field(..., description="상태")
    engine_loaded: bool = Field(..., description="엔진 로드 여부")
    cache_enabled: bool = Field(..., description="캐시 활성화 여부")
    mode_a_combinations: int = Field(..., description="Mode A 조합 수")
    mode_b_beverages: int = Field(..., description="Mode B 음료 수")
    data_counts: dict = Field(..., description="데이터 집계")


# ═══════════════════════════════════════════════════════════════════
# 협업 필터링 (CF) 중심 통합 추천
# ═══════════════════════════════════════════════════════════════════

class CFScoreBreakdown(BaseModel):
    """CF 점수 분석"""
    profile_popularity: float = Field(..., description="같은 프로필 사용자 인기도 (0~1)")
    global_popularity: float = Field(..., description="전체 사용자 평균 인기도 (0~1)")
    cf_score: float = Field(..., description="CF 종합 점수 = 0.6×profile + 0.4×global")


class IntegratedRecommendationItem(BaseModel):
    """통합 추천 아이템 (CF 기반)"""
    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    cf_breakdown: CFScoreBreakdown = Field(..., description="CF 점수 분석")
    trend_score: float = Field(..., description="트렌드 가중치 (0.5~2.0)")
    final_score: float = Field(..., description="최종 점수 = CF_Score + (Trend×0.15)")
    reasoning: str = Field(..., description="추천 이유")


class SuggestRequest(BaseModel):
    """협업 필터링 추천 요청"""
    gender: str = Field(..., description="M (남성) or F (여성)")
    age: int = Field(..., ge=15, le=100, description="사용자 나이 (세)")
    cart_items: List[int] = Field(default_factory=list, description="장바구니 음료 menu_id 목록")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")
    include_trend: Optional[bool] = Field(True, description="트렌드 반영 여부")


class SuggestResponse(BaseModel):
    """협업 필터링 추천 응답"""
    mode: str = Field(default="CF", description="추천 모드")
    user_context: dict = Field(..., description="사용자 컨텍스트 {gender, age_group, period}")
    cart_items: List[SelectedMenuResponse] = Field(..., description="장바구니 음료 목록")
    recommendations: List[IntegratedRecommendationItem] = Field(..., description="CF 기반 추천 음료 목록")
    cache_hit: Optional[bool] = Field(None, description="캐시 히트 여부")
