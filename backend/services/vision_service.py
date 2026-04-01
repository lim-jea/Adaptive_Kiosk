from schemas.vision import VisionEventCreate

# 간편모드 전환 기준 연령대
SIMPLE_MODE_AGE_GROUPS = {"60대", "70대이상"}
SIMPLE_MODE_MIN_CONFIDENCE = 0.7


def should_use_simple_mode(vision_data: VisionEventCreate) -> bool:
    """
    비전 결과를 바탕으로 간편모드 전환 여부를 판단합니다.
    - 추정 연령대가 60대 이상이고 신뢰도가 0.7 이상이면 간편모드 활성화
    """
    if not vision_data.estimated_age_group:
        return False
    if vision_data.age_confidence is None:
        return False
    return (
        vision_data.estimated_age_group in SIMPLE_MODE_AGE_GROUPS
        and vision_data.age_confidence >= SIMPLE_MODE_MIN_CONFIDENCE
    )
