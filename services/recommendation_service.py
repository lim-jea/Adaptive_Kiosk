from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.menu import get_menus_by_category_name, get_all_menus


async def get_recommendations(
    db: AsyncSession,
    preferred_category: str,
    estimated_gender: Optional[str] = None,
    estimated_age_group: Optional[str] = None,
) -> dict:
    """
    추천 결과를 생성합니다.

    Returns:
        {
            "your_picks": [...],   # 선호 계열 중심 추천
            "discovery": [...],    # CF 기반 다른 계열 추천 (현재는 인기메뉴 fallback)
        }

    현재는 DB 기반 단순 추천이며, 추후 CF 모델로 교체 예정.
    """
    # your_picks: 선호 카테고리 내 메뉴
    category_menus = await get_menus_by_category_name(db, preferred_category)
    your_picks = [
        {
            "menu_id": menu.id,
            "menu_name": menu.name,
            "category": preferred_category,
            "price": menu.price,
            "image_url": menu.image_url,
            "recommendation_type": "your_picks",
        }
        for menu in category_menus
    ]

    # discovery: 다른 계열 메뉴
    all_menus = await get_all_menus(db)
    category_menu_ids = {m.id for m in category_menus}
    discovery_menus = [m for m in all_menus if m.id not in category_menu_ids]
    discovery = [
        {
            "menu_id": menu.id,
            "menu_name": menu.name,
            "category": preferred_category,
            "price": menu.price,
            "image_url": menu.image_url,
            "recommendation_type": "discovery",
        }
        for menu in discovery_menus[:5]
    ]

    return {
        "your_picks": your_picks,
        "discovery": discovery,
    }
