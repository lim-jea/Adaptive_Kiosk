"""
메뉴 + 메뉴 옵션 초기 데이터를 DB에 삽입한다.

서버 시작 시 호출되며 아래를 수행한다.
1. 새 구조에 맞는 누락 테이블을 create_all 이후 채운다.
2. 레거시 option_groups/option_items/menu_option_groups 데이터가 있으면 menu_options로 이관한다.
3. 완전한 빈 DB라면 기본 메뉴/옵션 시드를 넣는다.
"""
import json
import logging

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from model import Menu, MenuOption

logger = logging.getLogger(__name__)

MENUS = [
    {"name": "에스프레소", "category": "커피", "price": 4000, "icon_emoji": "☕", "calories": 5, "serving_temperature": "hot", "is_caffeinated": True},
    {"name": "따뜻한 아메리카노", "category": "커피", "price": 4500, "icon_emoji": "☕", "calories": 10, "serving_temperature": "hot", "is_caffeinated": True},
    {"name": "아이스 아메리카노", "category": "커피", "price": 4500, "icon_emoji": "☕", "calories": 10, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "따뜻한 카페라떼", "category": "커피", "price": 5200, "icon_emoji": "🥛", "calories": 120, "serving_temperature": "hot", "is_caffeinated": True},
    {"name": "아이스 카페라떼", "category": "커피", "price": 5200, "icon_emoji": "🥛", "calories": 110, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "카푸치노", "category": "커피", "price": 5200, "icon_emoji": "☕", "calories": 100, "serving_temperature": "hot", "is_caffeinated": True},
    {"name": "콜드브루", "category": "커피", "price": 5200, "icon_emoji": "🖤", "calories": 10, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "콜드브루 라떼", "category": "커피", "price": 5800, "icon_emoji": "🖤", "calories": 110, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "드립 커피", "category": "커피", "price": 5000, "icon_emoji": "☕", "calories": 10, "serving_temperature": "hot", "is_caffeinated": True},
    {"name": "바닐라 라떼", "category": "달콤한커피", "price": 5900, "icon_emoji": "🍦", "calories": 200, "serving_temperature": "both", "is_caffeinated": True},
    {"name": "카라멜 마끼아또", "category": "달콤한커피", "price": 6200, "icon_emoji": "🍮", "calories": 250, "serving_temperature": "both", "is_caffeinated": True},
    {"name": "프라푸치노", "category": "블렌디드", "price": 6500, "icon_emoji": "🍫", "calories": 350, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "말차 프라페", "category": "블렌디드", "price": 6300, "icon_emoji": "🍵", "calories": 300, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "녹차 라떼", "category": "티", "price": 5800, "icon_emoji": "🍵", "calories": 160, "serving_temperature": "both", "is_caffeinated": True},
    {"name": "캐모마일 티", "category": "티", "price": 4900, "icon_emoji": "🌼", "calories": 5, "serving_temperature": "hot", "is_caffeinated": False},
    {"name": "복숭아 아이스티", "category": "달콤한티", "price": 5200, "icon_emoji": "🍑", "calories": 80, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "자몽 허니 블랙 티", "category": "달콤한티", "price": 5700, "icon_emoji": "🍊", "calories": 90, "serving_temperature": "cold", "is_caffeinated": True},
    {"name": "레몬에이드", "category": "에이드", "price": 6000, "icon_emoji": "🍋", "calories": 120, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "자몽에이드", "category": "에이드", "price": 6200, "icon_emoji": "🍊", "calories": 110, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "딸기 스무디", "category": "스무디", "price": 6500, "icon_emoji": "🍓", "calories": 260, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "망고 스무디", "category": "스무디", "price": 6500, "icon_emoji": "🥭", "calories": 250, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "오렌지 주스", "category": "주스", "price": 5800, "icon_emoji": "🍊", "calories": 110, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "카페모카", "category": "달콤한커피", "price": 6200, "icon_emoji": "🍫", "calories": 290, "serving_temperature": "both", "is_caffeinated": True},
    {"name": "블루레몬 에이드", "category": "에이드", "price": 6000, "icon_emoji": "💙", "calories": 130, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "초코 라떼", "category": "블렌디드", "price": 6300, "icon_emoji": "🍫", "calories": 320, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "딸기 라떼", "category": "블렌디드", "price": 6300, "icon_emoji": "🍓", "calories": 280, "serving_temperature": "cold", "is_caffeinated": False},
    {"name": "유자차", "category": "달콤한티", "price": 5400, "icon_emoji": "🍋", "calories": 120, "serving_temperature": "both", "is_caffeinated": False},
    {"name": "자몽차", "category": "달콤한티", "price": 5500, "icon_emoji": "🍊", "calories": 110, "serving_temperature": "both", "is_caffeinated": False},
    {"name": "레몬차", "category": "달콤한티", "price": 5400, "icon_emoji": "🍋", "calories": 100, "serving_temperature": "both", "is_caffeinated": False},
    {"name": "얼그레이 티", "category": "달콤한티", "price": 5400, "icon_emoji": "🫖", "calories": 5, "serving_temperature": "both", "is_caffeinated": True},
    {"name": "페퍼민트 티", "category": "달콤한티", "price": 5400, "icon_emoji": "🌿", "calories": 5, "serving_temperature": "hot", "is_caffeinated": False},
    {"name": "요거트 스무디", "category": "스무디", "price": 6500, "icon_emoji": "🥛", "calories": 240, "serving_temperature": "cold", "is_caffeinated": False},
]

