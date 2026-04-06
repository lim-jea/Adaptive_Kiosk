from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.order_service import create_order, get_order_response
from schemas.order import OrderCreateRequest, OrderResponse
from schemas.common import make_error

router = APIRouter(prefix="/orders", tags=["Order"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(
    req: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """주문 생성. 서버가 unit_price를 재계산하여 검증합니다."""
    return await create_order(db, req)


@router.get("/{order_uuid}", response_model=OrderResponse)
async def read_order(order_uuid: str, db: AsyncSession = Depends(get_db)):
    """주문 단건 조회."""
    result = await get_order_response(db, order_uuid)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("ORDER_NOT_FOUND", "Order not found", order_uuid=order_uuid),
        )
    return result
