"""
음성 주문 페르소나 정의.
숫자 나이(age_est)를 우선 사용하고, 없으면 문자열 age_group으로 폴백.
"""

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
    """숫자 나이(age_est) 우선, 없으면 문자열 age_group으로 폴백."""
    if age is not None:
        if age <= 12:
            return "child"
        if age <= 55:
            return "general"
        return "elderly"  # 56세 이상

    if not age_group:
        return "unknown"
    if age_group in {"노년", "60대", "70대", "80대"}:
        return "elderly"
    if age_group in {"어린이", "아동", "10대 초", "10대"}:
        return "child"
    if age_group in {"청년", "중장년", "청소년", "중년", "20대", "30대", "40대", "50대"}:
        return "general"
    return "unknown"
