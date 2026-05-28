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
    id: 'samsung_pay',
    label: 'Samsung Pay',
    desc: '삼성 Pay로 간편 결제',
  },
  {
    id: 'apple_pay',
    label: 'Apple Pay',
    desc: 'Face ID / Touch ID로 결제',
  },
  {
    id: 'naver_pay',
    label: '네이버페이',
    desc: '네이버페이 포인트·머니 결제',
  },
  {
    id: 'telecom',
    label: '통신사 할인',
    desc: 'SKT · KT · LG U+ 최대 20% 할인',
    discount: 0.2,
  },
]

const TELECOM_PROVIDERS = [
  { id: 'skt', label: 'SKT', color: '#E51937', icon: '📡' },
  { id: 'kt',  label: 'KT',  color: '#BC1F2E', icon: '📶' },
  { id: 'lg',  label: 'LG U+', color: '#E4006B', icon: '📻' },
]

function NumPad({ value, onChange, maxLength = 11 }) {
  const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫']
  return (
    <div className="grid grid-cols-3 gap-2 mt-3">
      {keys.map((key, i) => (
        <button
          key={i}
          onClick={() => {
            if (key === '⌫') onChange(value.slice(0, -1))
            else if (key === '') return
            else if (value.length < maxLength) onChange(value + key)
          }}
          disabled={key === ''}
          className={`h-14 rounded-2xl text-2xl font-bold transition-all
            ${key === '' ? 'invisible' : 'bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-800'}
            ${key === '⌫' ? 'text-red-500' : ''}`}
        >
          {key}
        </button>
      ))}
    </div>
  )
}