OPTION_GROUPS = [
    {
        "name": "사이즈",
        "is_required": True,
        "min_select": 1,
        "max_select": 1,
        "items": [
            {"name": "Tall", "extra_price": 0, "is_default": True},
            {"name": "Grande", "extra_price": 500, "is_default": False},
            {"name": "Venti", "extra_price": 1000, "is_default": False},
        ],
    },
    {
        "name": "온도",
        "is_required": True,
        "min_select": 1,
        "max_select": 1,
        "items": [
            {"name": "HOT", "extra_price": 0, "is_default": True},
            {"name": "ICE", "extra_price": 0, "is_default": False},
        ],
    },
    {
        "name": "샷 추가",
        "is_required": False,
        "min_select": 0,
        "max_select": 3,
        "items": [
            {"name": "샷 추가 (+1)", "extra_price": 500, "is_default": False},
        ],
    },
    {
        "name": "시럽",
        "is_required": False,
        "min_select": 0,
        "max_select": 2,
        "items": [
            {"name": "바닐라 시럽", "extra_price": 300, "is_default": False},
            {"name": "헤이즐넛 시럽", "extra_price": 300, "is_default": False},
            {"name": "카라멜 시럽", "extra_price": 300, "is_default": False},
        ],
    },
    {
        "name": "휘핑크림",
        "is_required": False,
        "min_select": 0,
        "max_select": 1,
        "items": [
            {"name": "휘핑크림 추가", "extra_price": 500, "is_default": False},
        ],
    },
    {
        "name": "당도",
        "is_required": False,
        "min_select": 0,
        "max_select": 1,
        "items": [
            {"name": "기본", "extra_price": 0, "is_default": True},
            {"name": "덜 달게", "extra_price": 0, "is_default": False},
            {"name": "더 달게", "extra_price": 0, "is_default": False},
        ],
    },
]

CATEGORY_OPTION_MAP = {
    "커피": ["사이즈", "샷 추가", "시럽"],
    "달콤한커피": ["사이즈", "온도", "샷 추가", "시럽"],
    "블렌디드": ["사이즈", "휘핑크림", "당도"],
    "티": ["사이즈", "온도", "당도"],
    "달콤한티": ["사이즈", "당도"],
    "에이드": ["사이즈", "당도"],
    "스무디": ["사이즈", "당도"],
    "주스": ["사이즈", "당도"],
}

_OPTION_GROUPS_BY_NAME = {group["name"]: group for group in OPTION_GROUPS}

