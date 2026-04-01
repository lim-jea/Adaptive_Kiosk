from typing import List, Optional
from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    """추천 요청 (선호 카테고리 입력)"""
    session_id: int
    preferred_category: str          # "커피", "라떼", "에이드", "티" 등
    estimated_gender: Optional[str] = None
    estimated_age_group: Optional[str] = None


class RecommendedMenuItem(BaseModel):
    menu_id: int
    menu_name: str
    category: str
    price: int
    image_url: Optional[str] = None
    recommendation_type: str         # "your_picks" / "discovery"


class RecommendationResponse(BaseModel):
    your_picks: List[RecommendedMenuItem]    # 선호 계열 중심 추천
    discovery: List[RecommendedMenuItem]     # CF 기반 다른 계열 추천


class RecommendationClickLog(BaseModel):
    """추천 메뉴 클릭 이벤트"""
    session_id: int
    recommendation_event_id: int
    menu_id: int
