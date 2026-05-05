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
    include_unavailable: bool = False,
) -> Tuple[list[dict[str, Any]], int]:
    base = select(Menu)
    count_q = select(func.count(Menu.id))

    if not include_unavailable:
        base = base.where(Menu.is_available == True)
        count_q = count_q.where(Menu.is_available == True)

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


async def get_menu_by_id(db: AsyncSession, menu_id: int) -> Optional[Menu]:
    result = await db.execute(select(Menu).where(Menu.id == menu_id))
    return result.scalar_one_or_none()


async def get_menu_detail(
    db: AsyncSession,
    menu_name: str,
    *,
    include_unavailable_options: bool = False,
) -> Optional[dict[str, Any]]:
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        return None

    stmt = select(MenuOption).where(MenuOption.menu_id == menu.id)
    if not include_unavailable_options:
        stmt = stmt.where(MenuOption.is_available == True)
    option_rows = (await db.execute(stmt)).scalars().all()

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


async def update_menu(db: AsyncSession, menu_id: int, data: dict[str, Any]) -> Optional[Menu]:
    menu = await get_menu_by_id(db, menu_id)
    if not menu:
        return None

    for field, value in data.items():
        setattr(menu, field, value)

    await db.commit()
    await db.refresh(menu)
    return menu


async def soft_delete_menu(db: AsyncSession, menu_id: int) -> Optional[Menu]:
    """메뉴를 숨김(`is_available=False`)으로 처리. 실제 row는 보존."""
    return await update_menu(db, menu_id, {"is_available": False})


