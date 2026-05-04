from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.enums import OrderStatus
from core.security import verify_credentials
from services.order_service import create_order, get_order_response, list_order_responses
from schemas import OrderCreateRequest, OrderResponse, PaginatedResponse, make_error

router = APIRouter(prefix="/orders", tags=["Order"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(
    req: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """주문 생성. 서버가 unit_price를 재계산하여 검증합니다."""
    return await create_order(db, req)


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def list_orders_endpoint(
    order_status: OrderStatus | None = Query(None, alias="status"),
    kiosk_id: int | None = Query(None),
    used_recommendation: bool | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """주문 목록. 상태/키오스크/추천사용/기간 필터 + 페이지네이션. 관리자 인증 필요."""
    items, total = await list_order_responses(
        db,
        status=order_status.value if order_status else None,
        kiosk_id=kiosk_id,
        used_recommendation=used_recommendation,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


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
