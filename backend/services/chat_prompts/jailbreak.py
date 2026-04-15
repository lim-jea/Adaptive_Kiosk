"""
입력 정제 + 프롬프트 우회 시도 차단.
패턴은 coala/coala-api-server/app/api/v1/ai_chat/service.py 에서 가져왔다.
"""
import re

_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_ZW_RE = re.compile(r"[\u200B-\u200F\uFEFF]")  # zero-width
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
    # STT가 끝에 붙이는 마침표/물음표/따옴표 등을 제거해서 패턴 매칭률을 올린다.
    return _EDGE_PUNCT_RE.sub("", text or "").strip()


def sanitize_input(text: str) -> str:
    cleaned = _CTRL_RE.sub("", text or "")
    cleaned = _ZW_RE.sub("", cleaned)
    cleaned = cleaned.replace("\u00A0", " ")  # nbsp
    cleaned = cleaned.strip()
    cleaned = _strip_edge_punct(cleaned)
    cleaned = _WS_RE.sub(" ", cleaned)

    if not cleaned:
        return ""

    # 필러 사운드(의미 없는 감탄사)만 있는 경우는 빈 문자열로 처리
    compact = re.sub(r"[\s\.,!?~…·]", "", cleaned)
    if compact and all(token in _FILLER_WORDS for token in re.findall(r"[가-힣]+", compact) or [compact]):
        if compact in _FILLER_WORDS:
            return ""

    return cleaned


def check_jailbreak(text: str) -> None:
    for pattern in _JAILBREAK_PATTERNS:
        if pattern.search(text):
            raise JailbreakDetectedError("부적절한 요청이 감지되었습니다.")
