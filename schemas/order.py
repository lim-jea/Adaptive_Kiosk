from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class OrderItemCreate(BaseModel):
    menu_id: int
    quantity: int = 1
    from_recommendation: bool = False


class OrderCreate(BaseModel):
    session_id: int
    items: List[OrderItemCreate]
    used_recommendation: bool = False


class OrderItemResponse(BaseModel):
    id: int
    menu_id: int
    quantity: int
    from_recommendation: bool

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    session_id: int
    created_at: datetime
    total_time_seconds: Optional[int] = None
    used_recommendation: bool
    status: str
    items: List[OrderItemResponse]

    model_config = {"from_attributes": True}
