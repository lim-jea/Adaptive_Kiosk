from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Cart


def _empty_cart_data() -> dict:
    return {"items": []}


async def get_cart_by_session_id(db: AsyncSession, session_id: int) -> Cart | None:
    result = await db.execute(select(Cart).where(Cart.session_id == session_id))
    return result.scalar_one_or_none()


async def create_cart(db: AsyncSession, session_id: int) -> Cart:
    cart = Cart(session_id=session_id, cart_data=_empty_cart_data())
    db.add(cart)
    await db.flush()
    return cart


async def get_or_create_cart(db: AsyncSession, session_id: int) -> Cart:
    cart = await get_cart_by_session_id(db, session_id)
    if cart:
        return cart
    return await create_cart(db, session_id)