MENU_IMAGES = {
    "에스프레소": "https://images.unsplash.com/photo-1510707577719-ae7c14805e3a?w=400&h=400&fit=crop&auto=format",
    "따뜻한 아메리카노": "https://images.unsplash.com/photo-1504630083234-14187a9df0f5?w=400&h=400&fit=crop&auto=format",
    "아이스 아메리카노": "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400&h=400&fit=crop&auto=format",
    "따뜻한 카페라떼": "https://images.unsplash.com/photo-1561047029-3000c68339ca?w=400&h=400&fit=crop&auto=format",
    "아이스 카페라떼": "https://images.unsplash.com/photo-1578314675249-a6910f80cc4e?w=400&h=400&fit=crop&auto=format",
    "카푸치노": "https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=400&h=400&fit=crop&auto=format",
    "콜드브루": "https://images.unsplash.com/photo-1548546738-8509cb246ed3?w=400&h=400&fit=crop&auto=format",
    "콜드브루 라떼": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=400&h=400&fit=crop&auto=format",
    "드립 커피": "https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=400&h=400&fit=crop&auto=format",
    "바닐라 라떼": "https://images.unsplash.com/photo-1485808191679-5f86510bd652?w=400&h=400&fit=crop&auto=format",
    "카라멜 마끼아또": "https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=400&h=400&fit=crop&auto=format",
    "프라푸치노": "https://images.unsplash.com/photo-1455951673516-95f09e43d8bc?w=400&h=400&fit=crop&auto=format",
    "말차 프라페": "https://images.unsplash.com/photo-1515823064-d6e0c04616a7?w=400&h=400&fit=crop&auto=format",
    "녹차 라떼": "https://images.unsplash.com/photo-1536256263959-770b48d82b0a?w=400&h=400&fit=crop&auto=format",
    "캐모마일 티": "https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9?w=400&h=400&fit=crop&auto=format",
    "복숭아 아이스티": "https://images.unsplash.com/photo-1499638673689-79a0b5115d87?w=400&h=400&fit=crop&auto=format",
    "자몽 허니 블랙 티": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop&auto=format",
    "레몬에이드": "https://images.unsplash.com/photo-1523371054106-bbf80586c38c?w=400&h=400&fit=crop&auto=format",
    "자몽에이드": "https://images.unsplash.com/photo-1497534446932-c925b458314e?w=400&h=400&fit=crop&auto=format",
    "딸기 스무디": "https://images.unsplash.com/photo-1570696516188-ade861b84a49?w=400&h=400&fit=crop&auto=format",
    "망고 스무디": "https://images.unsplash.com/photo-1589733955941-5eeaf752f6dd?w=400&h=400&fit=crop&auto=format",
    "오렌지 주스": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=400&h=400&fit=crop&auto=format",
    "카페모카": "https://images.unsplash.com/photo-1579888944880-d98341245702?w=400&h=400&fit=crop&auto=format",
    "블루레몬 에이드": "https://images.unsplash.com/photo-1556881286-fc6915169721?w=400&h=400&fit=crop&auto=format",
    "초코 라떼": "https://images.unsplash.com/photo-1517578239113-b03992dcdd25?w=400&h=400&fit=crop&auto=format",
    "딸기 라떼": "https://images.unsplash.com/photo-1586917049352-1c1f9b1f1d62?w=400&h=400&fit=crop&auto=format",
    "유자차": "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?w=400&h=400&fit=crop&auto=format",
    "자몽차": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400&h=400&fit=crop&auto=format",
    "레몬차": "https://images.unsplash.com/photo-1556881286-fc6915169721?w=400&h=400&fit=crop&auto=format",
    "얼그레이 티": "https://images.unsplash.com/photo-1597318181409-cf64d0b5d8a2?w=400&h=400&fit=crop&auto=format",
    "페퍼민트 티": "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?w=400&h=400&fit=crop&auto=format",
    "요거트 스무디": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop&auto=format",
}


async def _get_table_names(db: AsyncSession) -> list[str]:
    conn = await db.connection()
    return await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())


async def _get_foreign_keys(db: AsyncSession, table_name: str) -> list[dict]:
    conn = await db.connection()
    return await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_foreign_keys(table_name))


async def _get_columns(db: AsyncSession, table_name: str) -> list[dict]:
    conn = await db.connection()
    return await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns(table_name))


async def _drop_foreign_key(db: AsyncSession, table_name: str, fk_name: str) -> None:
    conn = await db.connection()
    dialect = conn.dialect.name
    if dialect.startswith("mysql"):
        sql = f"ALTER TABLE {table_name} DROP FOREIGN KEY {fk_name}"
    elif dialect == "postgresql":
        sql = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{fk_name}"'
    else:
        logger.info("Skipping FK drop for unsupported dialect: %s", dialect)
        return
    await db.execute(text(sql))


async def _add_column_if_missing(
    db: AsyncSession,
    table_name: str,
    existing_columns: set[str],
    column_name: str,
    column_sql: str,
) -> bool:
    if column_name in existing_columns:
        return False
    await db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))
    return True


