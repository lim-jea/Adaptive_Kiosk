from schemas.vision import VisionEventCreate

# face_service.py의 _age_to_group()이 반환하는 값과 일치시켜야 함
# 매핑: <=12: 어린이, <=35: 청년, <=55: 중장년, >55: 노년
SIMPLE_MODE_AGE_GROUPS = {"노년"}    # 55세 초과 시 간편모드
SIMPLE_MODE_MIN_CONFIDENCE = 0.7


def should_use_simple_mode(vision_data: VisionEventCreate) -> bool:
    """
    비전 결과를 바탕으로 간편모드 전환 여부를 판단합니다.
    - 추정 연령대가 노년이고 신뢰도가 0.7 이상이면 간편모드 활성화
    """
    if not vision_data.estimated_age_group:
        return False
    if vision_data.age_confidence is None:
        return False
    return (
        vision_data.estimated_age_group in SIMPLE_MODE_AGE_GROUPS
        and vision_data.age_confidence >= SIMPLE_MODE_MIN_CONFIDENCE
    )
