from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.order import create_order, get_order
from schemas.order import OrderCreate, OrderResponse

router = APIRouter(prefix="/orders", tags=["Order"])


@router.post("", response_model=OrderResponse)
async def place_order(
    data: OrderCreate,
    total_time_seconds: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """주문을 생성합니다 (메뉴 선택, 추천 경유 여부 포함)."""
    return await create_order(db, data, total_time_seconds)


@router.get("/{order_id}", response_model=OrderResponse)
async def read_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """주문 상세를 조회합니다."""
    order = await get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
