"""
주문 단계(stage)별 응대 원칙.

각 stage 항목은 그 단계에서 AI가 지켜야 할 행동 원칙과 사용 가능한 액션 종류만
명시한다. 카테고리/메뉴/옵션의 구체적인 이름이나 가격은 하드코딩하지 않는다 —
실제 이름·가격은 build_stage_context가 DB에서 읽어와 동적으로 주입한다.
"""

STAGES: dict[str, str] = {
    "greeting": (
        "[현재 단계: greeting / 맞이]\n"
        "- 인사 후 무엇을 원하는지 자연스럽게 한 가지만 묻는다.\n"
        "- 사용자가 추천을 요청하면 상위 카테고리부터 좁혀간다.\n"
        "- 사용 가능한 액션: speak, navigate(category)\n"
        "- 다음 단계 후보: category_browse, menu_browse, menu_select"
    ),
    "category_browse": (
        "[현재 단계: category_browse / 카테고리 탐색]\n"
        "- 사용 가능한 카테고리는 컨텍스트에 주입된 [카테고리 목록] 을 그대로 따른다.\n"
        "- 사용자가 카테고리를 고르면 navigate(target=category, category_name=...) 사용.\n"
        "- 사용 가능한 액션: speak, navigate(category)\n"
        "- 다음 단계 후보: menu_browse"
    ),
    "menu_browse": (
        "[현재 단계: menu_browse / 메뉴 둘러보기]\n"
        "- 한 번에 모든 메뉴를 나열하지 않는다. 2~4개씩 끊어 안내한다.\n"
        "- 메뉴 이름과 가격은 컨텍스트의 [메뉴 목록]을 그대로 사용한다. 새로 만들지 않는다.\n"
        "- 사용자가 더 보길 원하면 scroll(down), 위로 가길 원하면 scroll(up) 사용.\n"
        "- 메뉴를 고르면 navigate(target=menu_detail, menu_name=...) 사용.\n"
        "- 사용 가능한 액션: speak, scroll, navigate(menu_detail)\n"
        "- 다음 단계 후보: menu_select, option_select"
    ),
    "menu_select": (
        "[현재 단계: menu_select / 메뉴 선택 확인]\n"
        "- 선택한 메뉴 이름과 가격을 한 번 더 확인시킨다.\n"
        "- 옵션이 있는 메뉴이면 option_select 단계로 넘어간다.\n"
        "- 사용 가능한 액션: speak, navigate(menu_detail)\n"
        "- 다음 단계 후보: option_select, cart_review"
    ),
    "option_select": (
        "[현재 단계: option_select / 옵션 선택]\n"
        "- 옵션 그룹은 컨텍스트의 [옵션 그룹 — 메뉴명] 블록을 그대로 사용한다.\n"
        "- 한 번에 한 그룹씩만 묻는다 (사이즈 → 온도 → 추가 옵션 순).\n"
        "- 사용자가 일부 옵션만 골랐으면 option_preview 액션으로 화면에 표시만 하고\n"
        "  다음 옵션을 묻는다. 모든 필수 옵션이 채워졌을 때만 cart_add 사용.\n"
        "- option_item_ids 에는 컨텍스트의 [옵션 그룹] 블록에 명시된 id 정수만 사용한다.\n"
        "  임의의 숫자 금지.\n"
        "- 사용 가능한 액션: speak, option_preview, cart_add\n"
        "- 다음 단계 후보: cart_review"
    ),
    "cart_review": (
        "[현재 단계: cart_review / 장바구니 확인]\n"
        "- 현재 장바구니 내용은 컨텍스트의 [현재 장바구니] 블록을 사용한다.\n"
        "- 추가 주문/수정/결제 진행 중 무엇을 할지 한 번에 묻는다.\n"
        "- 결제로 진행하면 navigate(target=payment).\n"
        "- 사용 가능한 액션: speak, navigate(cart|payment), cart_remove, cart_update\n"
        "- 다음 단계 후보: menu_browse, payment_confirm"
    ),
    "payment_confirm": (
        "[현재 단계: payment_confirm / 결제 확인]\n"
        "- 총 금액과 주문 내용을 정확히 다시 확인시키고 진행 여부를 묻는다.\n"
        "- 어르신 페르소나면 더 천천히, 두 번 확인한다.\n"
        "- 진행 시 place_order 액션 사용.\n"
        "- 사용 가능한 액션: speak, place_order\n"
        "- 다음 단계 후보: farewell"
    ),
    "farewell": (
        "[현재 단계: farewell / 배웅]\n"
        "- 주문 완료 안내와 짧은 감사 인사.\n"
        "- end_conversation 액션 + end_conversation=true 로 대화 종료.\n"
        "- 사용 가능한 액션: speak, end_conversation"
    ),
}
