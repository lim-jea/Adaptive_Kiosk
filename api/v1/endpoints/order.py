from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.order import create_order, get_order_by_uuid
from schemas.order import OrderCreateRequest, OrderResponse

router = APIRouter(prefix="/orders", tags=["Order"])


@router.post("", response_model=OrderResponse)
async def place_order(
    req: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """주문 생성. 서버가 가격을 재검증합니다."""
    return await create_order(db, req)


@router.get("/{order_uuid}", response_model=OrderResponse)
async def read_order(order_uuid: str, db: AsyncSession = Depends(get_db)):
    """주문 조회."""
    result = await get_order_by_uuid(db, order_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result
