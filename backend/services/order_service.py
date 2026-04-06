"""주문 비즈니스 로직 — 가격 검증, 옵션 처리, 응답 구성"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu
from crud.menu import get_menu_by_name, get_option_item_by_id
from crud.session import get_session_by_uuid, get_session_by_id
from crud import order as order_crud
from schemas.order import (
    OrderCreateRequest,
    OrderResponse,
    OrderItemResponse,
    OrderItemOptionResponse,
)
from schemas.common import make_error


async def calculate_unit_price(db: AsyncSession, menu_name: str, option_item_ids: list[int]) -> tuple[int, "Menu"]:
    """서버 사이드 단가 재계산 + 메뉴 객체 반환"""
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        raise HTTPException(
            status_code=404,
            detail=make_error("MENU_NOT_FOUND", f"Menu '{menu_name}' not found", menu_name=menu_name),
        )
    if not menu.is_available:
        raise HTTPException(
            status_code=400,
            detail=make_error("MENU_NOT_AVAILABLE", f"Menu '{menu.name}' is not available"),
        )
    total = menu.price
    for oi_id in option_item_ids:
        oi = await get_option_item_by_id(db, oi_id)
        if not oi:
            raise HTTPException(
                status_code=400,
                detail=make_error(
                    "OPTION_NOT_FOUND",
                    f"Option item ID {oi_id} not found",
                    option_item_id=oi_id,
                ),
            )
        total += oi.extra_price
    return total, menu


async def create_order(db: AsyncSession, data: OrderCreateRequest) -> OrderResponse:
    session = await get_session_by_uuid(db, data.session_uuid)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "SESSION_NOT_FOUND", "Invalid session_uuid", session_uuid=data.session_uuid
            ),
        )

    order = await order_crud.insert_order(
        db, session_id=session.id, total_price=0, used_recommendation=data.used_recommendation
    )

    response_items = []
    total_price = 0

    for item in data.items:
        option_ids = [opt.option_item_id for opt in item.selected_options]
        server_unit_price, menu = await calculate_unit_price(db, item.menu_name, option_ids)

        order_item = await order_crud.insert_order_item(
            db,
            order_id=order.id,
            menu_id=menu.id,
            quantity=item.quantity,
            unit_price=server_unit_price,
            from_recommendation=item.from_recommendation,
        )

        option_responses = []
        for opt in item.selected_options:
            oi = await get_option_item_by_id(db, opt.option_item_id)
            if oi:
                await order_crud.insert_order_item_option(
                    db,
                    order_item_id=order_item.id,
                    option_item_id=oi.id,
                    option_name=oi.name,
                    extra_price=oi.extra_price,
                )
                option_responses.append(
                    OrderItemOptionResponse(option_name=oi.name, extra_price=oi.extra_price)
                )

        total_price += server_unit_price * item.quantity

        response_items.append(
            OrderItemResponse(
                id=order_item.id,
                menu_name=menu.name,
                quantity=item.quantity,
                unit_price=server_unit_price,
                from_recommendation=item.from_recommendation,
                options=option_responses,
            )
        )

    order.total_price = total_price
    await db.commit()
    await db.refresh(order)  # server_default 값 (created_at) 로드

    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=data.session_uuid,
        created_at=order.created_at,
        total_price=total_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=response_items,
    )


async def get_order_response(db: AsyncSession, order_uuid: str) -> OrderResponse | None:
    order = await order_crud.get_order_by_uuid(db, order_uuid)
    if not order:
        return None

    session = await get_session_by_id(db, order.session_id)
    session_uuid = session.session_uuid if session else ""

    response_items = []
    for item in order.items:
        menu_result = await db.execute(select(Menu).where(Menu.id == item.menu_id))
        menu = menu_result.scalar_one_or_none()
        response_items.append(
            OrderItemResponse(
                id=item.id,
                menu_name=menu.name if menu else "",
                quantity=item.quantity,
                unit_price=item.unit_price,
                from_recommendation=item.from_recommendation,
                options=[
                    OrderItemOptionResponse(option_name=o.option_name, extra_price=o.extra_price)
                    for o in item.options
                ],
            )
        )

    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=session_uuid,
        created_at=order.created_at,
        total_price=order.total_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=response_items,
    )
