"""
메뉴 카탈로그 텍스트를 메모리 캐시한다.

DB의 메뉴/카테고리는 자주 바뀌지 않으므로 5분 TTL의 단순 메모리 캐시로
프롬프트 빌드 시 매번 DB를 조회하지 않게 한다.
"""
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.menu import Menu, Category

_CACHE_TTL_SEC = 300
_cache: dict = {"text": None, "expires_at": 0.0}


async def _build_menu_catalog_text(db: AsyncSession) -> str:
    cats = (await db.execute(select(Category).order_by(Category.display_order))).scalars().all()
    menus = (
        await db.execute(
            select(Menu).where(Menu.is_available == True).order_by(Menu.category, Menu.name)
        )
    ).scalars().all()

    by_cat: dict[str, list[Menu]] = {}
    for m in menus:
        by_cat.setdefault(m.category, []).append(m)

    lines: list[str] = ["[메뉴 카탈로그]"]
    for c in cats:
        items = by_cat.get(c.name, [])
        if not items:
            continue
        lines.append(f"- {c.name}:")
        for m in items:
            tags = []
            if m.serving_temperature:
                tags.append(m.serving_temperature)
            if m.is_caffeinated:
                tags.append("카페인")
            tag_str = f" ({'/'.join(tags)})" if tags else ""
            lines.append(f"  · {m.name} — {m.price}원{tag_str}")
    return "\n".join(lines)


async def get_cached_menu_catalog_text(db: AsyncSession) -> str:
    now = time.time()
    if _cache["text"] is not None and _cache["expires_at"] > now:
        return _cache["text"]
    text = await _build_menu_catalog_text(db)
    _cache["text"] = text
    _cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


def invalidate_menu_catalog_cache() -> None:
    _cache["text"] = None
    _cache["expires_at"] = 0.0