export default function SeniorPaymentPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)
  const tts = useTTS({ rate: 0.65 })
  const ttsCalledRef = useRef(false)

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | selecting | processing | done
  const [errorMessage, setErrorMessage] = useState('')

  // 통신사 할인 팝업 상태
  const [showTelecomPopup, setShowTelecomPopup] = useState(false)
  const [telecomStep, setTelecomStep] = useState('provider') // provider | method | phone | scan | confirm
  const [selectedProvider, setSelectedProvider] = useState(null)
  const [phoneNumber, setPhoneNumber] = useState('')

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

  const handlePay = useCallback(async (method, discountRate = null) => {
    logger.log('payment', 'payment', {
      actionName: 'payment_method_select',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: { total_price: totalPrice, total_count: totalCount },
    })
    const discount = discountRate ?? method.discount ?? null
    const discountedPrice = discount ? Math.floor(totalPrice * (1 - discount)) : totalPrice
    logger.log('payment', 'payment', {
      actionName: 'payment_start',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: {
        total_price: discountedPrice,
        original_price: totalPrice,
        discount_amount: discount ? totalPrice - discountedPrice : 0,
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
      const discountAmount = discount ? totalPrice - discountedPrice : 0
      const discountType = discount
        ? (method.id === 'telecom' ? `telecom_${selectedProvider?.id || ''}` : method.id)
        : null
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
        payload: { total_price: discountedPrice, total_count: totalCount },
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
    await logger.flush()
    navigate('/seniorcomplete', {
      replace: true,
      state: {
        paymentMethod: method.id === 'telecom'
          ? `${selectedProvider?.label} 통신사 할인`
          : method.label,
        totalPrice: discountedPrice,
        totalCount,
        orderUuid,
      },
    })
  }, [logger, navigate, state, totalCount, totalPrice, selectedProvider])

  const handleTelecomClick = () => {
    setTelecomStep('provider')
    setSelectedProvider(null)
    setPhoneNumber('')
    setShowTelecomPopup(true)
  }

  const handleTelecomConfirm = () => {
    setShowTelecomPopup(false)
    const telecomMethod = PAYMENT_METHODS.find((m) => m.id === 'telecom')
    handlePay(telecomMethod, 0.2)
  }

  // 결제 중 오버레이
  if (status === 'processing') {
    const method = PAYMENT_METHODS.find((m) => m.id === selectedMethod)
    const discount = method?.discount
    const discountedPrice = discount ? Math.floor(totalPrice * (1 - discount)) : totalPrice
    return (
      <div className="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <div className="w-16 h-16 mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl font-bold text-amber-600">결제</span>
        </div>
        <div className="w-12 h-12 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">결제 중...</h2>
        <p className="text-gray-400">
          {selectedMethod === 'telecom'
            ? `${selectedProvider?.label} 통신사 할인으로 처리하고 있어요`
            : `${method?.label}으로 처리하고 있어요`}
        </p>
        {discount ? (
          <div className="mt-4 text-center">
            <p className="line-through text-lg text-gray-400">{totalPrice.toLocaleString()}원</p>
            <p className="text-amber-600 font-bold text-2xl">{discountedPrice.toLocaleString()}원
              <span className="text-base ml-1">({discount * 100}% 할인)</span>
            </p>
          </div>
        ) : (
          <p className="text-amber-600 font-bold mt-4 text-2xl">{totalPrice.toLocaleString()}원</p>
        )}
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
          <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl px-5 py-4 text-center">
            <p className="text-2xl font-bold text-amber-700">주문하신 메뉴가 맞으신가요?</p>
            <p className="text-lg text-amber-600 mt-1">확인 후 결제를 진행해 주세요</p>
          </div>

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
        <div className="bg-amber-50 border-2 border-amber-200 rounded-2xl px-5 py-4 text-center">
          <p className="text-xl font-bold text-amber-700">결제 수단을 선택해 주세요</p>
          <p className="text-base text-amber-600 mt-1">버튼을 누르면 바로 결제가 시작됩니다</p>
        </div>

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
              onClick={() => method.id === 'telecom' ? handleTelecomClick() : handlePay(method)}
              className="w-full flex items-center gap-5 px-6 py-6 rounded-2xl border-2 bg-white text-gray-800 border-gray-200 active:scale-95 transition-all shadow-sm hover:shadow-md hover:border-gray-300"
            >
              <div className="text-left flex-1">
                <p className="font-bold text-2xl">{method.label}</p>
                <p className="text-lg mt-1 text-gray-400">{method.desc}</p>
              </div>
              {method.discount && (
                <span className="text-base font-black px-3 py-1 rounded-full bg-amber-100 text-amber-600 flex-shrink-0">
                  -{method.discount * 100}%
                </span>
              )}
              <span className="text-3xl flex-shrink-0 text-gray-300">›</span>
            </button>
          ))}
        </div>
      </div>

      {/* 통신사 할인 팝업 */}
      {showTelecomPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowTelecomPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-6 bg-white"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Step 1 — 통신사 선택 */}
            {telecomStep === 'provider' && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">통신사 선택</h2>
                <p className="text-lg text-gray-400 mb-5">이용 중인 통신사를 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  {TELECOM_PROVIDERS.map((provider) => (
                    <button
                      key={provider.id}
                      onClick={() => { setSelectedProvider(provider); setTelecomStep('method') }}
                      className="w-full py-5 rounded-2xl font-bold text-white text-xl flex items-center gap-3 px-5 active:scale-95 transition-all"
                      style={{ background: provider.color }}
                    >
                      <span className="text-3xl">{provider.icon}</span>
                      <span>{provider.label}</span>
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowTelecomPopup(false)}
                  className="w-full mt-4 py-4 rounded-2xl font-bold border-2 border-gray-300 text-gray-500 text-xl"
                >
                  취소
                </button>
              </>
            )}

            {/* Step 2 — 인증 방법 선택 */}
            {telecomStep === 'method' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('provider')} className="text-gray-400 text-2xl">←</button>
                  <h2 className="text-2xl font-black text-gray-800">{selectedProvider?.label} 할인 인증</h2>
                </div>
                <p className="text-lg text-gray-400 mb-5">인증 방법을 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => setTelecomStep('phone')}
                    className="w-full py-5 rounded-2xl border-2 border-gray-200 bg-white font-bold flex items-center gap-4 px-5 active:scale-95 transition-all hover:border-amber-300"
                  >
                    <span className="text-3xl">📱</span>
                    <div className="text-left">
                      <p className="font-bold text-xl text-gray-800">전화번호 입력</p>
                      <p className="text-base text-gray-400 font-normal">등록된 번호로 인증</p>
                    </div>
                  </button>
                  <button
                    onClick={() => setTelecomStep('scan')}
                    className="w-full py-5 rounded-2xl border-2 border-gray-200 bg-white font-bold flex items-center gap-4 px-5 active:scale-95 transition-all hover:border-amber-300"
                  >
                    <span className="text-3xl">🎫</span>
                    <div className="text-left">
                      <p className="font-bold text-xl text-gray-800">쿠폰 스캔</p>
                      <p className="text-base text-gray-400 font-normal">할인 쿠폰을 카메라에</p>
                    </div>
                  </button>
                </div>
                <button
                  onClick={() => setShowTelecomPopup(false)}
                  className="w-full mt-4 py-4 rounded-2xl font-bold border-2 border-gray-300 text-gray-500 text-xl"
                >
                  취소
                </button>
              </>
            )}

            {/* Step 3a — 전화번호 입력 */}
            {telecomStep === 'phone' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('method')} className="text-gray-400 text-2xl">←</button>
                  <h2 className="text-2xl font-black text-gray-800">전화번호 입력</h2>
                </div>
                <p className="text-lg text-gray-400 mb-3">
                  {selectedProvider?.label} 가입 번호를 입력해 주세요
                </p>
                <div className="rounded-2xl px-4 py-4 text-center bg-gray-100">
                  <p className="text-3xl font-black text-gray-800 tracking-widest">
                    {phoneNumber
                      ? phoneNumber.replace(/(\d{3})(\d{0,4})(\d{0,4})/, (_, a, b, c) => [a, b, c].filter(Boolean).join('-'))
                      : '010-0000-0000'}
                  </p>
                </div>
                <NumPad value={phoneNumber} onChange={setPhoneNumber} maxLength={11} />
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => { setTelecomStep('method'); setPhoneNumber('') }}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-500 text-xl font-bold"
                  >
                    뒤로
                  </button>
                  <button
                    onClick={() => setTelecomStep('confirm')}
                    disabled={phoneNumber.length < 10}
                    className={`flex-1 py-4 rounded-2xl text-xl font-bold transition-colors
                      ${phoneNumber.length >= 10
                        ? 'bg-amber-500 hover:bg-amber-600 text-white'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
                  >
                    인증
                  </button>
                </div>
              </>
            )}

            {/* Step 3b — 쿠폰 스캔 */}
            {telecomStep === 'scan' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('method')} className="text-gray-400 text-2xl">←</button>
                  <h2 className="text-2xl font-black text-gray-800">쿠폰 스캔</h2>
                </div>
                <p className="text-lg text-gray-400 mb-4">
                  쿠폰의 바코드를 카메라에 가져다 대주세요
                </p>
                <div className="rounded-2xl h-44 flex items-center justify-center mb-4 bg-gray-100 border-2 border-dashed border-amber-400">
                  <div className="text-center">
                    <p className="text-5xl mb-2">📷</p>
                    <p className="text-amber-500 font-bold">카메라 준비 중...</p>
                    <p className="text-base text-gray-400 mt-1">바코드를 화면 중앙에 맞춰주세요</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setTelecomStep('method')}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-500 text-xl font-bold"
                  >
                    뒤로
                  </button>
                  <button
                    onClick={() => setTelecomStep('confirm')}
                    className="flex-1 py-4 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white text-xl font-bold"
                  >
                    인식 완료
                  </button>
                </div>
              </>
            )}

            {/* Step 4 — 할인 확인 */}
            {telecomStep === 'confirm' && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">할인 확인</h2>
                <p className="text-lg text-gray-400 mb-5">
                  {selectedProvider?.label} 통신사 할인이 적용됩니다
                </p>
                <div className="rounded-2xl p-5 mb-5 bg-amber-50 border border-amber-200">
                  <div className="flex justify-between items-center mb-2 text-lg">
                    <span className="text-gray-400">원래 금액</span>
                    <span className="line-through text-gray-400">{totalPrice.toLocaleString()}원</span>
                  </div>
                  <div className="flex justify-between items-center mb-2 text-lg">
                    <span className="text-amber-600 font-bold">통신사 할인 (20%)</span>
                    <span className="font-bold text-amber-600">
                      -{Math.floor(totalPrice * 0.2).toLocaleString()}원
                    </span>
                  </div>
                  <div className="border-t pt-3 flex justify-between items-center border-amber-200">
                    <span className="font-black text-xl text-gray-800">최종 결제 금액</span>
                    <span className="font-black text-3xl text-amber-600">
                      {Math.floor(totalPrice * 0.8).toLocaleString()}원
                    </span>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setTelecomStep('method')}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-500 text-xl font-bold"
                  >
                    취소
                  </button>
                  <button
                    onClick={handleTelecomConfirm}
                    className="flex-1 py-4 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white text-xl font-bold"
                  >
                    결제하기
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
