from typing import List, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu, Category, OptionGroup, OptionItem, MenuOptionGroup


async def get_category(
    db: AsyncSession,
    category_name: Optional[str] = None,
    name: Optional[str] = None,
) -> Union[Optional[Category], List[Category]]:
    query = select(Category)
    if category_name is not None:
        query = query.where(Category.name == category_name)
    elif name is not None:
        query = query.where(Category.name == name)
    else:
        query = query.order_by(Category.display_order)
        return list((await db.execute(query)).scalars().all())
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_all_menus(db: AsyncSession, category_name: Optional[str] = None) -> List[dict]:
    """메뉴 목록 반환 (category_name 포함)"""
    query = select(
        Menu,
        Category.id.label("category_id"),
        Category.name.label("category_name"),
    ).join(
        Category, Menu.category == Category.name
    ).where(Menu.is_available == True)
    if category_name:
        query = query.where(Category.name == category_name) 
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            **{c.key: getattr(row[0], c.key) for c in Menu.__table__.columns},
            "category_id": row[1],
            "category_name": row[2],
        }
        for row in rows
    ]



async def search_menus(db: AsyncSession, name: str) -> List[dict]:
    """메뉴 이름 검색 (부분 일치)"""
    query = select(
        Menu,
        Category.id.label("category_id"),
        Category.name.label("category_name"),
    ).join(
        Category, Menu.category == Category.name
    ).where(Menu.is_available == True, Menu.name.contains(name))
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            **{c.key: getattr(row[0], c.key) for c in Menu.__table__.columns},
            "category_id": row[1],
            "category_name": row[2],
        }
        for row in rows
    ]

async def get_menu_by_name(db: AsyncSession, menu_name: str) -> Optional[Menu]:
    result = await db.execute(select(Menu).where(Menu.name == menu_name, Menu.is_available == True))
    return result.scalar_one_or_none()

async def get_menu_detail(db: AsyncSession, menu_name: str) -> Optional[dict]:
    """메뉴 상세 + 옵션 그룹/아이템 포함 + category_name 포함"""
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        return None

    # 카테고리 이름
    cat = await get_category(db, category_name=menu.category)
    category_name = cat.name if cat else ""

    # 옵션 그룹
    mog_result = await db.execute(
        select(MenuOptionGroup)
        .where(MenuOptionGroup.menu_id == menu.id)
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
        "category_id": cat.id if cat else 0,
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
