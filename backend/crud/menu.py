from typing import List, Optional, Tuple
from sqlalchemy import select, func, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu, Category, OptionGroup, OptionItem, MenuOptionGroup


# ─── Category ───

async def get_categories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[Category], int]:
    base = select(Category).order_by(Category.display_order)
    total = (await db.execute(select(func.count(Category.id)))).scalar() or 0
    rows = (await db.execute(base.offset(skip).limit(limit))).scalars().all()
    return list(rows), total


async def get_category_by_name(db: AsyncSession, name: str) -> Optional[Category]:
    result = await db.execute(select(Category).where(Category.name == name))
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, name: str, display_order: int = 0) -> Category:
    cat = Category(name=name, display_order=display_order)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


# ─── Menu ───

def _menu_row_to_dict(menu: Menu) -> dict:
    return {c.key: getattr(menu, c.key) for c in Menu.__table__.columns}


async def get_menus(
    db: AsyncSession,
    category_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> Tuple[List[dict], int]:
    base = select(Menu).where(Menu.is_available == True)
    count_q = select(func.count(Menu.id)).where(Menu.is_available == True)

    if category_name:
        base = base.where(Menu.category == category_name)
        count_q = count_q.where(Menu.category == category_name)

    sort_col = getattr(Menu, sort_by, Menu.name)
    base = base.order_by(asc(sort_col) if sort_order == "asc" else desc(sort_col))

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base.offset(skip).limit(limit))).scalars().all()
    return [_menu_row_to_dict(m) for m in rows], total


async def get_menu_by_name(db: AsyncSession, menu_name: str) -> Optional[Menu]:
    result = await db.execute(select(Menu).where(Menu.name == menu_name))
    return result.scalar_one_or_none()


async def get_menu_detail(db: AsyncSession, menu_name: str) -> Optional[dict]:
    """메뉴 상세 + 옵션 그룹/아이템 포함"""
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        return None

    # 옵션 그룹 조회
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
        **_menu_row_to_dict(menu),
        "option_groups": option_groups,
    }


async def create_menu(db: AsyncSession, data: dict) -> Menu:
    menu = Menu(**data)
    db.add(menu)
    await db.commit()
    await db.refresh(menu)
    return menu


# ─── Option ───

async def get_option_groups(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[OptionGroup], int]:
    total = (await db.execute(select(func.count(OptionGroup.id)))).scalar() or 0
    rows = (await db.execute(
        select(OptionGroup).order_by(OptionGroup.id).offset(skip).limit(limit)
    )).scalars().all()
    return list(rows), total


async def get_option_group_by_name(db: AsyncSession, name: str) -> Optional[OptionGroup]:
    result = await db.execute(select(OptionGroup).where(OptionGroup.name == name))
    return result.scalar_one_or_none()


async def get_option_group_with_items(db: AsyncSession, name: str) -> Optional[dict]:
    og = await get_option_group_by_name(db, name)
    if not og:
        return None
    items = (await db.execute(
        select(OptionItem).where(OptionItem.group_id == og.id)
    )).scalars().all()
    return {
        "id": og.id,
        "name": og.name,
        "is_required": og.is_required,
        "min_select": og.min_select,
        "max_select": og.max_select,
        "items": list(items),
    }


async def upsert_option_group(
    db: AsyncSession,
    name: str,
    is_required: bool,
    min_select: int,
    max_select: int,
    items: list,
) -> OptionGroup:
    """옵션 그룹 upsert + 아이템도 같이 upsert"""
    og = await get_option_group_by_name(db, name)
    if og:
        og.is_required = is_required
        og.min_select = min_select
        og.max_select = max_select
    else:
        og = OptionGroup(
            name=name,
            is_required=is_required,
            min_select=min_select,
            max_select=max_select,
        )
        db.add(og)
        await db.flush()

    # 기존 아이템 가져오기
    existing_items = (await db.execute(
        select(OptionItem).where(OptionItem.group_id == og.id)
    )).scalars().all()
    existing_by_name = {i.name: i for i in existing_items}

    for item_data in items:
        existing = existing_by_name.get(item_data["name"])
        if existing:
            existing.extra_price = item_data.get("extra_price", 0)
            existing.is_default = item_data.get("is_default", False)
            existing.is_available = item_data.get("is_available", True)
        else:
            db.add(OptionItem(group_id=og.id, **item_data))

    await db.commit()
    await db.refresh(og)
    return og


async def link_menu_option_group(
    db: AsyncSession,
    menu_id: int,
    option_group_id: int,
    display_order: int = 0,
) -> MenuOptionGroup:
    # 중복 연결 방지
    existing = (await db.execute(
        select(MenuOptionGroup).where(
            MenuOptionGroup.menu_id == menu_id,
            MenuOptionGroup.option_group_id == option_group_id,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    link = MenuOptionGroup(
        menu_id=menu_id,
        option_group_id=option_group_id,
        display_order=display_order,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def get_option_item_by_id(db: AsyncSession, option_item_id: int) -> Optional[OptionItem]:
    result = await db.execute(select(OptionItem).where(OptionItem.id == option_item_id))
    return result.scalar_one_or_none()
