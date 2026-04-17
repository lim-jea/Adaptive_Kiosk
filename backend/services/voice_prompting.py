"""
Voice prompting helpers.

음성 주문에서 Gemini에 주입하는 페르소나, 단계 규칙, DB 컨텍스트,
시스템 프롬프트를 한 축으로 모아 유지보수하기 쉽게 정리한 모듈이다.
"""
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crud.menu import get_categories, get_menu_detail, get_menus


PERSONAS: dict[str, str] = {
    "elderly": (
        "[페르소나: 어르신 손님]\n"
        "- 천천히, 또박또박, 한 번에 한 가지만.\n"
        "- 외래어를 쉬운 말로 (Tall→보통, Grande→큰 것, ICE→차가운 것, HOT→따뜻한 것).\n"
        "- 자주 재확인. 같은 말을 반복해도 친절하게.\n"
        "- 혼란스러워하면 가장 기본적인 것을 추천.\n"
        "- 정중하고 공손하게. 어린이 취급 절대 금지."
    ),
    "child": (
        "[페르소나: 어린 손님]\n"
        "- 친근하고 밝게, 어린이 취급은 하지 않기.\n"
        "- 카페인 음료 주문 시 한 번 확인."
    ),
    "general": (
        "[페르소나: 일반 손님]\n"
        "- 자연스럽고 간결하게."
    ),
    "unknown": (
        "[페르소나: 일반 손님]\n"
        "- 친절하지만 간결하게."
    ),
}


GREETING_BY_PERSONA: dict[str, str] = {
    "elderly": "안녕하세요. 천천히 말씀해 주세요. 어떤 음료를 드시고 싶으신가요?",
    "child": "안녕하세요! 어떤 음료가 좋을까요?",
    "general": "안녕하세요. 어떤 음료로 주문하시겠어요?",
    "unknown": "안녕하세요. 어떤 음료로 주문하시겠어요?",
}


def decide_persona(age: int | None = None, age_group: str | None = None) -> str:
    if age is not None:
        if age <= 12:
            return "child"
        if age <= 55:
            return "general"
        return "elderly"

    if not age_group:
        return "unknown"
    if age_group in {"노년", "60대", "70대", "80대"}:
        return "elderly"
    if age_group in {"어린이", "아동", "10대 초", "10대"}:
        return "child"
    if age_group in {"청년", "중장년", "청소년", "중년", "20대", "30대", "40대", "50대"}:
        return "general"
    return "unknown"


STAGES: dict[str, str] = {
    "greeting": (
        "[현재 단계: greeting / 맞이]\n"
        "- 인사 후 다음 행동(카테고리/추천/메뉴명)을 한 번만 묻는다.\n"
        "- 메뉴명을 말하면 바로 menu_detail로 이동.\n"
        "- 허용: speak, navigate(category|menu_detail)\n"
        "- 다음: category_browse|menu_browse|option_select / 종료: end_conversation"
    ),
    "category_browse": (
        "[현재 단계: category_browse / 카테고리 탐색]\n"
        "- [카테고리 목록]에 있는 카테고리만 안내.\n"
        "- 선택 시 navigate(category, category_name). 메뉴명은 menu_detail로.\n"
        "- 허용: speak, navigate(category|menu_detail)\n"
        "- 다음: menu_browse|option_select / 뒤로: greeting"
    ),
    "menu_browse": (
        "[현재 단계: menu_browse / 메뉴 둘러보기]\n"
        "- [메뉴 목록]에 있는 메뉴만 안내(짧게).\n"
        "- 더 보기/위로: scroll. 메뉴 선택: navigate(menu_detail).\n"
        "- 허용: speak, navigate(menu_detail|category), scroll\n"
        "- 다음: option_select / 뒤로: category_browse"
    ),
    "menu_select": (
        "[현재 단계: menu_select / 메뉴 선택 확인]\n"
        "- 선택한 메뉴를 확인하고 옵션 단계로 유도.\n"
        "- 허용: speak, navigate(menu_detail)\n"
        "- 다음: option_select|cart_review / 뒤로: menu_browse"
    ),
    "option_select": (
        "[현재 단계: option_select / 옵션 선택]\n"
        "- [옵션 그룹]에 있는 항목만 안내. 한 그룹씩 진행.\n"
        "- 부분 선택: option_preview, 필수 완료: cart_add.\n"
        "- 허용: speak, option_preview, cart_add\n"
        "- 다음: cart_review / 취소: 현재 선택 취소(전체 주문 취소 아님)"
    ),
    "cart_review": (
        "[현재 단계: cart_review / 장바구니 확인]\n"
        "- 장바구니/합계를 짧게 안내하고 다음 행동(추가/수정/결제) 질문.\n"
        "- 같은 메뉴가 여러 줄이면 cart_remove/cart_update에 cart_line_id 또는 option_item_ids를 함께 넣어 정확히 지정.\n"
        "- 결제: navigate(payment).\n"
        "- 허용: speak, navigate(category|menu_detail|payment), cart_remove, cart_update\n"
        "- 다음: category_browse|payment_confirm"
    ),
    "payment_confirm": (
        "[현재 단계: payment_confirm / 결제 확인]\n"
        "- 합계 안내 후 결제 진행 여부 확인.\n"
        "- 예: place_order / 아니요: cart_review / 더 추가: category_browse\n"
        "- 허용: speak, place_order, navigate(cart|category)\n"
        "- 다음: farewell"
    ),
    "farewell": (
        "[현재 단계: farewell / 배웅]\n"
        "- 주문 완료 안내 후 종료.\n"
        "- end_conversation=true + EndConversationAction"
    ),
}


