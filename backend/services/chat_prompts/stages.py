"""
주문 단계(stage)별 상세 시나리오.
허용 액션, 다음/이전 stage, 핵심 행동 지침을 명시한다.
"""

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
