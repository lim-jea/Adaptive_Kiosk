// 결제 페이지 — 결제 수단 선택 → 결제 중 → 완료 처리
import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { useTTS } from '../hooks/useTTS'
import { buildOrderPayload } from '../utils/orderPayload'
import { splitVAT } from '../utils/price'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

const PAYMENT_METHODS = [
  {
    id: 'card',
    label: '신용 / 체크카드',
    desc: 'IC칩 또는 마그네틱 결제',
  },
  {
    id: 'membership',
    label: '멤버십 카드',
    desc: '스탬프 2배 적립',
  },
  {
    id: 'samsung_pay',
    label: 'Samsung Pay',
    desc: '삼성 Pay로 간편 결제',
  },
  {
    id: 'apple_pay',
    label: 'Apple Pay',
    desc: 'Face ID / Touch ID로 결제',
  },
]

export default function SeniorPaymentPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)
  const tts = useTTS({ rate: 0.65 })
  const ttsCalledRef = useRef(false)

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | processing | done
  const [errorMessage, setErrorMessage] = useState('')

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)
  const vat = splitVAT(totalPrice)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('payment', {
        total_price: totalPrice,
        total_count: totalCount,
      })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('payment', Date.now() - enteredAt)
    }
  }, [logger, state.sessionUuid, totalCount, totalPrice])

  // ① 페이지 진입 시 TTS
  useEffect(() => {
    if (ttsCalledRef.current) return
    ttsCalledRef.current = true
    const menuList = state.cart.map((item) => `${item.displayName} ${item.quantity}개`).join(', ')
    tts.speak(`주문 내역을 확인해 주세요. ${menuList}. 총 ${totalPrice.toLocaleString()}원입니다.`)
  }, []) 

  // ② 결제수단 선택 단계로 넘어갈 때 TTS
  useEffect(() => {
    if (status === 'selecting') {
      tts.speak('결제 수단을 선택해 주세요.')
    }
  }, [status])

  // 결제 수단 선택 → 2초 처리 → 주문 API → 완료 페이지
  const handlePay = useCallback(async (method) => {
    logger.log('payment', 'payment', {
      actionName: 'payment_method_select',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: { total_price: totalPrice, total_count: totalCount },
    })
    logger.log('payment', 'payment', {
      actionName: 'payment_start',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: {
        total_price: totalPrice,
        total_count: totalCount,
        order_type: state.orderType,
        used_recommendation: state.cart.some((item) => item.fromRecommendation),
      },
    })
    setSelectedMethod(method.id)
    setStatus('processing')
    setErrorMessage('')

    await tts.speak(`${method.label}로 결제를 시작합니다.`)

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    const orderStartedAt = performance.now()
    try {
      // 주문 생성: 서버에 저장된 cart를 기준으로 생성
      const res = await api.post('/api/v1/orders', buildOrderPayload(state.sessionUuid, state.cart, {
        orderType: state.orderType,
      }))
      orderUuid = res.data.order_uuid
      logClientTiming('payment.createOrder', performance.now() - orderStartedAt, {
        order_uuid: orderUuid,
      })
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
      logger.log('order', 'payment', {
        actionName: 'order_submit_error',
        payload: { message: err?.message || 'order_submit_failed' },
        source: 'system',
      })
      setStatus('selecting')
      setErrorMessage('주문 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.')
      return
    }

    setStatus('done')
    const flushStartedAt = performance.now()
    await logger.flush()
    logClientTiming('payment.loggerFlush', performance.now() - flushStartedAt, {
      session_uuid: state.sessionUuid,
    })
    navigate('/seniorcomplete', {
      replace: true,
      state: {
        paymentMethod: method.label,
        totalPrice,
        totalCount,
        isMembership: method.id === 'membership',
        orderUuid,
      },
    })
  }, [logger, navigate, state, totalCount, totalPrice])

  // 결제 중 오버레이
  if (status === 'processing') {
    const method = PAYMENT_METHODS.find((m) => m.id === selectedMethod)
    return (
      <div className="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <div className="w-16 h-16 mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl font-bold text-amber-600">결제</span>
        </div>
        <div className="w-12 h-12 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">결제 중...</h2>
        <p className="text-gray-400">{method?.label}으로 처리하고 있어요</p>
        <p className="text-amber-600 font-bold mt-4 text-xl">{totalPrice.toLocaleString()}원</p>
      </div>
    )
  }

  // ── 주문 확인 단계 ──
  if (status === 'idle') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <header className="bg-white shadow-sm px-4 py-4 flex items-center sticky top-0 z-10">
          <button
            onClick={() => navigate('/seniorkiosk')}
            className="text-gray-500 hover:text-gray-700 p-2 -ml-2 mr-2 text-2xl font-bold"
          >
            ← 뒤로
          </button>
          <h1 className="text-2xl font-bold text-gray-800">주문 확인</h1>
        </header>

        <div className="flex-1 px-4 py-6 space-y-5">
          {DEMO_MODE && (
            <div className="rounded-xl px-4 py-3 bg-yellow-50 border-2 border-yellow-200 text-yellow-800 text-base font-bold text-center">
              🧪 테스트 결제 모드 · 실제 결제는 발생하지 않습니다
            </div>
          )}
          {/* 안내 문구 */}
          <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl px-5 py-4 text-center">
            <p className="text-2xl font-bold text-amber-700">주문하신 메뉴가 맞으신가요?</p>
            <p className="text-lg text-amber-600 mt-1">확인 후 결제를 진행해 주세요</p>
          </div>

          {/* 주문 내역 */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="px-5 py-4 border-b bg-gray-50">
              <p className="text-xl font-bold text-gray-500">주문 내역</p>
            </div>
            <div className="divide-y overflow-y-auto" style={{ maxHeight: '300px' }}>
              {state.cart.map((item) => {
                const optionLabel = (item.optionLabels || []).join(' · ')
                return (
                  <div key={item.cartItemId} className="px-5 py-4 flex items-center justify-between">
                    <div>
                      <p className="text-2xl font-bold text-gray-800">
                        {item.displayName}
                        <span className="text-amber-600 ml-2">×{item.quantity}</span>
                      </p>
                      {optionLabel && (
                        <p className="text-lg text-gray-400 mt-1">{optionLabel}</p>
                      )}
                    </div>
                    <p className="text-2xl font-bold text-gray-700">
                      {(item.unitPrice * item.quantity).toLocaleString()}원
                    </p>
                  </div>
                )
              })}
            </div>
            <div className="px-5 py-4 bg-amber-50 border-t border-amber-100 space-y-2">
              <div className="flex justify-between items-center text-lg text-gray-500">
                <span>공급가액</span>
                <span>{vat.net.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center text-lg text-gray-500">
                <span>부가세 (10%)</span>
                <span>{vat.tax.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center pt-2 border-t border-amber-200">
                <span className="text-2xl font-bold text-gray-700">총 {totalCount}개</span>
                <span className="text-3xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
              </div>
            </div>
          </div>
        </div>

        {/* 하단 버튼 */}
        <div className="px-4 pb-8 pt-2 flex gap-4">
          <button
            onClick={() => navigate('/seniorkiosk')}
            className="flex-1 py-6 rounded-2xl border-2 border-gray-300 text-gray-600 text-2xl font-bold hover:bg-gray-50 transition-colors"
          >
            수정하기
          </button>
          <button
            onClick={() => setStatus('selecting')}
            className="flex-1 py-6 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white text-2xl font-bold transition-colors"
          >
            결제하기
          </button>
        </div>
      </div>
    )
  }

  // ── 결제 수단 선택 단계 ──
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white shadow-sm px-4 py-4 flex items-center sticky top-0 z-10">
        <button
          onClick={() => setStatus('idle')}
          className="text-gray-500 hover:text-gray-700 p-2 -ml-2 mr-2 text-2xl font-bold"
        >
          ← 뒤로
        </button>
        <h1 className="text-2xl font-bold text-gray-800">결제 수단 선택</h1>
      </header>

      <div className="flex-1 px-4 py-6 space-y-5 pb-8">
        {DEMO_MODE && (
          <div className="rounded-xl px-4 py-3 bg-yellow-50 border-2 border-yellow-200 text-yellow-800 text-base font-bold text-center">
            🧪 테스트 결제 모드 · 실제 결제는 발생하지 않습니다
          </div>
        )}
        {/* 안내 문구 */}
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl px-5 py-4 text-center">
          <p className="text-xl font-bold text-amber-700">결제 수단을 선택해 주세요</p>
          <p className="text-base text-amber-600 mt-1">버튼을 누르면 바로 결제가 시작됩니다</p>
        </div>

        {/* 총 금액 */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-5 py-4 space-y-2">
          <div className="flex justify-between items-center text-lg text-gray-500">
            <span>공급가액</span>
            <span>{vat.net.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center text-lg text-gray-500">
            <span>부가세 (10%)</span>
            <span>{vat.tax.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center pt-2 border-t border-gray-100">
            <span className="text-2xl font-bold text-gray-700">총 금액</span>
            <span className="text-3xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
          </div>
        </div>

        {errorMessage && (
          <div className="bg-red-50 border-2 border-red-200 rounded-2xl px-5 py-4 text-red-700 text-xl font-bold">
            {errorMessage}
          </div>
        )}

        {/* 결제 수단 */}
        <div className="space-y-3">
          {PAYMENT_METHODS.map((method) => (
            <button
              key={method.id}
              onClick={() => handlePay(method)}
              className="w-full flex items-center gap-5 px-6 py-6 rounded-2xl border-2 bg-white text-gray-800 border-gray-200 active:scale-95 transition-all shadow-sm hover:shadow-md hover:border-gray-300"
            >
              <div className="text-left flex-1">
                <p className="font-bold text-2xl">{method.label}</p>
                <p className="text-lg mt-1 text-gray-400">
                  {method.desc}
                </p>
              </div>
              <span className="text-3xl flex-shrink-0 text-gray-300">›</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
