from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu, Category


async def get_all_menus(db: AsyncSession, category_id: Optional[int] = None) -> List[Menu]:
    query = select(Menu).where(Menu.is_available == True)
    if category_id:
        query = query.where(Menu.category_id == category_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_menu_by_id(db: AsyncSession, menu_id: int) -> Optional[Menu]:
    result = await db.execute(select(Menu).where(Menu.id == menu_id))
    return result.scalar_one_or_none()


async def get_all_categories(db: AsyncSession) -> List[Category]:
    result = await db.execute(select(Category))
    return list(result.scalars().all())


async def get_category_by_name(db: AsyncSession, name: str) -> Optional[Category]:
    result = await db.execute(select(Category).where(Category.name == name))
    return result.scalar_one_or_none()


async def get_menus_by_category_name(db: AsyncSession, category_name: str) -> List[Menu]:
    category = await get_category_by_name(db, category_name)
    if not category:
        return []
    return await get_all_menus(db, category_id=category.id)