async def soft_delete_option_group(
    db: AsyncSession,
    *,
    menu_id: int,
    group_name: str,
) -> int:
    """옵션 그룹의 모든 옵션 아이템을 `is_available=False`로 표시. 영향 받은 row 수 반환."""
    rows = (
        await db.execute(
            select(MenuOption).where(
                MenuOption.menu_id == menu_id,
                MenuOption.group_name == group_name,
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_available = False
    await db.commit()
    return len(rows)


async def replace_menu_option_groups(
    db: AsyncSession,
    *,
    menu: Menu,
    groups: list[dict[str, Any]],
) -> None:
    """메뉴 PATCH/POST의 인라인 옵션 편집용. 주어진 그룹 집합을 "정답"으로 간주하여
    - 새 그룹은 추가/갱신 (`upsert_option_group`)
    - 클라이언트가 보내지 않은 기존 그룹은 소프트 삭제 (`is_available=False`)
    빈 리스트가 들어오면 모든 기존 그룹이 비활성화된다 — 명시적 "전체 비움" 의미."""
    incoming_names = {g["name"] for g in groups if g.get("name")}

    existing_rows = (
        await db.execute(
            select(MenuOption.group_name)
            .where(MenuOption.menu_id == menu.id)
            .group_by(MenuOption.group_name)
        )
    ).all()
    existing_names = {row[0] for row in existing_rows}

    for stale_name in existing_names - incoming_names:
        await soft_delete_option_group(db, menu_id=menu.id, group_name=stale_name)

    for group in groups:
        await upsert_option_group(
            db,
            menu=menu,                # 이미 갖고 있는 Menu 객체 그대로 — 재조회 X
            menu_name=menu.name,
            name=group["name"],
            group_order=group.get("group_order", 0),
            is_required=group.get("is_required", True),
            min_select=group.get("min_select", 1),
            max_select=group.get("max_select", 1),
            items=group.get("items", []),
        )


async def get_option_groups(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    menu_name: Optional[str] = None,
) -> Tuple[list[dict[str, Any]], int]:
    stmt = (
        select(MenuOption)
        .where(MenuOption.is_available == True)
        .order_by(
            MenuOption.group_order,
            MenuOption.group_name,
            MenuOption.option_order,
            MenuOption.id,
        )
    )
    if menu_name:
        menu = await get_menu_by_name(db, menu_name)
        if not menu:
            return [], 0
        stmt = stmt.where(MenuOption.menu_id == menu.id)

    rows = (await db.execute(stmt)).scalars().all()
    groups = _group_menu_options(list(rows))
    total = len(groups)
    return groups[skip: skip + limit], total


async def get_option_group_with_items(
    db: AsyncSession,
    name: str,
    menu_name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    stmt = (
        select(MenuOption)
        .where(
            MenuOption.group_name == name,
            MenuOption.is_available == True,
        )
        .order_by(
            MenuOption.group_order,
            MenuOption.option_order,
            MenuOption.id,
        )
    )
    if menu_name:
        menu = await get_menu_by_name(db, menu_name)
        if not menu:
            return None
        stmt = stmt.where(MenuOption.menu_id == menu.id)

    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return None
    groups = _group_menu_options(list(rows))
    return groups[0] if groups else None


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
    menu: Optional[Menu] = None,
) -> Optional[dict[str, Any]]:
    """옵션 그룹 통째 교체. caller 가 이미 Menu 객체를 갖고 있으면 `menu=...` 로
    전달해 메뉴 재조회 round-trip 을 절약할 수 있다 (기본 동작은 menu_name 으로 lookup)."""
    if menu is None:
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


# ============================================================================
# Option catalog (전역 옵션 뷰) — 메뉴 단위 row를 (group_name, option_name)으로 집계
# ============================================================================


async def get_option_catalog(
    db: AsyncSession,
    *,
    include_unavailable: bool = True,
) -> list[dict[str, Any]]:
    """그룹/옵션 카탈로그. 같은 (group_name, option_name)이 여러 메뉴에 분포해 있는
    경우 사용 메뉴 목록과 평균 추가가격을 함께 반환."""
    stmt = (
        select(
            MenuOption.group_name,
            MenuOption.option_name,
            MenuOption.is_required,
            MenuOption.min_select,
            MenuOption.max_select,
            MenuOption.extra_price,
            MenuOption.menu_id,
            Menu.name.label("menu_name"),
        )
        .join(Menu, Menu.id == MenuOption.menu_id)
    )
    if not include_unavailable:
        stmt = stmt.where(MenuOption.is_available == True)
    rows = (await db.execute(stmt)).all()

    groups: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for r in rows:
        g = groups.setdefault(
            r.group_name,
            {
                "group_name": r.group_name,
                "is_required_votes": [],
                "min_votes": [],
                "max_votes": [],
                "items": OrderedDict(),
                "used_in_menus": {},
            },
        )
        g["is_required_votes"].append(bool(r.is_required))
        g["min_votes"].append(int(r.min_select))
        g["max_votes"].append(int(r.max_select))
        g["used_in_menus"][r.menu_id] = r.menu_name

        item = g["items"].setdefault(
            r.option_name,
            {
                "group_name": r.group_name,
                "option_name": r.option_name,
                "extra_prices": [],
                "used_in_menus": {},
            },
        )
        item["extra_prices"].append(int(r.extra_price))
        item["used_in_menus"][r.menu_id] = r.menu_name

    def mode(values: list) -> Any:
        if not values:
            return None
        counts: dict[Any, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return max(counts.items(), key=lambda kv: kv[1])[0]

    result = []
    for group in groups.values():
        items = []
        for item in group["items"].values():
            avg_price = round(sum(item["extra_prices"]) / len(item["extra_prices"]))
            items.append({
                "group_name": item["group_name"],
                "option_name": item["option_name"],
                "avg_extra_price": int(avg_price),
                "used_in_menus": [
                    {"id": mid, "name": name}
                    for mid, name in item["used_in_menus"].items()
                ],
            })
        result.append({
            "group_name": group["group_name"],
            "representative_min_select": int(mode(group["min_votes"]) or 1),
            "representative_max_select": int(mode(group["max_votes"]) or 1),
            "representative_is_required": bool(mode(group["is_required_votes"])
                                               if group["is_required_votes"] else True),
            "items": items,
            "used_in_menus": [
                {"id": mid, "name": name}
                for mid, name in group["used_in_menus"].items()
            ],
        })
    result.sort(key=lambda g: g["group_name"])
    return result
