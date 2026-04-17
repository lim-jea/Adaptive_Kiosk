"""
Voice matching helpers.

입력 정제, jailbreak 차단, fast-path 패턴 매칭, 메뉴 이름 직접 매칭을
한 곳에 모아 음성 주문의 빠른 경로를 정리한 모듈이다.
"""
import re
from typing import Optional

from schemas import AIChatResponse, EndConversationAction, NavigateAction, SpeakAction
from services.canned_responses import compose_template


_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_ZW_RE = re.compile(r"[\u200B-\u200F\uFEFF]")
_WS_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\s\.,!?~…·'\"()\[\]{}]+|[\s\.,!?~…·'\"()\[\]{}]+$")

_JAILBREAK_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"(disregard|forget|override)\s+(all\s+)?(previous|above|prior|your)\s+(instructions?|prompts?|rules?|guidelines?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(DAN|jailbr[eo]ken|unfiltered|unrestricted)", re.IGNORECASE),
    re.compile(r"(act|pretend|behave)\s+as\s+if\s+(you\s+have\s+)?no\s+(restrictions?|rules?|filters?|limits?)", re.IGNORECASE),
    re.compile(r"(시스템|이전|위의?)\s*(프롬프트|지시|규칙|명령).{0,10}(무시|잊어|무효|취소|삭제)", re.IGNORECASE),
    re.compile(r"(모든|전부|다)\s*(제한|규칙|필터|제약).{0,10}(무시|해제|풀어|없애)", re.IGNORECASE),
    re.compile(r"(역할|모드).{0,10}(바꿔|변경|전환).{0,10}(제한\s*없)", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


class JailbreakDetectedError(Exception):
    pass


_FILLER_WORDS = frozenset({"어", "음", "으", "아", "에", "엉", "흠", "어어", "음음", "으으"})


def _strip_edge_punct(text: str) -> str:
    return _EDGE_PUNCT_RE.sub("", text or "").strip()


def sanitize_input(text: str) -> str:
    cleaned = _CTRL_RE.sub("", text or "")
    cleaned = _ZW_RE.sub("", cleaned)
    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = cleaned.strip()
    cleaned = _strip_edge_punct(cleaned)
    cleaned = _WS_RE.sub(" ", cleaned)

    if not cleaned:
        return ""

    compact = re.sub(r"[\s\.,!?~…·]", "", cleaned)
    if compact and all(token in _FILLER_WORDS for token in re.findall(r"[가-힣]+", compact) or [compact]):
        if compact in _FILLER_WORDS:
            return ""

    return cleaned


def check_jailbreak(text: str) -> None:
    for pattern in _JAILBREAK_PATTERNS:
        if pattern.search(text):
            raise JailbreakDetectedError("부적절한 요청이 감지되었습니다.")


_VOICE_ORDER_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^(안녕|하이|헬로|여보세요|주문\s*시작|시작\s*해|반갑|반갑습)", re.IGNORECASE), "greet",
     "안녕하세요. 어떤 음료로 주문하시겠어요?"),
    (re.compile(r"(취소|주문\s*취소|전부\s*취소|전체\s*취소|그만|괜찮아|괜찮아요|종료|중단|됐어|됐습니다)", re.IGNORECASE), "cancel",
     "취소 도와드릴게요."),
    (re.compile(r"(도와|설명|사용법|방법|모르겠|어떻게|안내)", re.IGNORECASE), "help",
     "원하시는 음료 이름을 말씀해 주세요. 추천이 필요하시면 '추천해줘'라고 해주세요."),
    (re.compile(r"^(네|응|좋아|좋습니다|좋아요|맞아|맞습니다|그래|그래요|ok)$", re.IGNORECASE), "affirm",
     "네, 알겠습니다."),
    (re.compile(r"^(아니|아뇨|아니야|싫어|별로|아닌데|아니오)$", re.IGNORECASE), "deny",
     "알겠습니다. 다른 걸 도와드릴까요?"),
    (re.compile(r"(다시|뭐라고|못\s*들었|한\s*번\s*더)", re.IGNORECASE), "repeat",
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
            end = False
            actions = []

            if intent == "cancel":
                lower = (text or "").lower()
                explicit_all = any(keyword in lower for keyword in ("전부", "전체", "주문"))
                if stage in ("greeting", "category_browse") or explicit_all:
                    response_text = "주문을 취소할게요. 다음에 또 오세요."
                    actions = [SpeakAction(text=response_text), EndConversationAction()]
                    end = True
                else:
                    response_text = "지금 선택을 취소할까요? 주문 전체를 취소할까요?"
                    actions = [SpeakAction(text=response_text)]
            else:
                actions = [SpeakAction(text=response_text)]

            next_stage = "category_browse" if intent == "greet" and stage == "greeting" else None
            return AIChatResponse(
                intent=intent,
                response_text=response_text,
                next_stage=next_stage,
                actions=actions,
                requires_user_input=not end,
                end_conversation=end,
            )
    return None


_MENU_NORMALIZE_RE = re.compile(r"[\s\-_/\\,.!?~…'\"()\[\]{}]+")


def _normalize_menu_key(text: str) -> str:
    normalized = (text or "").strip().lower()
    return _MENU_NORMALIZE_RE.sub("", normalized)


_COMMON_MENU_ALIASES = {
    "아아": "아이스 아메리카노",
    "뜨아": "따뜻한 아메리카노",
    "아샷추": "아이스 아메리카노",
    "뜨샷추": "따뜻한 아메리카노",
}


def match_menu_name(text: str, menu_names: list[str]) -> Optional[AIChatResponse]:
    if not text:
        return None

    normalized_user = _normalize_menu_key(text)
    if not normalized_user:
        return None

    menu_map: dict[str, str] = {}
    for menu_name in menu_names:
        if not menu_name:
            continue
        key = _normalize_menu_key(menu_name)
        if not key:
            continue
        previous = menu_map.get(key)
        if previous is None or len(menu_name) > len(previous):
            menu_map[key] = menu_name

    for alias, canonical in _COMMON_MENU_ALIASES.items():
        if alias in text:
            key = _normalize_menu_key(canonical)
            if key in menu_map:
                name = menu_map[key]
                response = compose_template("menu_selected", menu=name) or f"{name} 선택하셨어요. 옵션을 골라주세요."
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

    sorted_names = sorted(menu_map.values(), key=len, reverse=True)
    for menu_name in sorted_names:
        key = _normalize_menu_key(menu_name)
        if key and key in normalized_user:
            response = compose_template("menu_selected", menu=menu_name) or f"{menu_name} 선택하셨어요. 옵션을 골라주세요."
            return AIChatResponse(
                intent="select_menu",
                response_text=response,
                next_stage="option_select",
                actions=[
                    NavigateAction(target="menu_detail", menu_name=menu_name),
                    SpeakAction(text=response),
                ],
                requires_user_input=True,
                end_conversation=False,
            )
    return None
