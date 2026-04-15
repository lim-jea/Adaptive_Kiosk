"""
주문 단계(stage)별 상세 시나리오.
허용 액션, 다음/이전 stage, 핵심 행동 지침을 명시한다.
"""

STAGES: dict[str, str] = {
    "greeting": (
        "[현재 단계: greeting / 맞이]\n"
        "- 인사 후 무엇을 원하는지 한 가지만 묻는다.\n"
        "- 추천 요청 → 카테고리부터 좁혀간다.\n"
        "- 메뉴 이름을 직접 말하면 → navigate(target=menu_detail, menu_name=...) 으로 바로 이동.\n"
        "- 허용 액션: speak, navigate(category | menu_detail)\n"
        "- 다음 stage: category_browse, menu_browse, menu_select, option_select\n"
        "- 취소/종료 시: end_conversation"
    ),
    "category_browse": (
        "[현재 단계: category_browse / 카테고리 탐색]\n"
        "- 아래 [카테고리 목록] 데이터에 있는 카테고리만 안내.\n"
        "- 카테고리 선택 → navigate(target=category, category_name=...).\n"
        "- 메뉴 이름을 직접 말하면 → navigate(target=menu_detail, menu_name=...) 으로 바로 이동.\n"
        "- 허용 액션: speak, navigate(category | menu_detail)\n"
        "- 다음 stage: menu_browse, menu_select, option_select\n"
        "- 뒤로/취소 시: greeting"
    ),
    "menu_browse": (
        "[현재 단계: menu_browse / 메뉴 둘러보기]\n"
        "- 아래 [메뉴 목록] 데이터에 있는 메뉴만 안내. 2~4개씩 끊어서.\n"
        "- 더 보기 → scroll(down). 위로 → scroll(up).\n"
        "- 메뉴 선택 → navigate(target=menu_detail, menu_name=...).\n"
        "- 허용 액션: speak, navigate(menu_detail | category), scroll\n"
        "- 다음 stage: menu_select, option_select\n"
        "- 뒤로/취소 시: category_browse"
    ),
    "menu_select": (
        "[현재 단계: menu_select / 메뉴 선택 확인]\n"
        "- 선택한 메뉴 이름과 가격을 한 번 더 확인.\n"
        "- 옵션이 있으면 option_select로 넘어간다.\n"
        "- 허용 액션: speak, navigate(menu_detail)\n"
        "- 다음 stage: option_select, cart_review\n"
        "- 뒤로/취소 시: menu_browse 또는 category_browse"
    ),
    "option_select": (
        "[현재 단계: option_select / 옵션 선택]\n"
        "- 아래 [옵션 그룹] 데이터에 있는 항목만 안내. 없는 옵션은 묻지 않는다.\n"
        "- 한 번에 한 그룹씩 묻는다.\n"
        "- '기본으로' / '다 기본' / '아무거나' → [기본] 표시된 항목을 자동 선택, 기본 없는 필수만 묻기.\n"
        "- 여러 옵션을 한 번에 말하면('톨 아이스로') → 해당하는 것 모두 option_preview.\n"
        "- 부분 선택 → option_preview. 모든 필수 완료 → cart_add.\n"
        "- option_item_ids는 아래 데이터의 id 정수만 사용. 임의의 숫자 금지.\n"
        "- 허용 액션: speak, option_preview, cart_add\n"
        "- 다음 stage: cart_review\n"
        "- 뒤로/취소 시: menu_browse (현재 메뉴 선택만 취소, 전체 주문 취소 아님)"
    ),
    "cart_review": (
        "[현재 단계: cart_review / 장바구니 확인]\n"
        "- 아래 [현재 장바구니]와 합계를 간단히 안내.\n"
        "- 추가 주문 / 수정 / 결제 중 무엇을 할지 묻는다.\n"
        "- 메뉴 이름을 직접 말하면 → 해당 메뉴로 바로 이동.\n"
        "- '결제할게' → navigate(target=payment).\n"
        "- 허용 액션: speak, navigate(category | menu_detail | payment), cart_remove, cart_update\n"
        "- 다음 stage: menu_browse, category_browse, payment_confirm\n"
        "- 뒤로/취소 시: category_browse (추가 메뉴 탐색) 또는 특정 항목만 cart_remove"
    ),
    "payment_confirm": (
        "[현재 단계: payment_confirm / 결제 확인]\n"
        "- 장바구니 합계를 정확히 안내하고 진행 여부 확인.\n"
        "- '네' / '진행' → place_order.\n"
        "- '아니요' / '잠깐' → cart_review로 돌아감.\n"
        "- '더 추가' → category_browse로 이동.\n"
        "- 허용 액션: speak, place_order, navigate(cart | category)\n"
        "- 다음 stage: farewell\n"
        "- 뒤로/취소 시: cart_review"
    ),
    "farewell": (
        "[현재 단계: farewell / 배웅]\n"
        "- 주문 완료 안내 + 감사 인사.\n"
        "- end_conversation=true + EndConversationAction.\n"
        "- 허용 액션: speak, end_conversation"
    ),
}