_CACHE_TTL_SEC = 300
_cat_cache: dict = {"text": None, "expires_at": 0.0}
_menu_names_cache: dict = {"text": None, "expires_at": 0.0}
_menu_prices_cache: dict = {"text": None, "expires_at": 0.0}


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


async def _build_menu_names_text(db: AsyncSession) -> str:
    cats, _ = await get_categories(db, limit=1000)
    rows, _ = await get_menus(db, limit=500)

    by_cat: dict[str, list] = {}
    for menu in rows:
        by_cat.setdefault(menu["category"], []).append(menu)

    lines = ["[메뉴 이름 목록] (navigate시 menu_name은 아래 이름 그대로 사용)"]
    for category in cats:
        items = by_cat.get(category["name"], [])
        if not items:
            continue
        names = [m["name"] for m in items if m.get("name")]
        if names:
            lines.append(f"[{category['name']}] " + ", ".join(names))
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
    cats, _ = await get_categories(db, limit=1000)
    rows, _ = await get_menus(db, limit=500)

    by_cat: dict[str, list] = {}
    for menu in rows:
        by_cat.setdefault(menu["category"], []).append(menu)

    lines = ["[메뉴 목록(가격)]"]
    for category in cats:
        items = by_cat.get(category["name"], [])
        if not items:
            continue
        pairs = [f"{m['name']}({m['price']}원)" for m in items if m.get("name")]
        if pairs:
            lines.append(f"[{category['name']}] " + ", ".join(pairs))
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
    for group in detail.get("option_groups") or []:
        requirement = "필수" if group.get("is_required") else "선택"
        lines.append(f"- 옵션: {group['name']} ({requirement}, {group['min_select']}~{group['max_select']}개)")
    return "\n".join(lines)


async def _build_option_groups_text(db: AsyncSession, menu_name: str) -> str:
    detail = await get_menu_detail(db, menu_name)
    if not detail:
        return f"[옵션] '{menu_name}' 을(를) 찾을 수 없습니다."
    groups = detail.get("option_groups") or []
    if not groups:
        return f"[옵션] '{menu_name}' 메뉴는 옵션이 없습니다."
    lines = [f"[옵션 그룹 — {menu_name}]"]
    for group in groups:
        requirement = "필수" if group.get("is_required") else "선택"
        lines.append(f"- {group['name']} ({requirement}, {group['min_select']}~{group['max_select']}개 선택)")
        for item in group.get("items", []):
            item_id = getattr(item, "id", None) if not isinstance(item, dict) else item.get("id")
            item_name = getattr(item, "name", None) if not isinstance(item, dict) else item.get("name")
            extra_price = getattr(item, "extra_price", None) if not isinstance(item, dict) else item.get("extra_price", 0)
            is_default = getattr(item, "is_default", None) if not isinstance(item, dict) else item.get("is_default")
            extra = f" (+{extra_price}원)" if extra_price else ""
            default = " [기본]" if is_default else ""
            lines.append(f"  · id={item_id} {item_name}{extra}{default}")
    return "\n".join(lines)


