"""
패스트 패스 매칭.

- match_pattern: 자주 쓰이는 짧은 발화(인사/취소/긍정/부정/도움 등)를 정규식으로 잡아
  Gemini 호출 없이 즉시 응답을 만든다.
- match_menu_name: 사용자 발화에서 카탈로그 메뉴 이름이 그대로 보이면
  바로 메뉴 상세로 이동시킨다.
"""
import re
from typing import Optional

from schemas.chat import (
    AIChatResponse,
    NavigateAction,
    SpeakAction,
    EndConversationAction,
)


# ─── 패턴 레지스트리 ─────────────────────────────────────────────────────────

_VOICE_ORDER_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^(안녕|하이|여보세요|시작|반가워|반갑)"), "greet",
     "안녕하세요. 어떤 음료로 주문하시겠어요?"),
    (re.compile(r"(취소|그만|관둘래|관둬|됐어|됐습니다)"), "cancel",
     "주문을 취소할게요."),
    (re.compile(r"(도와|도움|모르겠|어떻게)"), "help",
     "원하시는 음료 이름을 말씀해 주세요. 추천이 필요하시면 '추천해줘'라고 해주세요."),
    (re.compile(r"^(네|예|좋아|좋습니다|응|맞아|맞습니다|그래)"), "affirm",
     "네, 알겠습니다."),
    (re.compile(r"^(아니|아뇨|아니요|싫어|별로)"), "deny",
     "알겠습니다. 다른 걸 도와드릴까요?"),
]

PATTERN_REGISTRY: dict[str, list[tuple[re.Pattern, str, str]]] = {
    "voice_order": _VOICE_ORDER_PATTERNS,
}


def match_pattern(text: str, purpose: str = "voice_order") -> Optional[AIChatResponse]:
    patterns = PATTERN_REGISTRY.get(purpose, [])
    for pattern, intent, response_text in patterns:
        if pattern.search(text):
            actions = [SpeakAction(text=response_text)]
            end = False
            if intent == "cancel":
                actions.append(EndConversationAction())
                end = True
            return AIChatResponse(
                intent=intent,
                response_text=response_text,
                actions=actions,
                requires_user_input=not end,
                end_conversation=end,
            )
    return None


def match_menu_name(text: str, menu_names: list[str]) -> Optional[AIChatResponse]:
    """사용자 발화에 메뉴 이름이 직접 포함되면 메뉴 상세로 이동.
    긴 이름부터 매칭해서 '아이스 카페라떼'가 '카페라떼'보다 먼저 잡히게 한다."""
    sorted_names = sorted(menu_names, key=len, reverse=True)
    for name in sorted_names:
        if name and name in text:
            response = f"{name} 선택하셨어요. 옵션을 골라주세요."
            return AIChatResponse(
                intent="select_menu",
                response_text=response,
                next_stage="option_select",
                actions=[
                    NavigateAction(target="menu_detail", menu_name=name),
                    SpeakAction(text=response),
                ],
                requires_user_input=True,
                end_conversation=False,
            )
    return None
