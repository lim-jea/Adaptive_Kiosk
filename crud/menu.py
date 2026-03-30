from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu, Category, OptionGroup, OptionItem, MenuOptionGroup


async def get_all_categories(db: AsyncSession) -> List[Category]:
    result = await db.execute(select(Category).order_by(Category.display_order))
    return list(result.scalars().all())


async def get_category_by_id(db: AsyncSession, category_id: int) -> Optional[Category]:
    result = await db.execute(select(Category).where(Category.id == category_id))
    return result.scalar_one_or_none()


async def get_category_by_name(db: AsyncSession, name: str) -> Optional[Category]:
    result = await db.execute(select(Category).where(Category.name == name))
    return result.scalar_one_or_none()


async def get_all_menus(db: AsyncSession, category_id: Optional[int] = None) -> List[dict]:
    """메뉴 목록 반환 (category_name 포함)"""
    query = select(Menu, Category.name.label("category_name")).join(
        Category, Menu.category_id == Category.id
    ).where(Menu.is_available == True)
    if category_id:
        query = query.where(Menu.category_id == category_id)
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            **{c.key: getattr(row[0], c.key) for c in Menu.__table__.columns},
            "category_name": row[1],
        }
        for row in rows
    ]


async def get_menus_by_category_name(db: AsyncSession, category_name: str) -> List[dict]:
    category = await get_category_by_name(db, category_name)
    if not category:
        return []
    return await get_all_menus(db, category_id=category.id)


async def search_menus(db: AsyncSession, name: str) -> List[dict]:
    """메뉴 이름 검색 (부분 일치)"""
    query = select(Menu, Category.name.label("category_name")).join(
        Category, Menu.category_id == Category.id
    ).where(Menu.is_available == True, Menu.name.contains(name))
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            **{c.key: getattr(row[0], c.key) for c in Menu.__table__.columns},
            "category_name": row[1],
        }
        for row in rows
    ]


async def get_menu_by_id(db: AsyncSession, menu_id: int) -> Optional[Menu]:
    result = await db.execute(select(Menu).where(Menu.id == menu_id))
    return result.scalar_one_or_none()


async def get_menu_detail(db: AsyncSession, menu_id: int) -> Optional[dict]:
    """메뉴 상세 + 옵션 그룹/아이템 포함 + category_name 포함"""
    menu = await get_menu_by_id(db, menu_id)
    if not menu:
        return None

    # 카테고리 이름
    cat = await get_category_by_id(db, menu.category_id)
    category_name = cat.name if cat else ""

    # 옵션 그룹
    mog_result = await db.execute(
        select(MenuOptionGroup)
        .where(MenuOptionGroup.menu_id == menu_id)
        .order_by(MenuOptionGroup.display_order)
    )
    menu_option_groups = mog_result.scalars().all()

    option_groups = []
    for mog in menu_option_groups:
        og_result = await db.execute(
            select(OptionGroup).where(OptionGroup.id == mog.option_group_id)
        )
        og = og_result.scalar_one_or_none()
        if not og:
            continue
        oi_result = await db.execute(
            select(OptionItem)
            .where(OptionItem.group_id == og.id, OptionItem.is_available == True)
        )
        items = list(oi_result.scalars().all())
        option_groups.append({
            "id": og.id,
            "name": og.name,
            "is_required": og.is_required,
            "min_select": og.min_select,
            "max_select": og.max_select,
            "items": items,
        })

    return {
        "id": menu.id,
        "name": menu.name,
        "category_id": menu.category_id,
        "category_name": category_name,
        "price": menu.price,
        "emoji": menu.emoji,
        "cal": menu.cal,
        "temp": menu.temp,
        "description": menu.description,
        "image_url": menu.image_url,
        "is_available": menu.is_available,
        "option_groups": option_groups,
    }


async def get_option_item_by_id(db: AsyncSession, option_item_id: int) -> Optional[OptionItem]:
    result = await db.execute(select(OptionItem).where(OptionItem.id == option_item_id))
    return result.scalar_one_or_none()
