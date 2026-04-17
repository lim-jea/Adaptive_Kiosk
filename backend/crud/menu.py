from collections import OrderedDict
from typing import Any, Optional, Tuple

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Menu, MenuOption


_CATEGORY_DISPLAY_ORDER = {
    "커피": 1,
    "달콤한커피": 2,
    "블렌디드": 3,
    "티": 4,
    "달콤한티": 5,
    "에이드": 6,
    "스무디": 7,
    "주스": 8,
}


def _menu_row_to_dict(menu: Menu) -> dict[str, Any]:
    return {c.key: getattr(menu, c.key) for c in Menu.__table__.columns}


def _category_to_dict(name: str) -> dict[str, Any]:
    display_order = _CATEGORY_DISPLAY_ORDER.get(name, 999)
    return {
        "id": display_order,
        "name": name,
        "display_order": display_order,
    }


def _group_menu_options(options: list[MenuOption]) -> list[dict[str, Any]]:
    groups: "OrderedDict[tuple[str, int], dict[str, Any]]" = OrderedDict()

    sorted_options = sorted(
        options,
        key=lambda row: (row.group_order, row.group_name, row.option_order, row.id),
    )

    for row in sorted_options:
        key = (row.group_name, row.group_order)
        if key not in groups:
            groups[key] = {
                "id": len(groups) + 1,
                "name": row.group_name,
                "is_required": row.is_required,
                "min_select": row.min_select,
                "max_select": row.max_select,
                "items": [],
                "_seen_item_keys": set(),
            }

        item_key = (row.option_name, row.extra_price, row.is_default, row.is_available)
        if item_key in groups[key]["_seen_item_keys"]:
            continue
        groups[key]["_seen_item_keys"].add(item_key)
        groups[key]["items"].append(
            {
                "id": row.id,
                "name": row.option_name,
                "extra_price": row.extra_price,
                "is_default": row.is_default,
                "is_available": row.is_available,
            }
        )

    return [
        {
            "id": group["id"],
            "name": group["name"],
            "is_required": group["is_required"],
            "min_select": group["min_select"],
            "max_select": group["max_select"],
            "items": group["items"],
        }
        for group in groups.values()
    ]


async def get_categories(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[list[dict[str, Any]], int]:
    result = await db.execute(
        select(Menu.category)
        .where(Menu.is_available == True)
        .group_by(Menu.category)
    )
    names = [row[0] for row in result.all() if row[0]]
    items = sorted((_category_to_dict(name) for name in names), key=lambda item: (item["display_order"], item["name"]))
    total = len(items)
    return items[skip: skip + limit], total


async def get_menus(
    db: AsyncSession,
    category_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> Tuple[list[dict[str, Any]], int]:
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


async def get_menu_detail(db: AsyncSession, menu_name: str) -> Optional[dict[str, Any]]:
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        return None

    option_rows = (
        await db.execute(
            select(MenuOption)
            .where(MenuOption.menu_id == menu.id, MenuOption.is_available == True)
        )
    ).scalars().all()

    return {
        **_menu_row_to_dict(menu),
        "option_groups": _group_menu_options(list(option_rows)),
    }


async def create_menu(db: AsyncSession, data: dict[str, Any]) -> Menu:
    menu = Menu(**data)
    db.add(menu)
    await db.commit()
    await db.refresh(menu)
    return menu


async def get_option_groups(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    menu_name: Optional[str] = None,
) -> Tuple[list[dict[str, Any]], int]:
    if menu_name:
        detail = await get_menu_detail(db, menu_name)
        if not detail:
            return [], 0
        groups = detail["option_groups"]
        return groups[skip: skip + limit], len(groups)

    rows = (
        await db.execute(
            select(MenuOption)
            .where(MenuOption.is_available == True)
            .order_by(MenuOption.group_order, MenuOption.group_name, MenuOption.option_order, MenuOption.id)
        )
    ).scalars().all()

    groups = _group_menu_options(list(rows))
    total = len(groups)
    return groups[skip: skip + limit], total


async def get_option_group_with_items(
    db: AsyncSession,
    name: str,
    menu_name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    groups, _ = await get_option_groups(db, menu_name=menu_name, skip=0, limit=1000)
    for group in groups:
        if group["name"] == name:
            return group
    return None


async def upsert_option_group(
    db: AsyncSession,
    *,
    menu_name: str,
    name: str,
    group_order: int,
    is_required: bool,
    min_select: int,
    max_select: int,
    items: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        return None

    existing_rows = (
        await db.execute(
            select(MenuOption).where(
                MenuOption.menu_id == menu.id,
                MenuOption.group_name == name,
            )
        )
    ).scalars().all()

    for row in existing_rows:
        await db.delete(row)
    await db.flush()

    for index, item in enumerate(items):
        db.add(
            MenuOption(
                menu_id=menu.id,
                group_name=name,
                group_order=group_order,
                option_name=item["name"],
                option_order=item.get("option_order", index),
                extra_price=item.get("extra_price", 0),
                is_required=is_required,
                min_select=min_select,
                max_select=max_select,
                is_default=item.get("is_default", False),
                is_available=item.get("is_available", True),
            )
        )

    await db.commit()
    return await get_option_group_with_items(db, name, menu_name=menu_name)


async def get_option_item_by_id(db: AsyncSession, option_item_id: int) -> Optional[MenuOption]:
    result = await db.execute(select(MenuOption).where(MenuOption.id == option_item_id))
    return result.scalar_one_or_none()
