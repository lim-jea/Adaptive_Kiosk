"""
단계별로 AI에게 주입할 DB 컨텍스트를 빌드한다.

핵심: AI가 정확한 메뉴 이름을 사용하도록 **모든 단계에서 전체 메뉴 목록을 포함**한다.
메뉴 이름이 정확해야 프런트의 navigate(menu_detail)가 404를 내지 않는다.
"""
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.menu import get_menu_detail, get_menus
from models.menu import Category

_CACHE_TTL_SEC = 300
_cat_cache: dict = {"text": None, "expires_at": 0.0}
_menu_cache: dict = {"text": None, "expires_at": 0.0}


# ─── 카테고리 목록 (캐시) ───────────────────────────────────────────────────

async def _build_category_list_text(db: AsyncSession) -> str:
    cats = (await db.execute(select(Category).order_by(Category.display_order))).scalars().all()
    if not cats:
        return "[카테고리 목록] (없음)"
    return "[카테고리 목록]\n" + "\n".join(f"- {c.name}" for c in cats)


async def _get_cached_category_text(db: AsyncSession) -> str:
    now = time.time()
    if _cat_cache["text"] is not None and _cat_cache["expires_at"] > now:
        return _cat_cache["text"]
    text = await _build_category_list_text(db)
    _cat_cache["text"] = text
    _cat_cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


# ─── 전체 메뉴 목록 (캐시) — 모든 단계에서 사용 ──────────────────────────────

async def _build_full_menu_text(db: AsyncSession) -> str:
    """카테고리별로 묶은 전체 메뉴 이름+가격 목록.
    AI가 모든 단계에서 정확한 메뉴 이름을 사용하게 한다."""
    cats = (await db.execute(select(Category).order_by(Category.display_order))).scalars().all()
    rows, _ = await get_menus(db, limit=500)

    by_cat: dict[str, list] = {}
    for m in rows:
        by_cat.setdefault(m["category"], []).append(m)

    lines = ["[전체 메뉴 목록] ※ navigate시 menu_name은 아래 이름을 정확히 사용하세요."]
    for c in cats:
        items = by_cat.get(c.name, [])
        if not items:
            continue
        lines.append(f"  [{c.name}]")
        for m in items:
            tags = []
            if m.get("serving_temperature"):
                tags.append(m["serving_temperature"])
            if m.get("is_caffeinated"):
                tags.append("카페인")
            tag_str = f" ({'/'.join(tags)})" if tags else ""
            lines.append(f"  - {m['name']}: {m['price']}원{tag_str}")
    return "\n".join(lines)


async def _get_cached_menu_text(db: AsyncSession) -> str:
    now = time.time()
    if _menu_cache["text"] is not None and _menu_cache["expires_at"] > now:
        return _menu_cache["text"]
    text = await _build_full_menu_text(db)
    _menu_cache["text"] = text
    _menu_cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


def invalidate_menu_catalog_cache() -> None:
    _cat_cache["text"] = None
    _cat_cache["expires_at"] = 0.0
    _menu_cache["text"] = None
    _menu_cache["expires_at"] = 0.0


# ─── 메뉴 상세 / 옵션 텍스트 빌더 (특정 메뉴 선택 시) ─────────────────────

async def _build_menu_detail_text(db: AsyncSession, menu_name: str) -> str:
    detail = await get_menu_detail(db, menu_name)
    if not detail:
        return f"[메뉴 상세] '{menu_name}' 을(를) 찾을 수 없습니다."
    lines = [
        f"[메뉴 상세 — {detail['name']}]",
        f"- 기본 가격: {detail['price']}원",
    ]
    if detail.get("description"):
        lines.append(f"- 설명: {detail['description']}")
    temp = detail.get("serving_temperature")
    if temp:
        if temp in ("cold", "hot"):
            lines.append(f"- 제공 온도: {temp} (고정)")
        else:
            lines.append(f"- 제공 온도: {temp}")
    if detail.get("is_caffeinated"):
        lines.append("- 카페인 포함")
    for g in detail.get("option_groups") or []:
        req = "필수" if g.get("is_required") else "선택"
        lines.append(f"- 옵션: {g['name']} ({req}, {g['min_select']}~{g['max_select']}개)")
    return "\n".join(lines)


async def _build_option_groups_text(db: AsyncSession, menu_name: str) -> str:
    detail = await get_menu_detail(db, menu_name)
    if not detail:
        return f"[옵션] '{menu_name}' 을(를) 찾을 수 없습니다."
    groups = detail.get("option_groups") or []
    if not groups:
        return f"[옵션] '{menu_name}' 메뉴는 옵션이 없습니다."
    lines = [f"[옵션 그룹 — {menu_name}]"]
    for g in groups:
        req = "필수" if g.get("is_required") else "선택"
        lines.append(f"- {g['name']} ({req}, {g['min_select']}~{g['max_select']}개 선택)")
        for it in g.get("items", []):
            extra = f" (+{it.extra_price}원)" if it.extra_price else ""
            default = " [기본]" if it.is_default else ""
            lines.append(f"  · id={it.id} {it.name}{extra}{default}")
    return "\n".join(lines)


# ─── 단계별 통합 컨텍스트 빌더 ───────────────────────────────────────────────

async def build_stage_context(
    db: AsyncSession,
    *,
    stage: str,
    selected_category: Optional[str] = None,
    selected_menu_name: Optional[str] = None,
) -> str:
    """
    현재 stage에 필요한 DB 컨텍스트를 합쳐 반환.

    핵심: **전체 메뉴 목록은 모든 단계에서 항상 포함**.
    AI가 어느 단계에서든 사용자가 말한 메뉴 이름을 정확히 DB 이름으로 변환할 수 있다.
    """
    blocks: list[str] = []

    # 모든 단계에서 전체 메뉴 목록 포함 (캐시라서 DB 부하 거의 없음)
    blocks.append(await _get_cached_menu_text(db))

    # 단계별 추가 정보
    if stage in ("greeting", "category_browse"):
        blocks.append(await _get_cached_category_text(db))

    elif stage == "menu_select":
        if selected_menu_name:
            blocks.append(await _build_menu_detail_text(db, selected_menu_name))

    elif stage == "option_select":
        if selected_menu_name:
            blocks.append(await _build_option_groups_text(db, selected_menu_name))
        else:
            blocks.append("[옵션] 선택된 메뉴 정보가 없습니다. 사용자에게 메뉴부터 다시 물어보세요.")

    elif stage in ("cart_review", "payment_confirm"):
        blocks.append(await _get_cached_category_text(db))

    return "\n\n".join(blocks)
