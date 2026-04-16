"""
추천 시스템 유틸리티 함수
"""


def age_to_age_group(age: int) -> str:
    """
    사용자 나이를 age_group (나이대)로 변환

    Args:
        age: 사용자 나이 (정수)

    Returns:
        str: "20~29", "30~39", "40~49", "50+"

    Raises:
        ValueError: 유효하지 않은 나이 범위
    """
    if not isinstance(age, int) or age < 0:
        raise ValueError(f"나이는 0 이상의 정수여야 합니다. 입력값: {age}")

    if age < 20:
        raise ValueError(f"추천 시스템은 20세 이상만 지원합니다. 입력값: {age}")
    elif 20 <= age < 30:
        return "20~29"
    elif 30 <= age < 40:
        return "30~39"
    elif 40 <= age < 50:
        return "40~49"
    else:  # 50 이상
        return "50+"


def get_gender_label(gender: str) -> str:
    """
    성별 코드를 라벨로 변환

    Args:
        gender: "M" or "F"

    Returns:
        str: "남성" or "여성"
    """
    return "남성" if gender.upper() == "M" else "여성"
