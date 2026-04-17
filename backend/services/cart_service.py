import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from crud.cart import get_or_create_cart
from crud.menu import get_menu_by_name, get_option_item_by_id
from crud.session import get_session_by_uuid
from model import Cart, Menu
from schemas import (
    CartItemRequest,
    CartItemResponse,
    CartOptionResponse,
    CartReplaceRequest,
    CartResponse,
    make_error,
)


def _empty_cart_data() -> dict:
    return {"items": []}


async def calculate_unit_price(
    db: AsyncSession,
    menu_name: str,
    option_item_ids: list[int],
) -> tuple[int, Menu]:
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
    for option_item_id in option_item_ids:
        option = await get_option_item_by_id(db, option_item_id)
        if not option:
            raise HTTPException(
                status_code=400,
                detail=make_error(
                    "OPTION_NOT_FOUND",
                    f"Option item ID {option_item_id} not found",
                    option_item_id=option_item_id,
                ),
            )
        if option.menu_id != menu.id:
            raise HTTPException(
                status_code=400,
                detail=make_error(
                    "OPTION_MENU_MISMATCH",
                    f"Option item ID {option_item_id} does not belong to menu '{menu.name}'",
                    option_item_id=option_item_id,
                    menu_name=menu.name,
                ),
            )
        if not option.is_available:
            raise HTTPException(
                status_code=400,
                detail=make_error(
                    "OPTION_NOT_AVAILABLE",
                    f"Option item ID {option_item_id} is not available",
                    option_item_id=option_item_id,
                ),
            )
        total += option.extra_price

    return total, menu


async def _get_session_or_404(db: AsyncSession, session_uuid: str):
    session = await get_session_by_uuid(db, session_uuid)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=make_error("SESSION_NOT_FOUND", "Invalid session_uuid", session_uuid=session_uuid),
        )
    return session


async def _build_cart_item(db: AsyncSession, item: CartItemRequest) -> dict:
    option_ids = [option.option_item_id for option in item.selected_options]
    unit_price, menu = await calculate_unit_price(db, item.menu_name, option_ids)

    options = []
    for option_id in option_ids:
        option = await get_option_item_by_id(db, option_id)
        if option is None:
            continue
        options.append(
            {
                "option_item_id": option.id,
                "option_name": option.option_name,
                "extra_price": option.extra_price,
            }
        )

    return {
        "line_id": uuid.uuid4().hex,
        "menu_id": menu.id,
        "menu_name": menu.name,
        "quantity": item.quantity,
        "unit_price": unit_price,
        "line_total": unit_price * item.quantity,
        "from_recommendation": item.from_recommendation,
        "options": options,
    }


def _summarize_items(items: list[dict]) -> dict:
    return {
        "item_count": len(items),
        "total_quantity": sum(int(item.get("quantity", 0)) for item in items),
        "total_price": sum(int(item.get("line_total", 0)) for item in items),
        "contains_recommendation_item": any(bool(item.get("from_recommendation")) for item in items),
    }


def _serialize_cart(cart: Cart, session_uuid: str) -> CartResponse:
    cart_data = cart.cart_data or _empty_cart_data()
    items = [
        CartItemResponse(
            line_id=item["line_id"],
            menu_id=item["menu_id"],
            menu_name=item["menu_name"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
            from_recommendation=item.get("from_recommendation", False),
            options=[
                CartOptionResponse(
                    option_item_id=option["option_item_id"],
                    option_name=option["option_name"],
                    extra_price=option["extra_price"],
                )
                for option in item.get("options", [])
            ],
        )
        for item in cart_data.get("items", [])
    ]

    return CartResponse(
        session_uuid=session_uuid,
        status=cart.status,
        item_count=cart.item_count,
        total_quantity=cart.total_quantity,
        total_price=cart.total_price,
        contains_recommendation_item=cart.contains_recommendation_item,
        items=items,
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


async def ensure_cart_for_session(db: AsyncSession, session_id: int) -> Cart:
    cart = await get_or_create_cart(db, session_id)
    await db.commit()
    await db.refresh(cart)
    return cart


async def get_cart_response(db: AsyncSession, session_uuid: str) -> CartResponse:
    session = await _get_session_or_404(db, session_uuid)
    cart = await get_or_create_cart(db, session.id)
    await db.commit()
    await db.refresh(cart)
    return _serialize_cart(cart, session.session_uuid)


async def replace_cart(db: AsyncSession, session_uuid: str, payload: CartReplaceRequest) -> CartResponse:
    session = await _get_session_or_404(db, session_uuid)
    cart = await get_or_create_cart(db, session.id)

    items = [await _build_cart_item(db, item) for item in payload.items]
    summary = _summarize_items(items)

    cart.status = "active"
    cart.item_count = summary["item_count"]
    cart.total_quantity = summary["total_quantity"]
    cart.total_price = summary["total_price"]
    cart.contains_recommendation_item = summary["contains_recommendation_item"]
    cart.cart_data = {"items": items}

    await db.commit()
    await db.refresh(cart)
    return _serialize_cart(cart, session.session_uuid)


async def clear_cart(db: AsyncSession, session_uuid: str) -> CartResponse:
    session = await _get_session_or_404(db, session_uuid)
    cart = await get_or_create_cart(db, session.id)

    cart.status = "active"
    cart.item_count = 0
    cart.total_quantity = 0
    cart.total_price = 0
    cart.contains_recommendation_item = False
    cart.cart_data = _empty_cart_data()

    await db.commit()
    await db.refresh(cart)
    return _serialize_cart(cart, session.session_uuid)


async def get_cart_items_for_checkout(db: AsyncSession, session_id: int) -> tuple[Cart, list[dict]]:
    cart = await get_or_create_cart(db, session_id)
    items = (cart.cart_data or _empty_cart_data()).get("items", [])
    if not items:
        raise HTTPException(
            status_code=400,
            detail=make_error("CART_EMPTY", "Cart is empty"),
        )
    return cart, items
