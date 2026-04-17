"""주문 비즈니스 로직 - 가격 검증, 옵션 처리, 응답 구성"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Menu
from crud.menu import get_option_item_by_id
from crud.session import get_session_by_uuid, get_session_by_id
from crud import order as order_crud
from services.cart_service import calculate_unit_price, get_cart_items_for_checkout
from schemas import (
    OrderCreateRequest,
    OrderResponse,
    OrderItemResponse,
    OrderItemOptionResponse,
)
from schemas import make_error


async def create_order(db: AsyncSession, data: OrderCreateRequest) -> OrderResponse:
    session = await get_session_by_uuid(db, data.session_uuid)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "SESSION_NOT_FOUND", "Invalid session_uuid", session_uuid=data.session_uuid
            ),
        )

    cart = None
    if data.items:
        source_items = [
            {
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "from_recommendation": item.from_recommendation,
                "selected_option_ids": [opt.option_item_id for opt in item.selected_options],
            }
            for item in data.items
        ]
        used_recommendation = (
            data.used_recommendation
            if data.used_recommendation is not None
            else any(item["from_recommendation"] for item in source_items)
        )
    else:
        cart, cart_items = await get_cart_items_for_checkout(db, session.id)
        source_items = [
            {
                "menu_name": item["menu_name"],
                "quantity": item["quantity"],
                "from_recommendation": item.get("from_recommendation", False),
                "selected_option_ids": [
                    option["option_item_id"] for option in item.get("options", [])
                ],
            }
            for item in cart_items
        ]
        used_recommendation = (
            data.used_recommendation
            if data.used_recommendation is not None
            else cart.contains_recommendation_item
        )

    order = await order_crud.insert_order(
        db,
        session_id=session.id,
        total_price=0,
        used_recommendation=used_recommendation,
    )

    response_items = []
    total_price = 0

    for item in source_items:
        option_ids = item["selected_option_ids"]
        server_unit_price, menu = await calculate_unit_price(db, item["menu_name"], option_ids)

        selected_options_json = []
        option_responses = []
        for option_id in option_ids:
            oi = await get_option_item_by_id(db, option_id)
            if oi:
                selected_options_json.append(
                    {
                        "option_item_id": option_id,
                        "option_name": oi.option_name,
                        "extra_price": oi.extra_price,
                    }
                )
                option_responses.append(
                    OrderItemOptionResponse(option_name=oi.option_name, extra_price=oi.extra_price)
                )

        line_total = server_unit_price * item["quantity"]

        order_item = await order_crud.insert_order_item(
            db,
            order_id=order.id,
            menu_id=menu.id,
            menu_name_snapshot=menu.name,
            quantity=item["quantity"],
            unit_price=server_unit_price,
            line_total=line_total,
            from_recommendation=item["from_recommendation"],
            selected_options_json=selected_options_json,
        )

        total_price += line_total

        response_items.append(
            OrderItemResponse(
                id=order_item.id,
                menu_name=menu.name,
                quantity=item["quantity"],
                unit_price=server_unit_price,
                from_recommendation=item["from_recommendation"],
                options=option_responses,
            )
        )

    order.total_price = total_price
    if cart is not None:
        cart.status = "checked_out"
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
        option_snapshots = item.selected_options_json or []
        response_items.append(
            OrderItemResponse(
                id=item.id,
                menu_name=item.menu_name_snapshot or (menu.name if menu else ""),
                quantity=item.quantity,
                unit_price=item.unit_price,
                from_recommendation=item.from_recommendation,
                options=[
                    OrderItemOptionResponse(
                        option_name=option["option_name"],
                        extra_price=option["extra_price"],
                    )
                    for option in option_snapshots
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