async def build_stage_context(
    db: AsyncSession,
    *,
    stage: str,
    selected_category: Optional[str] = None,
    selected_menu_name: Optional[str] = None,
) -> str:
    blocks: list[str] = [await _get_cached_menu_names_text(db)]

    if stage == "menu_browse":
        blocks.append(await _get_cached_menu_prices_text(db))
        if selected_category:
            blocks.append(f"[현재 보고 있는 카테고리]\n- {selected_category}")

    if stage in ("greeting", "category_browse"):
        blocks.append(await _get_cached_category_text(db))
        if selected_category:
            blocks.append(f"[현재 보고 있는 카테고리]\n- {selected_category}")
    elif stage == "menu_select":
        if selected_menu_name:
            blocks.append(await _build_menu_detail_text(db, selected_menu_name))
        if selected_category:
            blocks.append(f"[현재 보고 있는 카테고리]\n- {selected_category}")
    elif stage == "option_select":
        if selected_menu_name:
            blocks.append(await _build_option_groups_text(db, selected_menu_name))
            blocks.append(f"[현재 선택된 메뉴]\n- {selected_menu_name}")
        else:
            blocks.append("[옵션] 선택된 메뉴 정보가 없습니다. 사용자에게 메뉴부터 다시 물어보세요.")
        if selected_category:
            blocks.append(f"[현재 보고 있는 카테고리]\n- {selected_category}")
    elif stage in ("cart_review", "payment_confirm"):
        blocks.append(await _get_cached_category_text(db))
        if selected_category:
            blocks.append(f"[현재 보고 있던 카테고리]\n- {selected_category}")

    return "\n\n".join(blocks)


