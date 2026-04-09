"""
단계별로 AI에게 주입할 DB 컨텍스트를 빌드한다.

각 stage에 필요한 카테고리/메뉴/옵션 정보를 DB에서 조회해 텍스트 블록으로 변환한다.
응답 예시나 액션 문법 같은 정적 가이드는 stages.py / chat_service._JSON_FORMAT_INSTRUCTION /
canned_responses 의 매뉴얼이 따로 처리하므로 여기서는 다루지 않는다.

카테고리 목록은 자주 바뀌지 않으므로 5분 메모리 캐시를 둔다.
"""
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.menu import get_menu_detail, get_menus
from models.menu import Category

_CACHE_TTL_SEC = 300
_cat_cache: dict = {"text": None, "expires_at": 0.0}


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


def invalidate_menu_catalog_cache() -> None:
    _cat_cache["text"] = None
    _cat_cache["expires_at"] = 0.0


# ─── 메뉴/옵션 텍스트 빌더 ───────────────────────────────────────────────────

async def _build_menus_in_category_text(db: AsyncSession, category: Optional[str]) -> str:
    rows, _ = await get_menus(db, category_name=category, limit=200)
    header = (
        f"[메뉴 목록 — 카테고리: {category}]" if category else "[메뉴 목록 (전체)]"
    )
    if not rows:
        return f"{header}\n(없음)"
    lines = [header]
    for m in rows:
        tags = []
        if m.get("serving_temperature"):
            tags.append(m["serving_temperature"])
        if m.get("is_caffeinated"):
            tags.append("카페인")
        tag_str = f" ({'/'.join(tags)})" if tags else ""
        desc = f" — {m['description']}" if m.get("description") else ""
        lines.append(f"- {m['name']}: {m['price']}원{tag_str}{desc}")
    return "\n".join(lines)


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
    if detail.get("serving_temperature"):
        lines.append(f"- 제공 온도: {detail['serving_temperature']}")
    if detail.get("is_caffeinated"):
        lines.append("- 카페인 포함")
    for g in detail.get("option_groups") or []:
        req = "필수" if g.get("is_required") else "선택"
        lines.append(
            f"- 옵션 그룹: {g['name']} ({req}, {g['min_select']}~{g['max_select']}개)"
        )
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
    """현재 stage에 필요한 DB 컨텍스트만 합쳐 반환. 응답 예시는 포함하지 않는다."""
    if stage in ("greeting", "category_browse"):
        return await _get_cached_category_text(db)

    if stage == "menu_browse":
        return await _build_menus_in_category_text(db, selected_category)

    if stage == "menu_select":
        if selected_menu_name:
            return await _build_menu_detail_text(db, selected_menu_name)
        return await _build_menus_in_category_text(db, selected_category)

    if stage == "option_select":
        if selected_menu_name:
            return await _build_option_groups_text(db, selected_menu_name)
        return "[옵션] 선택된 메뉴 정보가 없습니다. 사용자에게 메뉴부터 다시 물어보세요."

    # cart_review / payment_confirm / farewell — 카트 스냅샷이 별도로 들어가므로 DB 컨텍스트 불필요
    return ""
