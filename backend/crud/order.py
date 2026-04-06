"""순수 DB 접근 — 비즈니스 로직은 services/order_service.py로 이동"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.order import Order, OrderItem, OrderItemOption


async def insert_order(
    db: AsyncSession,
    session_id: int,
    total_price: int,
    used_recommendation: bool,
) -> Order:
    order = Order(
        session_id=session_id,
        used_recommendation=used_recommendation,
        total_price=total_price,
    )
    db.add(order)
    await db.flush()
    return order


async def insert_order_item(
    db: AsyncSession,
    order_id: int,
    menu_id: int,
    quantity: int,
    unit_price: int,
    from_recommendation: bool,
) -> OrderItem:
    item = OrderItem(
        order_id=order_id,
        menu_id=menu_id,
        quantity=quantity,
        unit_price=unit_price,
        from_recommendation=from_recommendation,
    )
    db.add(item)
    await db.flush()
    return item


async def insert_order_item_option(
    db: AsyncSession,
    order_item_id: int,
    option_item_id: int,
    option_name: str,
    extra_price: int,
) -> OrderItemOption:
    snapshot = OrderItemOption(
        order_item_id=order_item_id,
        option_item_id=option_item_id,
        option_name=option_name,
        extra_price=extra_price,
    )
    db.add(snapshot)
    return snapshot


async def get_order_by_uuid(db: AsyncSession, order_uuid: str) -> Optional[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.order_uuid == order_uuid)
        .options(selectinload(Order.items).selectinload(OrderItem.options))
    )
    return result.scalar_one_or_none()
