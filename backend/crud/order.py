"""순수 DB 접근 — 비즈니스 로직은 services/order_service.py로 이동"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from model import Order, OrderItem


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
    menu_name_snapshot: str,
    quantity: int,
    unit_price: int,
    line_total: int,
    from_recommendation: bool,
    selected_options_json: list[dict],
) -> OrderItem:
    item = OrderItem(
        order_id=order_id,
        menu_id=menu_id,
        menu_name_snapshot=menu_name_snapshot,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        from_recommendation=from_recommendation,
        selected_options_json=selected_options_json,
    )
    db.add(item)
    await db.flush()
    return item

async def get_order_by_uuid(db: AsyncSession, order_uuid: str) -> Optional[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.order_uuid == order_uuid)
        .options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()
