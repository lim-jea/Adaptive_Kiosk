from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.order import Order, OrderItem
from schemas.order import OrderCreate


async def create_order(db: AsyncSession, data: OrderCreate, total_time_seconds: Optional[int] = None) -> Order:
    order = Order(
        session_id=data.session_id,
        used_recommendation=data.used_recommendation,
        total_time_seconds=total_time_seconds,
    )
    db.add(order)
    await db.flush()

    for item in data.items:
        order_item = OrderItem(
            order_id=order.id,
            menu_id=item.menu_id,
            quantity=item.quantity,
            from_recommendation=item.from_recommendation,
        )
        db.add(order_item)

    await db.commit()
    await db.refresh(order)

    # items 관계 로드
    result = await db.execute(
        select(Order).where(Order.id == order.id).options(selectinload(Order.items))
    )
    return result.scalar_one()


async def get_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    result = await db.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()
