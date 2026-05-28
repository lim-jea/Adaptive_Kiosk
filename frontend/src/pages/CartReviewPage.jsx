// 주문 확인 페이지 — 담은 메뉴 전체 확인 후 결제 진행 or 추가 주문 선택

import { useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { getKioskRoute, getPaymentRoute } from '../utils/routes'
import { splitVAT } from '../utils/price'

export default function CartReviewPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)
  const vat = splitVAT(totalPrice)

  useEffect(() => {
    if (state.cart.length === 0) {
      navigate(getKioskRoute(state.ageGroup), { replace: true })
    }
  }, [state.ageGroup, state.cart.length, navigate])

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('cart_review', { total_price: totalPrice, total_count: totalCount })
    return () => logger.logScreenExit('cart_review', Date.now() - enteredAt)
  }, [logger, totalCount, totalPrice])

  // 카트 변경 시 서버에도 PUT 동기화.
  // KioskPage 가 마지막으로 동기화한 카트가 그대로 전달된다는 가정 하에,
  // 마운트 시점의 signature 를 baseline 으로 잡고 그 이후의 변경만 PUT 으로 반영한다.
  // 이렇게 하지 않으면 CartReview 에서 수량 변경/삭제 후 "추가 주문" 으로 KioskPage 에 돌아가면
  // 서버의 이전 카트가 다시 불러와져 변경이 사라지는 회귀가 발생한다.
  const serializeCartForSync = useCallback((cart) => JSON.stringify(
    cart.map((item) => ({
      menu_name: item.menuName,
      quantity: item.quantity,
      from_recommendation: Boolean(item.fromRecommendation),
      selected_options: item.selectedOptions || [],
    }))
  ), [])

  // 마지막 PUT 동기화 Promise — navigate 핸들러가 기다릴 수 있도록 보관.
  // (그렇지 않으면 사용자가 수량 변경 직후 "추가 주문"을 누르면 PUT 완료 전에 navigate 되어
  //  KioskPage 가 이전 서버 카트를 GET 해 변경이 사라지는 race 가 발생한다.)
  const baselineCartSignatureRef = useRef(null)
  const pendingSyncRef = useRef(Promise.resolve())
  useEffect(() => {
    if (!state.sessionUuid) return
    const signature = serializeCartForSync(state.cart)
    if (baselineCartSignatureRef.current === null) {
      baselineCartSignatureRef.current = signature
      return
    }
    if (signature === baselineCartSignatureRef.current) return

    let cancelled = false
    pendingSyncRef.current = (async () => {
      try {
        await api.put(`/api/v1/carts/${state.sessionUuid}`, {
          items: state.cart.map((item) => ({
            menu_name: item.menuName,
            quantity: item.quantity,
            from_recommendation: Boolean(item.fromRecommendation),
            selected_options: item.selectedOptions || [],
          })),
        })
        if (!cancelled) baselineCartSignatureRef.current = signature
      } catch (err) {
        console.error('CartReview 카트 동기화 실패:', err)
      }
    })()
    return () => { cancelled = true }
  }, [state.sessionUuid, state.cart, serializeCartForSync])

  const handleAddMore = async () => {
    logger.log('navigation', 'cart_review', {
      actionName: 'add_more_items',
      targetType: 'button',
      targetLabel: 'back_to_kiosk',
    })
    // 미완료 카트 동기화가 있으면 기다린 뒤 이동 — KioskPage 의 GET cart 가 옛 데이터를 받지 않도록.
    await pendingSyncRef.current
    navigate(getKioskRoute(state.ageGroup))
  }

  const handleQtyChange = (item, delta) => {
    const nextQuantity = item.quantity + delta
    logger.log('cart', 'cart_review', {
      actionName: 'cart_qty_change',
      targetType: 'cart_item',
      targetId: item.cartItemId,
      targetLabel: item.menuName,
      payload: {
        previous_quantity: item.quantity,
        next_quantity: nextQuantity,
      },
    })
    dispatch({
      type: ACTIONS.UPDATE_CART_QTY,
      payload: { cartItemId: item.cartItemId, quantity: nextQuantity },
    })
  }

  const handleRemove = (item) => {
    logger.log('cart', 'cart_review', {
      actionName: 'cart_remove',
      targetType: 'cart_item',
      targetId: item.cartItemId,
      targetLabel: item.menuName,
    })
    dispatch({
      type: ACTIONS.REMOVE_FROM_CART,
      payload: { cartItemId: item.cartItemId },
    })
  }

  const handleEditOptions = async (item) => {
    logger.log('cart', 'cart_review', {
      actionName: 'cart_edit_open',
      targetType: 'cart_item',
      targetId: item.cartItemId,
      targetLabel: item.menuName,
      payload: { menu_name: item.menuName, option_item_ids: (item.selectedOptions || []).map((o) => o.option_item_id) },
    })
    await pendingSyncRef.current
    dispatch({
      type: ACTIONS.SET_EDIT_TARGET,
      payload: { cartItemId: item.cartItemId, source: 'cart_review' },
    })
    navigate(getKioskRoute(state.ageGroup))
  }

  const handleProceed = async () => {
    logger.log('navigation', 'cart_review', {
      actionName: 'proceed_to_discount',
      targetType: 'button',
      targetLabel: 'proceed',
    })
    await pendingSyncRef.current
    if (state.ageGroup === '청년' || !state.ageGroup) {
      navigate('/discount')
      return
    }
    navigate(getPaymentRoute(state.ageGroup))
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f9f5f0' }}>

      {/* 헤더 */}
      <header className="bg-white shadow-sm px-5 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button
          onClick={handleAddMore}
          className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-800">주문 확인</h1>
          <p className="text-xs text-gray-400">총 {totalCount}개 항목</p>
        </div>
      </header>

      {/* 주문 목록 */}
      <div className="flex-1 px-4 py-5 space-y-3 pb-44">
        <p className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1 mb-4">
          담은 메뉴
        </p>

        {state.cart.map((item, idx) => {
          const optionLabel = (item.optionLabels || []).join(' · ')
          return (
            <div
              key={item.cartItemId}
              className="bg-white rounded-2xl px-5 py-4 shadow-sm border border-gray-100 flex items-start gap-4"
            >
              {/* 번호 */}
              <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-600 font-black text-sm flex items-center justify-center flex-shrink-0 mt-0.5">
                {idx + 1}
              </div>

              {item.menuImageUrl ? (
                <img
                  src={item.menuImageUrl}
                  alt=""
                  className="w-16 h-16 rounded-xl object-cover flex-shrink-0"
                  onError={(event) => {
                    event.currentTarget.style.display = 'none'
                  }}
                />
              ) : (
                <div className="w-16 h-16 rounded-xl bg-amber-50 flex items-center justify-center text-3xl flex-shrink-0">
                  {item.menuEmoji || '☕'}
                </div>
              )}

              {/* 메뉴 정보 */}
              <div className="flex-1 min-w-0">
                <p className="font-bold text-gray-800 text-base">{item.displayName}</p>
                {optionLabel && (
                  <p className="text-sm text-gray-400 mt-0.5">{optionLabel}</p>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-xs bg-amber-50 text-amber-600 font-semibold px-2 py-0.5 rounded-full border border-amber-100">
                    {item.unitPrice.toLocaleString()}원
                  </span>
                  <span className="text-xs text-gray-400">× {item.quantity}</span>
                </div>
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <button
                    type="button"
                    onClick={() => handleQtyChange(item, -1)}
                    className="w-8 h-8 rounded-full border border-gray-300 text-gray-600 font-bold"
                  >
                    −
                  </button>
                  <span className="w-8 text-center text-sm font-black text-gray-800">{item.quantity}</span>
                  <button
                    type="button"
                    onClick={() => handleQtyChange(item, 1)}
                    className="w-8 h-8 rounded-full bg-amber-500 text-white font-bold"
                  >
                    +
                  </button>
                  <button
                    type="button"
                    onClick={() => handleEditOptions(item)}
                    className="ml-1 px-3 h-8 rounded-full border border-amber-300 text-amber-600 text-xs font-bold hover:bg-amber-50"
                  >
                    옵션 변경
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRemove(item)}
                    className="px-3 h-8 rounded-full border border-red-200 text-red-500 text-xs font-bold"
                  >
                    삭제
                  </button>
                </div>
              </div>

              {/* 소계 */}
              <div className="text-right flex-shrink-0">
                <p className="font-black text-gray-800 text-base">
                  {(item.unitPrice * item.quantity).toLocaleString()}원
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {/* 하단 고정 영역 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 shadow-2xl px-4 pt-4 pb-6">
        {/* 합계 */}
        <div className="mb-4 px-1 space-y-1">
          <div className="flex justify-between items-center text-xs text-gray-400">
            <span>공급가액</span>
            <span>{vat.net.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center text-xs text-gray-400">
            <span>부가세 (10%)</span>
            <span>{vat.tax.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center pt-1 border-t border-gray-100">
            <span className="text-gray-500 font-medium">총 결제 금액 <span className="text-[10px] text-gray-400">(부가세 포함)</span></span>
            <span className="text-2xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
          </div>
        </div>

        {/* 버튼 2개 */}
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={handleAddMore}
            className="
              min-h-[54px] rounded-2xl border-2 border-gray-200
              text-gray-600 font-bold text-base
              hover:bg-gray-50 active:scale-95
              transition-all duration-150
            "
          >
            + 추가 주문
          </button>
          <button
            onClick={handleProceed}
            className="
              min-h-[54px] rounded-2xl
              bg-amber-500 hover:bg-amber-600 active:bg-amber-700
              text-white font-bold text-base
              shadow-lg shadow-amber-200
              active:scale-95 transition-all duration-150
            "
          >
            결제 진행 →
          </button>
        </div>
      </div>
    </div>
  )
}