async def _drop_legacy_foreign_keys(db: AsyncSession, tables: set[str]) -> None:
    if "menus" in tables:
        for fk in await _get_foreign_keys(db, "menus"):
            if fk.get("referred_table") == "categories" and fk.get("constrained_columns") == ["category"]:
                name = fk.get("name")
                if name:
                    logger.info("Dropping legacy foreign key menus.category -> categories.name (%s)", name)
                    await _drop_foreign_key(db, "menus", name)

    if "order_item_options" in tables:
        for fk in await _get_foreign_keys(db, "order_item_options"):
            if fk.get("constrained_columns") == ["option_item_id"]:
                name = fk.get("name")
                if name:
                    logger.info("Dropping legacy foreign key order_item_options.option_item_id (%s)", name)
                    await _drop_foreign_key(db, "order_item_options", name)

    await db.commit()


async def _migrate_order_item_snapshots(db: AsyncSession, tables: set[str]) -> None:
    if "order_items" not in tables:
        return

    columns = {column["name"] for column in await _get_columns(db, "order_items")}
    changed = False

    conn = await db.connection()
    dialect = conn.dialect.name
    json_sql = "JSON"
    if dialect == "postgresql":
        json_sql = "JSONB"

    changed |= await _add_column_if_missing(
        db,
        "order_items",
        columns,
        "menu_name_snapshot",
        "VARCHAR(100) NULL",
    )
    changed |= await _add_column_if_missing(
        db,
        "order_items",
        columns,
        "line_total",
        "INTEGER NULL",
    )
    changed |= await _add_column_if_missing(
        db,
        "order_items",
        columns,
        "selected_options_json",
        f"{json_sql} NULL",
    )
    if changed:
        await db.commit()

    item_rows = (
        await db.execute(
            text(
                """
                SELECT oi.id, oi.menu_name_snapshot, oi.line_total, oi.unit_price, oi.quantity, m.name AS menu_name
                FROM order_items AS oi
                LEFT JOIN menus AS m ON m.id = oi.menu_id
                """
            )
        )
    ).mappings().all()

    for row in item_rows:
        updates: dict[str, object] = {}
        if row["menu_name_snapshot"] is None and row["menu_name"] is not None:
            updates["menu_name_snapshot"] = str(row["menu_name"])
        if row["line_total"] is None:
            updates["line_total"] = int(row["unit_price"] or 0) * int(row["quantity"] or 0)
        if updates:
            await db.execute(
                text(
                    """
                    UPDATE order_items
                    SET
                        menu_name_snapshot = COALESCE(:menu_name_snapshot, menu_name_snapshot),
                        line_total = COALESCE(:line_total, line_total)
                    WHERE id = :order_item_id
                    """
                ),
                {
                    "order_item_id": int(row["id"]),
                    "menu_name_snapshot": updates.get("menu_name_snapshot"),
                    "line_total": updates.get("line_total"),
                },
            )

    if "order_item_options" in tables:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT order_item_id, option_item_id, option_name, extra_price
                    FROM order_item_options
                    ORDER BY id
                    """
                )
            )
        ).mappings().all()

        grouped: dict[int, list[dict]] = {}
        for row in rows:
            grouped.setdefault(int(row["order_item_id"]), []).append(
                {
                    "option_item_id": int(row["option_item_id"]),
                    "option_name": str(row["option_name"]),
                    "extra_price": int(row["extra_price"] or 0),
                }
            )

        for order_item_id, options in grouped.items():
            serialized = json.dumps(options, ensure_ascii=False)
            await db.execute(
                text(
                    """
                    UPDATE order_items
                    SET selected_options_json = COALESCE(selected_options_json, :selected_options_json)
                    WHERE id = :order_item_id
                    """
                ),
                {
                    "order_item_id": order_item_id,
                    "selected_options_json": serialized,
                },
            )

    await db.execute(
        text(
            """
            UPDATE order_items
            SET selected_options_json = COALESCE(selected_options_json, '[]')
            """
        )
    )
    await db.commit()


async def _seed_menus_if_needed(db: AsyncSession) -> None:
    existing = await db.execute(select(Menu.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return

    for item in MENUS:
        db.add(Menu(**item))
    await db.commit()
    logger.info("Inserted default menus: %d", len(MENUS))


async def _seed_menu_options_from_category_map(db: AsyncSession) -> int:
    existing = await db.execute(select(MenuOption.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return 0

    menu_rows = (await db.execute(select(Menu))).scalars().all()
    if not menu_rows:
        return 0

    inserted = 0
    for menu in menu_rows:
        group_names = CATEGORY_OPTION_MAP.get(menu.category, [])
        for group_order, group_name in enumerate(group_names):
            group = _OPTION_GROUPS_BY_NAME.get(group_name)
            if not group:
                continue
            for option_order, item in enumerate(group["items"]):
                db.add(
                    MenuOption(
                        menu_id=menu.id,
                        group_name=group["name"],
                        group_order=group_order,
                        option_name=item["name"],
                        option_order=option_order,
                        extra_price=item.get("extra_price", 0),
                        is_required=group["is_required"],
                        min_select=group["min_select"],
                        max_select=group["max_select"],
                        is_default=item.get("is_default", False),
                        is_available=item.get("is_available", True),
                    )
                )
                inserted += 1

    await db.commit()
    return inserted


async def _migrate_legacy_option_tables(db: AsyncSession, tables: set[str]) -> int:
    required = {"option_groups", "option_items", "menu_option_groups", "menus", "menu_options"}
    if not required.issubset(tables):
        return 0

    existing = await db.execute(select(MenuOption.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return 0

    rows = (
        await db.execute(
            text(
                """
                SELECT
                    mog.menu_id AS menu_id,
                    og.name AS group_name,
                    mog.display_order AS group_order,
                    oi.name AS option_name,
                    oi.extra_price AS extra_price,
                    og.is_required AS is_required,
                    og.min_select AS min_select,
                    og.max_select AS max_select,
                    oi.is_default AS is_default,
                    oi.is_available AS is_available
                FROM menu_option_groups AS mog
                JOIN option_groups AS og ON og.id = mog.option_group_id
                JOIN option_items AS oi ON oi.group_id = og.id
                ORDER BY mog.menu_id, mog.display_order, oi.id
                """
            )
        )
    ).mappings().all()

    if not rows:
        return 0

    option_order_by_group: dict[tuple[int, str, int], int] = {}
    inserted = 0
    for row in rows:
        key = (int(row["menu_id"]), str(row["group_name"]), int(row["group_order"] or 0))
        option_order = option_order_by_group.get(key, 0)
        option_order_by_group[key] = option_order + 1

        db.add(
            MenuOption(
                menu_id=int(row["menu_id"]),
                group_name=str(row["group_name"]),
                group_order=int(row["group_order"] or 0),
                option_name=str(row["option_name"]),
                option_order=option_order,
                extra_price=int(row["extra_price"] or 0),
                is_required=bool(row["is_required"]),
                min_select=int(row["min_select"] or 0),
                max_select=int(row["max_select"] or 1),
                is_default=bool(row["is_default"]),
                is_available=bool(row["is_available"]),
            )
        )
        inserted += 1

    await db.commit()
    return inserted


async def _update_menu_images_if_missing(db: AsyncSession) -> int:
    menu_rows = (await db.execute(select(Menu))).scalars().all()
    updated = 0
    for menu in menu_rows:
        url = MENU_IMAGES.get(menu.name)
        if url and menu.image_url != url:
            menu.image_url = url
            updated += 1
    if updated:
        await db.commit()
        logger.info("Updated menu image URLs: %d menus", updated)
    return updated


async def seed_menu_data(db: AsyncSession) -> None:
    tables = set(await _get_table_names(db))

    try:
        await _drop_legacy_foreign_keys(db, tables)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Legacy foreign key cleanup skipped: %s", exc)
        await db.rollback()

    try:
        await _migrate_order_item_snapshots(db, tables)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Order item snapshot migration skipped: %s", exc)
        await db.rollback()

    await _seed_menus_if_needed(db)

    migrated = 0
    try:
        migrated = await _migrate_legacy_option_tables(db, tables)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Legacy option migration skipped: %s", exc)
        await db.rollback()

    if migrated > 0:
        logger.info("Migrated legacy option tables into menu_options: %d rows", migrated)
        return

    inserted = await _seed_menu_options_from_category_map(db)
    if inserted > 0:
        logger.info("Inserted default menu options: %d rows", inserted)
    else:
        logger.info("Menu seed data already exists. Skipping.")

    await _update_menu_images_if_missing(db)
