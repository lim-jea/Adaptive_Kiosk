"""패스트 패스 매칭.

- match_pattern: 자주 쓰이는 짧은 발화(인사/취소/긍정/부정/도움/반복/대기 등)를
    정규식으로 잡아 Gemini 호출 없이 즉시 응답을 만든다.
- match_menu_name: 사용자 발화에서 카탈로그 메뉴 이름이 보이면 바로 메뉴 상세로 이동시킨다.

주의: 음성(STT) 입력은 마침표/따옴표/공백/중복 표현이 섞이므로, 간단한 정규화 후 매칭한다.
"""
import re
from typing import Optional

from schemas import (
    AIChatResponse,
    NavigateAction,
    SpeakAction,
    EndConversationAction,
)

from services.canned_responses import compose_template, template_to_segments


# ─── 패턴 레지스트리 ─────────────────────────────────────────────────────────

_VOICE_ORDER_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^(안녕|하이|헬로|여보세요|주문\s*시작|시작\s*해|반가워|반갑)", re.IGNORECASE), "greet",
     "안녕하세요. 어떤 음료로 주문하시겠어요?"),
    (re.compile(r"(취소|주문\s*취소|전부\s*취소|전체\s*취소|그만|관둘래|관둬|끝낼래|종료|중단|됐어|됐습니다)", re.IGNORECASE), "cancel",
     "취소 도와드릴게요."),
    (re.compile(r"(도와|도움|설명|사용법|방법|모르겠|어떻게|어렵|헷갈)", re.IGNORECASE), "help",
     "원하시는 음료 이름을 말씀해 주세요. 추천이 필요하시면 '추천해줘'라고 해주세요."),
    (re.compile(r"^(네|네네|예|좋아|좋습니다|좋아요|응|응응|맞아|맞습니다|맞아요|그래|그래요|오케이|ok)$", re.IGNORECASE), "affirm",
     "네, 알겠습니다."),
    (re.compile(r"^(아니|아뇨|아니요|싫어|싫어요|별로|아닌데|아니야)$", re.IGNORECASE), "deny",
     "알겠습니다. 다른 걸 도와드릴까요?"),
    (re.compile(r"(다시|뭐라고|못\s*들었|안\s*들려|한\s*번\s*더)", re.IGNORECASE), "repeat",
     "네, 다시 말씀드릴게요."),
    (re.compile(r"(잠시만|잠깐|기다려|기다려\s*줘)", re.IGNORECASE), "wait",
     "네, 천천히 말씀하세요."),
]

PATTERN_REGISTRY: dict[str, list[tuple[re.Pattern, str, str]]] = {
    "voice_order": _VOICE_ORDER_PATTERNS,
}


def match_pattern(text: str, purpose: str = "voice_order", *, stage: Optional[str] = None) -> Optional[AIChatResponse]:
    patterns = PATTERN_REGISTRY.get(purpose, [])
    for pattern, intent, response_text in patterns:
        if pattern.search(text):
            # cancel은 stage/문구에 따라 '전체 취소'인지 '현재 단계 취소'인지가 다를 수 있어
            # fast path에서 과도하게 end_conversation을 걸지 않도록 보수적으로 처리한다.
            end = False
            actions = []

            if intent == "cancel":
                lower = (text or "").lower()
                explicit_all = any(k in lower for k in ("전부", "전체", "주문"))
                if stage in ("greeting", "category_browse") or explicit_all:
                    response_text = "주문을 취소할게요. 다음에 또 오세요."
                    actions = [SpeakAction(text=response_text), EndConversationAction()]
                    end = True
                else:
                    response_text = "지금 선택을 취소할까요, 주문 전체를 취소할까요?"
                    actions = [SpeakAction(text=response_text)]
                    end = False
            else:
                actions = [SpeakAction(text=response_text)]

            next_stage = None
            if intent == "greet" and stage == "greeting":
                next_stage = "category_browse"

            return AIChatResponse(
                intent=intent,
                response_text=response_text,
                next_stage=next_stage,
                actions=actions,
                requires_user_input=not end,
                end_conversation=end,
            )
    return None


_MENU_NORMALIZE_RE = re.compile(r"[\s\-_/\\,.!?~…·'\"()\[\]{}]+")


def _normalize_menu_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = _MENU_NORMALIZE_RE.sub("", s)
    return s


_COMMON_MENU_ALIASES = {
    "아아": "아이스 아메리카노",
    "뜨아": "따뜻한 아메리카노",
    "아샷추": "아이스 아메리카노",
    "뜨샷추": "따뜻한 아메리카노",
}


def match_menu_name(text: str, menu_names: list[str]) -> Optional[AIChatResponse]:
    """사용자 발화에 메뉴 이름이 포함되면 메뉴 상세로 이동.

    - 공백/구두점 차이를 무시해 매칭률을 올린다.
    - '아아/뜨아' 같은 흔한 축약어는 카탈로그에 있으면 해당 메뉴로 정규화한다.
    - 긴 이름을 우선하여 부분 매칭 오탐을 줄인다.
    """
    if not text:
        return None

    normalized_user = _normalize_menu_key(text)
    if not normalized_user:
        return None

    # 정규화된 메뉴 키 → 실제 메뉴명
    menu_map: dict[str, str] = {}
    for n in menu_names:
        if not n:
            continue
        k = _normalize_menu_key(n)
        if not k:
            continue
        # 같은 키가 중복될 경우 긴 이름을 우선
        prev = menu_map.get(k)
        if prev is None or len(n) > len(prev):
            menu_map[k] = n

    # 별칭 우선
    for alias, canonical in _COMMON_MENU_ALIASES.items():
        if alias in text:
            key = _normalize_menu_key(canonical)
            if key in menu_map:
                name = menu_map[key]
                response = compose_template("menu_selected", menu=name) or f"{name} 선택하셨어요. 옵션을 골라주세요."
                segments = template_to_segments("menu_selected", menu=name)
                return AIChatResponse(
                    intent="select_menu",
                    response_text=response,
                    next_stage="option_select",
                    actions=[
                        NavigateAction(target="menu_detail", menu_name=name),
                        SpeakAction(text=response),
                    ],
                    audio_segments=segments,
                    requires_user_input=True,
                    end_conversation=False,
                )

    # 긴 이름 우선 부분 매칭
    sorted_names = sorted(menu_map.values(), key=len, reverse=True)
    for name in sorted_names:
        key = _normalize_menu_key(name)
        if key and key in normalized_user:
            response = compose_template("menu_selected", menu=name) or f"{name} 선택하셨어요. 옵션을 골라주세요."
            segments = template_to_segments("menu_selected", menu=name)
            return AIChatResponse(
                intent="select_menu",
                response_text=response,
                next_stage="option_select",
                actions=[
                    NavigateAction(target="menu_detail", menu_name=name),
                    SpeakAction(text=response),
                ],
                audio_segments=segments,
                requires_user_input=True,
                end_conversation=False,
            )
    return None
