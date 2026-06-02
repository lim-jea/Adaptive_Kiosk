// 결제 페이지 — 결제 수단 선택 + 직원 호출
import { useState, useCallback, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { buildOrderPayload } from '../utils/orderPayload'
import { getCompleteRoute } from '../utils/routes'
import { splitVAT } from '../utils/price'
import PaymentMethodGrid from '../components/PaymentMethodGrid'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

const PAYMENT_METHODS = [
  {
    id: 'apple_pay',
    label: '애플페이',
    desc: 'Face ID / Touch ID로 결제',
  },
  {
    id: 'samsung_pay',
    label: '삼성페이',
    desc: '삼성 Pay로 간편 결제',
  },
  {
    id: 'naver_pay',
    label: '네이버페이',
    desc: '네이버페이 포인트·머니 결제',
  },
  {
    id: 'card',
    label: '카드 결제',
    desc: 'IC카드 또는 마그네틱 결제',
  },
]

export default function PaymentPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { discountType = null, discountLabel = null, discountRate = 0 } = location.state || {}

  // 'idle' | 'processing' | 'calling_staff' | 'done'
  const [status, setStatus] = useState('idle')
  const [selectedMethod, setSelectedMethod] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const MAX_RETRY = 3

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)
  const discountAmount = Math.floor(totalPrice * discountRate)
  const finalPrice = totalPrice - discountAmount
  const vat = splitVAT(finalPrice)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('payment', {
        total_price: totalPrice,
        total_count: totalCount,
        discount_type: discountType,
      })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('payment', Date.now() - enteredAt)
    }
  }, [logger, state.sessionUuid, totalCount, totalPrice, discountType])

  const handlePay = useCallback(async (method) => {
    logger.log('payment', 'payment', {
      actionName: 'payment_method_select',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: { total_price: totalPrice, total_count: totalCount, discount_type: discountType },
    })
    logger.log('payment', 'payment', {
      actionName: 'payment_start',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: {
        total_price: finalPrice,
        original_price: totalPrice,
        discount_amount: discountAmount,
        total_count: totalCount,
        discount_type: discountType,
        order_type: state.orderType,
        used_recommendation: state.cart.some((item) => item.fromRecommendation),
      },
    })
    setSelectedMethod(method)
    setStatus('processing')
    setErrorMessage('')

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    const orderStartedAt = performance.now()
    try {
      const res = await api.post('/api/v1/orders', buildOrderPayload(state.sessionUuid, state.cart, {
        orderType: state.orderType,
        discountType,
        discountAmount,
      }))
      orderUuid = res.data.order_uuid
      logClientTiming('payment.createOrder', performance.now() - orderStartedAt, { order_uuid: orderUuid })
      logger.log('order', 'payment', {
        actionName: 'order_submit_success',
        targetType: 'order',
        targetId: orderUuid,
        payload: { total_price: totalPrice, total_count: totalCount },
        source: 'system',
      })
    } catch (err) {
      logClientTiming('payment.createOrder.error', performance.now() - orderStartedAt, {
        session_uuid: state.sessionUuid,
      })
      console.error('주문 저장 실패:', err)
      const nextRetry = retryCount + 1
      logger.log('order', 'payment', {
        actionName: 'order_submit_error',
        payload: { message: err?.message || 'order_submit_failed', retry_count: nextRetry },
        source: 'system',
      })
      setRetryCount(nextRetry)

      if (nextRetry >= MAX_RETRY) {
        logger.log('payment', 'payment', { actionName: 'payment_retry_exhausted', source: 'system', payload: { max_retry: MAX_RETRY } })
        setStatus('calling_staff')
        setErrorMessage(`결제가 ${MAX_RETRY}회 실패했습니다. 직원을 호출했습니다.`)
        // calling_staff 오버레이는 자동으로 닫혀 사용자가 결제 화면에 묶이지 않도록 한다.
        setTimeout(() => setStatus('idle'), 3000)
        return
      }
      setStatus('idle')
      setErrorMessage(`주문 생성에 실패했습니다. (${nextRetry}/${MAX_RETRY}) 잠시 후 다시 시도해주세요.`)
      return
    }

    setStatus('done')
    const flushStartedAt = performance.now()
    await logger.flush()
    logClientTiming('payment.loggerFlush', performance.now() - flushStartedAt, {
      session_uuid: state.sessionUuid,
    })
    navigate(getCompleteRoute(state.ageGroup), {
      replace: true,
      state: {
        paymentMethod: method.label,
        totalPrice: finalPrice,
        discountAmount,
        discountLabel,
        discountType,
        totalCount,
        orderUuid,
        isMembership: ['employee', 'skt', 'lg'].includes(discountType),
      },
    })
  }, [logger, navigate, state, totalCount, totalPrice, finalPrice, discountAmount, discountType, discountLabel, retryCount])

  const handleCallStaff = () => {
    logger.log('click', 'payment', {
      actionName: 'call_staff',
      targetType: 'button',
      targetLabel: 'call_staff',
    })
    setStatus('calling_staff')
    setTimeout(() => setStatus('idle'), 2000)
  }

  // 테스트 배포용: 무동작 자동 복귀 비활성화 (각 사용자에게 보내 자유롭게 둘러볼 수 있도록).
  // 향후 운영 시 useIdleTimeout / IdleWarningOverlay 를 다시 도입하면 된다.

  // 결제 중 오버레이
  if (status === 'processing') {
    return (
      <div className="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <div className="w-16 h-16 mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl font-bold text-amber-600">결제</span>
        </div>
        <div className="w-12 h-12 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">결제 중...</h2>
        <p className="text-gray-400">{selectedMethod?.label}으로 처리하고 있어요</p>
        <p className="text-amber-600 font-bold mt-4 text-xl">{finalPrice.toLocaleString()}원</p>
      </div>
    )
  }

  // 직원 호출 중 오버레이
  if (status === 'calling_staff') {
    return (
      <div className="fixed inset-0 bg-amber-900/95 flex flex-col items-center justify-center z-50">
        <div className="text-7xl mb-6 animate-pulse">🔔</div>
        <h2 className="text-2xl font-black text-white mb-3">직원을 호출 중입니다</h2>
        <p className="text-amber-200/80 text-sm">잠시만 기다려 주세요</p>
        <div className="mt-8 flex gap-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2.5 h-2.5 rounded-full bg-amber-300 animate-bounce"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>
      </div>
    )
  }

  const isChild = state.ageGroup === '어린이'

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f9f5f0' }}>

      {/* 헤더 */}
      <header className="bg-white shadow-sm px-5 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button
          onClick={() => navigate('/discount')}
          className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-800">결제</h1>
          <p className="text-xs text-gray-400">결제 수단을 선택해주세요</p>
        </div>
      </header>

      <div className={`flex-1 px-4 py-5 space-y-5 ${isChild ? 'pb-[380px]' : 'pb-6'}`}>
        {DEMO_MODE && (
          <div className="rounded-xl px-4 py-2 bg-yellow-50 border border-yellow-200 text-yellow-800 text-xs font-bold text-center">
            🧪 테스트 결제 모드 · 실제 결제는 발생하지 않습니다
          </div>
        )}
        {/* 금액 요약 */}
        <div className="bg-white rounded-2xl px-5 py-4 shadow-sm border border-gray-100 space-y-2">
          <div className="flex justify-between items-center text-sm text-gray-400">
            <span>상품 금액 ({totalCount}개)</span>
            <span className={discountAmount > 0 ? 'line-through' : ''}>
              {totalPrice.toLocaleString()}원
            </span>
          </div>
          {discountAmount > 0 && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-green-600 font-semibold">
                {discountLabel} ({Math.round(discountRate * 100)}% 할인)
              </span>
              <span className="text-green-600 font-semibold">
                -&nbsp;{discountAmount.toLocaleString()}원
              </span>
            </div>
          )}
          <div className="pt-1 border-t border-gray-100 space-y-1">
            <div className="flex justify-between items-center text-xs text-gray-400">
              <span>공급가액</span>
              <span>{vat.net.toLocaleString()}원</span>
            </div>
            <div className="flex justify-between items-center text-xs text-gray-400">
              <span>부가세 (10%)</span>
              <span>{vat.tax.toLocaleString()}원</span>
            </div>
            <div className="flex justify-between items-center pt-1">
              <span className="text-base font-bold text-gray-800">최종 결제 금액</span>
              <span className="text-2xl font-black text-amber-600">{finalPrice.toLocaleString()}원</span>
            </div>
          </div>
        </div>

        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl px-5 py-4 font-bold text-sm">
            {errorMessage}
          </div>
        )}

        {/* 주문 내역 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">주문 내역</p>
          </div>
          <div className="divide-y">
            {state.cart.map((item) => {
              const optionLabel = (item.optionLabels || []).join(' · ')
              return (
                <div key={item.cartItemId} className="px-4 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {item.displayName}
                      <span className="text-amber-600 ml-1">×{item.quantity}</span>
                    </p>
                    {optionLabel && (
                      <p className="text-xs text-gray-400 mt-0.5">{optionLabel}</p>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-gray-700">
                    {(item.unitPrice * item.quantity).toLocaleString()}원
                  </p>
                </div>
              )
            })}
          </div>
        </div>

        {/* 결제 수단 — 일반(비어린이)만 스크롤 영역에 표시 */}
        {!isChild && (
          <>
            <div>
              <p className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1 mb-3">
                결제 수단
              </p>
              <PaymentMethodGrid methods={PAYMENT_METHODS} onSelect={handlePay} />
            </div>
            <button
              onClick={handleCallStaff}
              className="
                w-full min-h-[52px] rounded-2xl border-2 border-amber-300
                bg-amber-50 hover:bg-amber-100 active:bg-amber-200
                text-amber-700 font-bold text-base
                flex items-center justify-center gap-2
                active:scale-[0.98] transition-all duration-150
              "
            >
              <span className="text-xl">🔔</span>
              직원 호출
            </button>
            <p className="text-center text-xs text-gray-400 pb-4">
              결제 수단을 탭하면 바로 결제가 시작됩니다
            </p>
          </>
        )}
      </div>

      {/* 어린이 — 하단 고정 결제 수단 패널 */}
      {isChild && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 shadow-2xl px-4 pt-4 pb-6">
          <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">결제 수단 선택</p>
          <PaymentMethodGrid methods={PAYMENT_METHODS} onSelect={handlePay} compact className="mb-3 gap-2" />
          <button
            onClick={handleCallStaff}
            className="
              w-full min-h-[44px] rounded-xl border-2 border-amber-300
              bg-amber-50 hover:bg-amber-100 active:bg-amber-200
              text-amber-700 font-bold text-sm
              flex items-center justify-center gap-2
              active:scale-[0.98] transition-all duration-150
            "
          >
            <span>🔔</span>
            직원 호출
          </button>
          <p className="text-center text-xs text-gray-400 mt-2">결제 수단을 탭하면 바로 결제가 시작됩니다</p>
        </div>
      )}
    </div>
  )
}
