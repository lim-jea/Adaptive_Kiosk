// 추천 패널 표시 여부 판단 유틸
// RecommendationPanel 내부의 isUnderage 체크와 동일 조건을 사용해, 패널이 null 을 반환할 때
// 키오스크 페이지의 사이드바 슬롯도 함께 숨기도록 한다.
// 그렇지 않으면 패널은 비어있는데 wrapper 가 lg:w-72 공간을 차지해 오른쪽이 빈 채로 남는다.

export function shouldShowRecommendation({
  ageGroup = null,
  ageEst = null,
  isChild = false,
  hasUserProfile = true,
  allowUnderage = false,
}) {
  if (isChild) return false
  if (!hasUserProfile) return false
  if (allowUnderage) return true
  const age = Number(ageEst)
  if (Number.isFinite(age) && age < 20) return false
  if (ageGroup === '어린이' || ageGroup === '10~19' || ageGroup === 'child') return false
  return true
}
