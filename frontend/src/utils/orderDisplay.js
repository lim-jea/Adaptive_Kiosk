// 주문번호 표시 유틸
// 백엔드가 발급한 order_uuid (32자 hex) 의 마지막 일부를 4자리 숫자로 매핑.
// Math.random 사용 시 1/900 확률로 충돌하던 문제를 해결한다.

export function formatOrderDisplayNo(orderUuid) {
  if (!orderUuid || typeof orderUuid !== 'string') return null
  const tail = orderUuid.slice(-5)
  const num = parseInt(tail, 16)
  if (!Number.isFinite(num)) return null
  return String(num % 10000).padStart(4, '0')
}
