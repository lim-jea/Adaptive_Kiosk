"""
주문 단계(stage)별 시나리오 가이드.

각 stage는 사용자의 현재 위치를 의미하며, 시스템 프롬프트에 동적으로 끼워넣어
AI가 현재 단계에 맞는 응답과 다음 stage를 결정하게 한다.

시나리오 작성 참고: 일반 카페 직원 매뉴얼의 응대 5단계
(맞이 → 주문받기 → 추천/확인 → 결제 안내 → 배웅).
"""

STAGES: dict[str, str] = {
    "greeting": (
        "[현재 단계: greeting / 맞이]\n"
        "- 인사 후 어떤 음료를 원하는지 자연스럽게 물어보세요.\n"
        "- 사용자가 '추천해줘'라고 하면 카테고리(커피/티/스무디 등)부터 좁혀가세요.\n"
        "- 다음 단계 후보: category_browse, menu_browse, menu_select"
    ),
    "category_browse": (
        "[현재 단계: category_browse / 카테고리 탐색]\n"
        "- 카테고리(커피/달콤한커피/블렌디드/티/달콤한티/에이드/스무디/주스)를 안내하세요.\n"
        "- 사용자가 카테고리를 고르면 NavigateAction(target=category, category_name=...)을 사용하세요.\n"
        "- 다음 단계 후보: menu_browse"
    ),
    "menu_browse": (
        "[현재 단계: menu_browse / 메뉴 둘러보기]\n"
        "- 카테고리 안의 메뉴를 2~4개씩 묶어 짧게 안내하세요. 한 번에 모두 나열하지 마세요.\n"
        "- 사용자가 더 보기를 원하면 ScrollAction을 사용하세요.\n"
        "- 사용자가 메뉴를 고르면 NavigateAction(target=menu_detail, menu_name=...)을 사용하세요.\n"
        "- 다음 단계 후보: menu_select, option_select"
    ),
    "menu_select": (
        "[현재 단계: menu_select / 메뉴 선택 확인]\n"
        "- 선택한 메뉴 이름과 가격을 한 번 더 확인시키세요.\n"
        "- 옵션이 있는 메뉴이면 option_select 단계로 넘어가세요.\n"
        "- 다음 단계 후보: option_select, cart_review"
    ),
    "option_select": (
        "[현재 단계: option_select / 옵션 선택]\n"
        "- 옵션 그룹(사이즈/온도/샷/시럽/휘핑크림/당도)을 한 번에 하나씩 물어보세요.\n"
        "- 필수 옵션이 빠지면 다시 물어보세요.\n"
        "- 옵션 결정 후 CartAddAction을 사용하세요.\n"
        "- 다음 단계 후보: cart_review"
    ),
    "cart_review": (
        "[현재 단계: cart_review / 장바구니 확인]\n"
        "- 현재 장바구니 내용을 짧게 요약해 들려주세요.\n"
        "- 추가 주문, 수정, 결제 진행 중 무엇을 할지 물어보세요.\n"
        "- 결제로 이동 시 NavigateAction(target=payment).\n"
        "- 다음 단계 후보: menu_browse, payment_confirm"
    ),
    "payment_confirm": (
        "[현재 단계: payment_confirm / 결제 확인]\n"
        "- 총 금액과 주문 내용을 정확히 다시 확인시키고 진행 여부를 물어보세요.\n"
        "- 어르신 페르소나라면 더 천천히, 두 번 확인하세요.\n"
        "- 진행 시 PlaceOrderAction을 사용하세요.\n"
        "- 다음 단계 후보: farewell"
    ),
    "farewell": (
        "[현재 단계: farewell / 배웅]\n"
        "- 주문 완료 안내와 짧은 감사 인사를 하세요.\n"
        "- end_conversation=true, EndConversationAction을 사용하세요."
    ),
}
