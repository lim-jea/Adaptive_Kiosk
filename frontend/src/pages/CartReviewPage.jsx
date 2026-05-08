// 주문 확인 페이지 — 담은 메뉴 전체 확인 후 결제 진행 or 추가 주문 선택

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

export default function CartReviewPage() {
  const navigate = useNavigate()
  const { state } = useSession()
  const logger = useLogger(state.sessionUuid)

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  useEffect(() => {
    if (state.cart.length === 0) {
      navigate('/kiosk', { replace: true })
    }
  }, [state.cart.length, navigate])

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('cart_review', { total_price: totalPrice, total_count: totalCount })
    return () => logger.logScreenExit('cart_review', Date.now() - enteredAt)
  }, [logger, totalCount, totalPrice])

  const handleAddMore = () => {
    logger.log('navigation', 'cart_review', {
      actionName: 'add_more_items',
      targetType: 'button',
      targetLabel: 'back_to_kiosk',
    })
    navigate('/kiosk')
  }

  const handleProceed = () => {
    logger.log('navigation', 'cart_review', {
      actionName: 'proceed_to_discount',
      targetType: 'button',
      targetLabel: 'proceed',
    })
    navigate('/discount')
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
        <div className="flex justify-between items-center mb-4 px-1">
          <span className="text-gray-500 font-medium">총 결제 금액</span>
          <span className="text-2xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
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
