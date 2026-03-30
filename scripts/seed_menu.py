"""
카테고리 + 메뉴 + 옵션 초기 데이터를 DB에 삽입합니다.
서버 시작 시 main.py lifespan에서 호출됩니다.
이미 데이터가 있으면 건너뜁니다.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Category, Menu, OptionGroup, OptionItem, MenuOptionGroup

logger = logging.getLogger(__name__)

# ─── 카테고리 ───
CATEGORIES = [
    {"name": "커피", "display_order": 1},
    {"name": "달콤한커피", "display_order": 2},
    {"name": "블렌디드", "display_order": 3},
    {"name": "티", "display_order": 4},
    {"name": "달콤한티", "display_order": 5},
    {"name": "에이드", "display_order": 6},
    {"name": "스무디", "display_order": 7},
    {"name": "주스", "display_order": 8},
]

# ─── 메뉴 ───
MENUS = [
    # 커피
    {"name": "에스프레소", "category": "커피", "price": 4000, "emoji": "☕", "cal": 5, "temp": "hot"},
    {"name": "따뜻한 아메리카노", "category": "커피", "price": 4500, "emoji": "☕", "cal": 10, "temp": "hot"},
    {"name": "아이스 아메리카노", "category": "커피", "price": 4500, "emoji": "☕", "cal": 10, "temp": "cold"},
    {"name": "따뜻한 카페라떼", "category": "커피", "price": 5200, "emoji": "🥛", "cal": 120, "temp": "hot"},
    {"name": "아이스 카페라떼", "category": "커피", "price": 5200, "emoji": "🥛", "cal": 110, "temp": "cold"},
    {"name": "카푸치노", "category": "커피", "price": 5200, "emoji": "☕", "cal": 100, "temp": "hot"},
    {"name": "콜드브루", "category": "커피", "price": 5200, "emoji": "🖤", "cal": 10, "temp": "cold"},
    {"name": "콜드브루 라떼", "category": "커피", "price": 5800, "emoji": "🖤", "cal": 110, "temp": "cold"},
    {"name": "드립 커피", "category": "커피", "price": 5000, "emoji": "☕", "cal": 10, "temp": "hot"},
    # 달콤한 커피
    {"name": "바닐라 라떼", "category": "달콤한커피", "price": 5900, "emoji": "🍦", "cal": 200, "temp": "both"},
    {"name": "카라멜 마끼아또", "category": "달콤한커피", "price": 6200, "emoji": "🍮", "cal": 250, "temp": "both"},
    # 블렌디드
    {"name": "프라푸치노", "category": "블렌디드", "price": 6500, "emoji": "🍫", "cal": 350, "temp": "cold"},
    {"name": "말차 프라페", "category": "블렌디드", "price": 6300, "emoji": "🍵", "cal": 300, "temp": "cold"},
    # 티
    {"name": "녹차 라떼", "category": "티", "price": 5800, "emoji": "🍵", "cal": 160, "temp": "both"},
    {"name": "캐모마일 티", "category": "티", "price": 4900, "emoji": "🌼", "cal": 5, "temp": "hot"},
    # 달콤한 티
    {"name": "복숭아 아이스티", "category": "달콤한티", "price": 5200, "emoji": "🍑", "cal": 80, "temp": "cold"},
    {"name": "자몽 허니 블랙 티", "category": "달콤한티", "price": 5700, "emoji": "🍊", "cal": 90, "temp": "cold"},
    # 에이드/주스
    {"name": "레몬에이드", "category": "에이드", "price": 6000, "emoji": "🍋", "cal": 120, "temp": "cold"},
    {"name": "자몽에이드", "category": "에이드", "price": 6200, "emoji": "🍊", "cal": 110, "temp": "cold"},
    # 스무디
    {"name": "딸기 스무디", "category": "스무디", "price": 6500, "emoji": "🍓", "cal": 260, "temp": "cold"},
    {"name": "망고 스무디", "category": "스무디", "price": 6500, "emoji": "🥭", "cal": 250, "temp": "cold"},
    # 주스
    {"name": "오렌지 주스", "category": "주스", "price": 5800, "emoji": "🍊", "cal": 110, "temp": "cold"},
]

# ─── 옵션 그룹 + 아이템 ───
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

# 어떤 카테고리의 메뉴에 어떤 옵션 그룹을 연결할지 (카테고리 이름 → 옵션 그룹 이름 목록)
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


async def seed_menu_data(db: AsyncSession):
    """DB에 초기 메뉴 데이터를 삽입합니다. 이미 있으면 건너뜁니다."""
    existing = await db.execute(select(Category.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        logger.info("Seed data already exists. Skipping.")
        return

    # 1. 카테고리 생성
    cat_map = {}
    for cat in CATEGORIES:
        c = Category(name=cat["name"], display_order=cat["display_order"])
        db.add(c)
    await db.flush()

    # 카테고리 ID 맵 구축
    result = await db.execute(select(Category))
    for c in result.scalars().all():
        cat_map[c.name] = c.id

    # 2. 메뉴 생성
    for m in MENUS:
        cat_name = m["category"]
        cat_id = cat_map.get(cat_name)
        if not cat_id:
            continue
        menu = Menu(
            name=m["name"],
            category=cat_name,
            price=m["price"],
            emoji=m.get("emoji"),
            cal=m.get("cal"),
            temp=m.get("temp"),
        )
        db.add(menu)
    await db.flush()

    # 3. 옵션 그룹 + 아이템 생성
    og_map = {}
    for og_data in OPTION_GROUPS:
        og = OptionGroup(
            name=og_data["name"],
            is_required=og_data["is_required"],
            min_select=og_data["min_select"],
            max_select=og_data["max_select"],
        )
        db.add(og)
        await db.flush()
        og_map[og.name] = og.id

        for item_data in og_data["items"]:
            oi = OptionItem(
                group_id=og.id,
                name=item_data["name"],
                extra_price=item_data["extra_price"],
                is_default=item_data["is_default"],
            )
            db.add(oi)

    await db.flush()

    # 4. 메뉴 - 옵션 그룹 연결
    menu_result = await db.execute(select(Menu))
    all_menus = menu_result.scalars().all()

    for menu in all_menus:
        # 메뉴의 카테고리 이름 조회
        cat_result = await db.execute(select(Category).where(Category.name == menu.category))
        cat = cat_result.scalar_one_or_none()
        if not cat:
            continue

        option_names = CATEGORY_OPTION_MAP.get(cat.name, [])
        for order, og_name in enumerate(option_names):
            og_id = og_map.get(og_name)
            if og_id:
                mog = MenuOptionGroup(
                    menu_id=menu.id,
                    option_group_id=og_id,
                    display_order=order,
                )
                db.add(mog)

    await db.commit()
    logger.info("Seed data inserted successfully.")
