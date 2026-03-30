from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.order import Order, OrderItem, OrderItemOption
from crud.menu import get_menu_by_id, get_option_item_by_id
from crud.session import get_session
from schemas.order import OrderCreateRequest, OrderItemResponse, OrderItemOptionResponse, OrderResponse


async def calculate_unit_price(db: AsyncSession, menu_id: int, option_item_ids: list[int]) -> int:
    """서버 사이드 단가 재계산"""
    menu = await get_menu_by_id(db, menu_id)
    if not menu:
        raise HTTPException(status_code=400, detail=f"Menu ID {menu_id} not found")
    if not menu.is_available:
        raise HTTPException(status_code=400, detail=f"Menu '{menu.name}' is not available")
    total = menu.price
    for oi_id in option_item_ids:
        oi = await get_option_item_by_id(db, oi_id)
        if not oi:
            raise HTTPException(status_code=400, detail=f"Option item ID {oi_id} not found")
        total += oi.extra_price
    return total


async def create_order(db: AsyncSession, data: OrderCreateRequest) -> OrderResponse:
    total_price = 0

    # session_uuid → 내부 session_id 변환
    session = await get_session(db, session_uuid=data.session_uuid)
    if not session:
        raise HTTPException(status_code=400, detail="Invalid session_uuid")

    order = Order(
        session_id=session.id,
        used_recommendation=data.used_recommendation,
        total_price=0,
    )
    db.add(order)
    await db.flush()

    response_items = []

    for item in data.items:
        option_ids = [opt.option_item_id for opt in item.selected_options]
        server_unit_price = await calculate_unit_price(db, item.menu_id, option_ids)

        # 메뉴 이름 조회
        menu = await get_menu_by_id(db, item.menu_id)

        order_item = OrderItem(
            order_id=order.id,
            menu_id=item.menu_id,
            quantity=item.quantity,
            unit_price=server_unit_price,
            from_recommendation=item.from_recommendation,
        )
        db.add(order_item)
        await db.flush()

        # 옵션 스냅샷 저장 + 응답 구성
        option_responses = []
        for opt in item.selected_options:
            oi = await get_option_item_by_id(db, opt.option_item_id)
            if oi:
                snapshot = OrderItemOption(
                    order_item_id=order_item.id,
                    option_item_id=oi.id,
                    option_name=oi.name,
                    extra_price=oi.extra_price,
                )
                db.add(snapshot)
                option_responses.append(OrderItemOptionResponse(
                    option_name=oi.name,
                    extra_price=oi.extra_price,
                ))

        total_price += server_unit_price * item.quantity

        response_items.append(OrderItemResponse(
            id=order_item.id,
            menu_id=item.menu_id,
            menu_name=menu.name if menu else "",
            quantity=item.quantity,
            unit_price=server_unit_price,
            from_recommendation=item.from_recommendation,
            options=option_responses,
        ))

    order.total_price = total_price
    await db.commit()

    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=data.session_uuid,
        created_at=order.created_at,
        total_price=total_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=response_items,
    )


async def get_order_by_uuid(db: AsyncSession, order_uuid: str) -> Optional[OrderResponse]:
    result = await db.execute(
        select(Order)
        .where(Order.order_uuid == order_uuid)
        .options(selectinload(Order.items).selectinload(OrderItem.options))
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    # session_uuid 조회
    from crud.session import get_session
    session = await get_session(db, order.session_id)
    session_uuid = session.session_uuid if session else ""

    response_items = []
    for item in order.items:
        menu = await get_menu_by_id(db, item.menu_id)
        response_items.append(OrderItemResponse(
            id=item.id,
            menu_id=item.menu_id,
            menu_name=menu.name if menu else "",
            quantity=item.quantity,
            unit_price=item.unit_price,
            from_recommendation=item.from_recommendation,
            options=[
                OrderItemOptionResponse(option_name=o.option_name, extra_price=o.extra_price)
                for o in item.options
            ],
        ))

    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=session_uuid,
        created_at=order.created_at,
        total_price=order.total_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=response_items,
    )
