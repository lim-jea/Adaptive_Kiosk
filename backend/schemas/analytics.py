from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnalyticsRangeRequest(BaseModel):
    """분석 기간 필터"""
    start_date: Optional[datetime] = Field(None, description="시작 시각 (포함)")
    end_date: Optional[datetime] = Field(None, description="종료 시각 (미포함)")
    kiosk_id: Optional[int] = Field(None, description="특정 키오스크만 필터")


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
    total_revenue: int
    avg_order_price: float
    recommendation_used_count: int
    recommendation_used_rate: float
