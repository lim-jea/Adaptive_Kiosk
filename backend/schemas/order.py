from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class SelectedOptionRequest(BaseModel):
    """선택한 옵션 아이템"""
    option_item_id: int = Field(..., gt=0, examples=[2])


class OrderItemRequest(BaseModel):
    """주문 아이템 1건"""
    menu_name: str = Field(..., min_length=1, examples=["아이스 아메리카노"])
    quantity: int = Field(default=1, ge=1, le=99, examples=[2])
    unit_price: int = Field(..., ge=0, examples=[5000], description="프런트 계산값 (서버에서 재검증)")
    from_recommendation: bool = Field(default=False)
    selected_options: List[SelectedOptionRequest] = Field(default=[], examples=[[{"option_item_id": 2}]])


class OrderCreateRequest(BaseModel):
    """주문 생성 요청"""
    session_uuid: str = Field(..., min_length=32, max_length=32)
    items: List[OrderItemRequest] = Field(..., min_length=1, description="최소 1개 아이템 필요")
    used_recommendation: bool = Field(default=False)


class OrderItemOptionResponse(BaseModel):
    option_name: str
    extra_price: int

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: int
    menu_name: str
    quantity: int
    unit_price: int
    from_recommendation: bool
    options: List[OrderItemOptionResponse] = []

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    order_uuid: str
    session_uuid: str
    created_at: datetime
    total_price: int
    used_recommendation: bool
    status: str
    items: List[OrderItemResponse]

    model_config = {"from_attributes": True}
