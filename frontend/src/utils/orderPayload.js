// 주문 payload 빌더
// orderType (매장/포장) 과 할인 정보는 백엔드 OrderCreateRequest 에 옵셔널 필드로 전달된다.
// 백엔드는 orders.total_price 를 할인 적용된 final_price 로 저장하여 매출 분석 정확도를 보장한다.
// 매장/포장 및 할인 메타데이터는 session_activity_logs.payload_json 으로 별도 분석 가능.

export function buildOrderItems(cart) {
  return cart.map((item) => ({
    menu_name: item.menuName,
    quantity: item.quantity,
    unit_price: item.unitPrice,
    from_recommendation: Boolean(item.fromRecommendation),
    selected_options: item.selectedOptions || [],
  }))
}

export function buildOrderPayload(sessionUuid, cart, extras = {}) {
  const payload = {
    session_uuid: sessionUuid,
    items: buildOrderItems(cart),
    used_recommendation: cart.some((item) => item.fromRecommendation),
  }

  if (extras.orderType) {
    payload.order_type = extras.orderType
  }
  if (extras.discountType) {
    payload.discount_type = extras.discountType
  }
  if (typeof extras.discountAmount === 'number' && extras.discountAmount > 0) {
    payload.discount_amount = Math.max(0, Math.floor(extras.discountAmount))
  }
  return payload
}