SYSTEM_PROMPT_TEMPLATE = """당신은 카페 키오스크의 음성 주문 도우미입니다.
손님의 음성을 듣고, 메뉴 선택부터 결제까지 자연스럽게 안내합니다.

[우선순위]
1. 현재 화면/장바구니/선택 상태를 먼저 따른다.
2. 현재 stage 규칙을 따른다.
3. 아래 DB 컨텍스트에 있는 메뉴/옵션/카테고리만 사용한다.
4. 확실하지 않으면 추측하지 말고 짧게 확인 질문한다.

[응답 형식 — 절대 변경 불가]
- 항상 JSON 스키마(AIChatResponse)로만 응답한다. JSON 외 텍스트 금지.
- response_text: 손님에게 음성으로 들려줄 짧은 한국어 문장 (가능하면 1문장, 길면 2문장까지).
- actions: 화면 조작 명령 배열. speak 액션은 항상 포함.
- next_stage: 반드시 다음 중 하나만 사용: greeting, category_browse, menu_browse, menu_select, option_select, cart_review, payment_confirm, farewell. 변경 없으면 null.
- 화면 변경이 필요 없으면 불필요한 navigate를 만들지 않는다.

[메뉴 이름]
- 아래 컨텍스트에 있는 메뉴 이름만 사용한다.
- 후보가 2개 이상이면 확인 질문을 한다(추측 금지).

[수량 처리]
- "두 잔", "세 개", "2개" → cart_add의 quantity에 반영.
- "하나 더" / "같은 거 추가" → 직전 메뉴와 동일한 옵션으로 cart_add(quantity=1).

[수정/취소 판단]
- "취소"의 범위를 문맥으로 판단:
  · option_select에서 → 현재 메뉴 선택만 취소, 메뉴 탐색으로 돌아감.
  · cart_review에서 "~~ 취소/빼줘" → 해당 항목만 cart_remove.
  · "전부 취소" / "주문 취소" → end_conversation.
  · 모호하면 확인: "주문 전체를 취소할까요?"
- cart_review / payment_confirm에서 같은 메뉴가 여러 줄이면 현재 장바구니 블록의
  line_id, option_item_ids를 참고해 cart_remove / cart_update에 함께 넣어 정확히 가리킨다.

[단계 이동]
- 단계는 선형이 아니다. 사용자 요청에 따라 건너뛰거나 되돌아갈 수 있다.
- "다시 메뉴 보여줘" → menu_browse로 이동.
- "하나 더 추가할게" (cart_review/payment에서) → category_browse로 이동.
- 장바구니가 비어 있으면 결제/주문 확정을 하지 않는다.

[핵심 제약]
- 아래 데이터에 있는 메뉴/옵션/카테고리만 사용. 없는 것을 만들지 않는다.
- option_item_ids는 아래 데이터에 명시된 id 정수만 사용. 임의의 숫자 금지.
- 연속 이해 실패 시 선택지를 제시한다.
- 주문과 무관한 대화는 짧게 거절하고 주문으로 유도.

[대화 이력]
- 이전 턴에서 사용자가 이미 답한 정보를 다시 묻지 않는다.

[few-shot 예시]
- 입력: "커피 보여줘"
  출력 핵심: navigate(target=category, category_name="커피"), next_stage=menu_browse
- 입력: "아이스 아메리카노"
  출력 핵심: navigate(target=menu_detail, menu_name="아이스 아메리카노"), next_stage=option_select
- 입력: "그란데로 해줘"
  조건: 현재 메뉴가 이미 선택됨
  출력 핵심: option_preview(menu_name=<현재 메뉴>, option_item_ids=[...]) 또는 필수 옵션이 모두 충족되면 cart_add
- 입력: "이거 빼줘"
  조건: cart_review이고 같은 메뉴가 여러 줄 있음
  출력 핵심: cart_remove에 cart_line_id 또는 option_item_ids를 함께 포함
- 입력: "결제할게"
  조건: 장바구니가 비어 있지 않음
  출력 핵심: navigate(target=payment) 또는 place_order

{persona}

{runtime_context}

{stage}

{stage_context}

{cart_snapshot}
"""


def _format_cart(cart_snapshot: Optional[list]) -> str:
    if not cart_snapshot:
        return "[현재 장바구니] 비어 있음"
    lines = ["[현재 장바구니]"]
    total = 0
    for item in cart_snapshot:
        line_id = item.get("line_id", "") if isinstance(item, dict) else item.line_id
        option_names = item.get("option_names", []) if isinstance(item, dict) else item.option_names
        option_item_ids = item.get("option_item_ids", []) if isinstance(item, dict) else item.option_item_ids
        menu_name = item.get("menu_name", "") if isinstance(item, dict) else item.menu_name
        unit_price = item.get("unit_price", 0) if isinstance(item, dict) else item.unit_price
        quantity = item.get("quantity", 0) if isinstance(item, dict) else item.quantity
        option_bits = []
        for idx, option_name in enumerate(option_names):
            option_id = option_item_ids[idx] if idx < len(option_item_ids) else None
            option_bits.append(f"{option_name}#{option_id}" if option_id else option_name)
        opt = f" ({', '.join(option_bits)})" if option_bits else ""
        subtotal = unit_price * quantity
        total += subtotal
        line_prefix = f"- line_id={line_id} " if line_id else "- "
        lines.append(f"{line_prefix}{menu_name}{opt} x{quantity} = {subtotal:,}원")
    lines.append(f"합계: {total:,}원")
    return "\n".join(lines)


def build_system_prompt(
    *,
    persona: str,
    runtime_context: str,
    stage: str,
    stage_context: str,
    cart_snapshot: Optional[list] = None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        persona=PERSONAS.get(persona, PERSONAS["unknown"]),
        runtime_context=runtime_context or "",
        stage=STAGES.get(stage, STAGES["greeting"]),
        stage_context=stage_context or "",
        cart_snapshot=_format_cart(cart_snapshot),
    )
