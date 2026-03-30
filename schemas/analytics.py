from pydantic import BaseModel


class SessionAnalytics(BaseModel):
    total_sessions: int
    simple_mode_sessions: int
    simple_mode_rate: float          # 간편모드 전환율
    help_triggered_count: int


class RecommendationAnalytics(BaseModel):
    total_shown: int                 # 추천 노출 수
    total_clicked: int               # 추천 클릭 수
    click_through_rate: float        # 추천 클릭률
    led_to_order_count: int          # 추천 → 주문 전환 수
    order_conversion_rate: float     # 추천 주문 전환율


class OrderAnalytics(BaseModel):
    total_orders: int
    avg_order_time_seconds: float    # 평균 주문 소요 시간
    recommendation_used_count: int   # 추천 경유 주문 수
    recommendation_used_rate: float  # 추천 경유 주문 비율


class MenuResponse(BaseModel):
    id: int
    name: str
    category_id: int
    price: int
    description: str | None = None
    image_url: str | None = None
    is_available: bool

    model_config = {"from_attributes": True}


class CategoryResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
