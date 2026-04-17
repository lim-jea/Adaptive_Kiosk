"""
단계별로 AI에게 주입할 DB 컨텍스트를 빌드한다.

핵심: AI가 정확한 메뉴 이름을 사용하도록 **모든 단계에서 전체 메뉴 목록을 포함**한다.
메뉴 이름이 정확해야 프런트의 navigate(menu_detail)가 404를 내지 않는다.
"""
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crud.menu import get_categories, get_menu_detail, get_menus

_CACHE_TTL_SEC = 300
_cat_cache: dict = {"text": None, "expires_at": 0.0}
_menu_names_cache: dict = {"text": None, "expires_at": 0.0}
_menu_prices_cache: dict = {"text": None, "expires_at": 0.0}


# ─── 카테고리 목록 (캐시) ───────────────────────────────────────────────────

async def _build_category_list_text(db: AsyncSession) -> str:
    cats, _ = await get_categories(db, limit=1000)
    if not cats:
        return "[카테고리 목록] (없음)"
    return "[카테고리 목록]\n" + "\n".join(f"- {c['name']}" for c in cats)


async def _get_cached_category_text(db: AsyncSession) -> str:
    now = time.time()
    if _cat_cache["text"] is not None and _cat_cache["expires_at"] > now:
        return _cat_cache["text"]
    text = await _build_category_list_text(db)
    _cat_cache["text"] = text
    _cat_cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


# ─── 메뉴 카탈로그 (캐시) ──────────────────────────────────────────────────

async def _build_menu_names_text(db: AsyncSession) -> str:
    """카테고리별 메뉴 이름만(컴팩트).
    대부분의 stage에서 '정확한 menu_name' 매칭만 필요하므로 가격/태그는 생략한다."""
    cats, _ = await get_categories(db, limit=1000)
    rows, _ = await get_menus(db, limit=500)

    by_cat: dict[str, list] = {}
    for m in rows:
        by_cat.setdefault(m["category"], []).append(m)

    lines = ["[메뉴 이름 목록] (navigate시 menu_name은 아래 이름 그대로 사용)"]
    for c in cats:
        items = by_cat.get(c["name"], [])
        if not items:
            continue
        names = [m["name"] for m in items if m.get("name")]
        if not names:
            continue
        lines.append(f"[{c['name']}] " + ", ".join(names))
    return "\n".join(lines)


async def _get_cached_menu_names_text(db: AsyncSession) -> str:
    now = time.time()
    if _menu_names_cache["text"] is not None and _menu_names_cache["expires_at"] > now:
        return _menu_names_cache["text"]
    text = await _build_menu_names_text(db)
    _menu_names_cache["text"] = text
    _menu_names_cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


async def _build_menu_prices_text(db: AsyncSession) -> str:
    """메뉴 이름+가격(간단 표기). 메뉴 탐색 단계에서만 추가 주입."""
    cats, _ = await get_categories(db, limit=1000)
    rows, _ = await get_menus(db, limit=500)

    by_cat: dict[str, list] = {}
    for m in rows:
        by_cat.setdefault(m["category"], []).append(m)

    lines = ["[메뉴 목록(가격)]"]
    for c in cats:
        items = by_cat.get(c["name"], [])
        if not items:
            continue
        pairs = [f"{m['name']}({m['price']}원)" for m in items if m.get("name")]
        if not pairs:
            continue
        lines.append(f"[{c['name']}] " + ", ".join(pairs))
    return "\n".join(lines)


async def _get_cached_menu_prices_text(db: AsyncSession) -> str:
    now = time.time()
    if _menu_prices_cache["text"] is not None and _menu_prices_cache["expires_at"] > now:
        return _menu_prices_cache["text"]
    text = await _build_menu_prices_text(db)
    _menu_prices_cache["text"] = text
    _menu_prices_cache["expires_at"] = now + _CACHE_TTL_SEC
    return text


def invalidate_menu_catalog_cache() -> None:
    _cat_cache["text"] = None
    _cat_cache["expires_at"] = 0.0
    _menu_names_cache["text"] = None
    _menu_names_cache["expires_at"] = 0.0
    _menu_prices_cache["text"] = None
    _menu_prices_cache["expires_at"] = 0.0


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
            item_id = getattr(it, "id", None) if not isinstance(it, dict) else it.get("id")
            item_name = getattr(it, "name", None) if not isinstance(it, dict) else it.get("name")
            extra_price = getattr(it, "extra_price", None) if not isinstance(it, dict) else it.get("extra_price", 0)
            is_default = getattr(it, "is_default", None) if not isinstance(it, dict) else it.get("is_default")
            extra = f" (+{extra_price}원)" if extra_price else ""
            default = " [기본]" if is_default else ""
            lines.append(f"  · id={item_id} {item_name}{extra}{default}")
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

    # 모든 단계에서 '메뉴 이름 목록'은 포함 (정확한 menu_name 매칭 목적)
    blocks.append(await _get_cached_menu_names_text(db))

    # 메뉴 탐색 단계에서는 가격 정보까지 추가로 포함
    if stage == "menu_browse":
        blocks.append(await _get_cached_menu_prices_text(db))

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
