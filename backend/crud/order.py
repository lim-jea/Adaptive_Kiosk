"""순수 DB 접근 — 비즈니스 로직은 services/order_service.py로 이동"""
from datetime import datetime
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from model import KioskSession, Order, OrderItem


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


async def list_orders(
    db: AsyncSession,
    *,
    status: Optional[str] = None,
    kiosk_id: Optional[int] = None,
    used_recommendation: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Order], int]:
    base = select(Order).options(selectinload(Order.items))
    count_q = select(func.count(Order.id))

    if kiosk_id is not None:
        base = base.join(KioskSession, KioskSession.id == Order.session_id)
        count_q = count_q.join(KioskSession, KioskSession.id == Order.session_id)
        base = base.where(KioskSession.kiosk_id == kiosk_id)
        count_q = count_q.where(KioskSession.kiosk_id == kiosk_id)
    if status is not None:
        base = base.where(Order.status == status)
        count_q = count_q.where(Order.status == status)
    if used_recommendation is not None:
        base = base.where(Order.used_recommendation == used_recommendation)
        count_q = count_q.where(Order.used_recommendation == used_recommendation)
    if start_date is not None:
        base = base.where(Order.created_at >= start_date)
        count_q = count_q.where(Order.created_at >= start_date)
    if end_date is not None:
        base = base.where(Order.created_at < end_date)
        count_q = count_q.where(Order.created_at < end_date)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(Order.created_at.desc(), Order.id.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return list(rows), total
