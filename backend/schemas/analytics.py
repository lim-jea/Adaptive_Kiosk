from pydantic import BaseModel


class SessionAnalytics(BaseModel):
    total_sessions: int
    simple_mode_sessions: int
    simple_mode_rate: float
    help_triggered_count: int


class RecommendationAnalytics(BaseModel):
    total_shown: int
    total_clicked: int
    click_through_rate: float
    led_to_order_count: int
    order_conversion_rate: float


class OrderAnalytics(BaseModel):
    total_orders: int
    total_revenue: int                   # 총 매출
    avg_order_price: float               # 평균 주문 금액
    recommendation_used_count: int
    recommendation_used_rate: float
