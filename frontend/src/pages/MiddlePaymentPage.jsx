// 중장년 결제 페이지 — 다양한 결제 수단 + 통신사 할인 팝업
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { buildOrderPayload } from '../utils/orderPayload'
import { splitVAT } from '../utils/price'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'

const PAYMENT_METHODS = [
  {
    id: 'card',
    label: '신용 / 체크카드',
    desc: 'IC칩 또는 마그네틱 결제',
    discount: null,
  },
  {
    id: 'apple_pay',
    label: '애플페이',
    desc: 'Face ID / Touch ID로 결제',
    discount: null,
  },
  {
    id: 'naver_pay',
    label: '네이버페이',
    desc: '네이버페이로 간편 결제',
    discount: null,
  },
  {
    id: 'samsung_pay',
    label: '삼성페이',
    desc: '삼성페이로 간편 결제',
    discount: null,
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
  { id: 'kt', label: 'KT', color: '#BC1F2E', icon: '📶' },
  { id: 'lg', label: 'LG U+', color: '#E4006B', icon: '📻' },
]

// 숫자 키패드
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
          className={`h-12 rounded-xl text-xl font-bold transition-all
            ${key === '' ? 'invisible' : 'hover:opacity-80 active:scale-95'}
            ${key === '⌫' ? 'text-red-400' : 'text-gray-700'}`}
          style={{ background: key === '' ? 'transparent' : '#fff3ec', border: '1px solid #fde8d8' }}
        >
          {key}
        </button>
      ))}
    </div>
  )
}

export default function MiddlePaymentPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | processing | done
  const [errorMessage, setErrorMessage] = useState('')

  // 통신사 할인 팝업 상태
  const [showTelecomPopup, setShowTelecomPopup] = useState(false)
  const [telecomStep, setTelecomStep] = useState('provider') // provider | method | phone | scan | confirm
  const [selectedProvider, setSelectedProvider] = useState(null)
  const [telecomMethod, setTelecomMethod] = useState(null) // phone | card | coupon
  const [phoneNumber, setPhoneNumber] = useState('')
  const [telecomDiscount, setTelecomDiscount] = useState(null)

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)
  const vat = splitVAT(totalPrice)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('payment', { total_price: totalPrice, total_count: totalCount })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('payment', Date.now() - enteredAt)
    }
  }, [logger, state.sessionUuid, totalCount, totalPrice])

  const handlePay = useCallback(async (method, discountRate = null) => {
    logger.log('payment', 'payment', {
      actionName: 'payment_method_select',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: { total_price: totalPrice, total_count: totalCount },
    })
    setSelectedMethod(method.id)
    setStatus('processing')
    setErrorMessage('')

    const discount = discountRate || method.discount
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
        discount_rate: discount || 0,
        discount_type: discount ? (method.id === 'telecom' ? `telecom_${selectedProvider?.id || ''}` : method.id) : null,
        order_type: state.orderType,
        used_recommendation: state.cart.some((item) => item.fromRecommendation),
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    const orderStartedAt = performance.now()
    try {
      const discountAmountForPayload = discount ? totalPrice - discountedPrice : 0
      const discountTypeForPayload = discount
        ? (method.id === 'telecom' ? `telecom_${selectedProvider?.id || ''}` : method.id)
        : null
      const res = await api.post('/api/v1/orders', buildOrderPayload(state.sessionUuid, state.cart, {
        orderType: state.orderType,
        discountType: discountTypeForPayload,
        discountAmount: discountAmountForPayload,
      }))
      orderUuid = res.data.order_uuid
      logClientTiming('payment.createOrder', performance.now() - orderStartedAt, { order_uuid: orderUuid })
    } catch (err) {
      logClientTiming('payment.createOrder.error', performance.now() - orderStartedAt, {
        session_uuid: state.sessionUuid,
      })
      console.error('주문 저장 실패:', err)

      setStatus('idle')
      setErrorMessage('주문 생성에 실패했습니다. 잠시 후 다시 시도해주세요.')
      return
    }

    setStatus('done')
    await logger.flush()
    navigate('/middlecomplete', {
      replace: true,
      state: {
        paymentMethod: method.id === 'telecom'
          ? `${selectedProvider?.label} 통신사 할인`
          : method.label,
        totalPrice: discountedPrice,
        totalCount,
        orderUuid,
        discountAmount: discount ? totalPrice - discountedPrice : 0,
        discountLabel: discount && method.id === 'telecom'
          ? `${selectedProvider?.label} 통신사 ${discount * 100}% 할인`
          : null,
      },
    })
  }, [logger, navigate, state, totalCount, totalPrice, selectedProvider])

  // 통신사 할인 팝업 열기
  const handleTelecomClick = () => {
    setTelecomStep('provider')
    setSelectedProvider(null)
    setTelecomMethod(null)
    setPhoneNumber('')
    setTelecomDiscount(null)
    setShowTelecomPopup(true)
  }

  // 통신사 할인 확정 후 결제
  const handleTelecomConfirm = () => {
    setShowTelecomPopup(false)
    const telecomMethod = PAYMENT_METHODS.find((m) => m.id === 'telecom')
    handlePay(telecomMethod, 0.2)
  }

  // 결제 중 오버레이
  if (status === 'processing') {
    const method = PAYMENT_METHODS.find((m) => m.id === selectedMethod)
    const discount = telecomDiscount || method?.discount
    const discountedPrice = discount ? Math.floor(totalPrice * (1 - discount)) : totalPrice

    return (
      <div className="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <div className="w-16 h-16 mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl font-bold text-amber-600">결제</span>
        </div>
        <div className="w-12 h-12 border-4 border-t-transparent rounded-full animate-spin mb-6"
          style={{ borderColor: '#f4a261', borderTopColor: 'transparent' }} />
        <h2 className="text-2xl font-bold mb-2" style={{ color: '#374151' }}>결제 중...</h2>
        <p style={{ color: '#9ca3af' }}>
          {selectedMethod === 'telecom'
            ? `${selectedProvider?.label} 통신사 할인으로 처리하고 있어요`
            : `${method?.label}으로 처리하고 있어요`}
        </p>
        {discount ? (
          <div className="mt-4 text-center">
            <p className="line-through text-sm" style={{ color: '#9ca3af' }}>
              {totalPrice.toLocaleString()}원
            </p>
            <p className="text-xl font-bold" style={{ color: '#f4a261' }}>
              {discountedPrice.toLocaleString()}원
              <span className="text-sm ml-1">({discount * 100}% 할인)</span>
            </p>
          </div>
        ) : (
          <p className="font-bold mt-4 text-xl" style={{ color: '#f4a261' }}>
            {totalPrice.toLocaleString()}원
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#fdf6f0' }}>
      {/* 헤더 */}
      <header className="px-4 py-3 flex items-center sticky top-0 z-10 shadow-sm"
        style={{ background: '#fff8f3' }}>
        <button
          onClick={() => navigate('/middlekiosk')}
          className="p-2 -ml-2 mr-2 font-medium"
          style={{ color: '#6b7280' }}
        >
          ← 뒤로
        </button>
        <h1 className="text-lg font-bold" style={{ color: '#374151' }}>결제</h1>
      </header>

      <div className="flex-1 px-4 py-5 space-y-4 pb-8">

        {DEMO_MODE && (
          <div className="rounded-xl px-4 py-2 text-xs font-bold text-center"
            style={{ background: '#FEF9C3', border: '1px solid #FEF08A', color: '#854D0E' }}>
            🧪 테스트 결제 모드 · 실제 결제는 발생하지 않습니다
          </div>
        )}

        {/* 주문 내역 */}
        <div className="rounded-2xl shadow-sm overflow-hidden" style={{ background: '#fff', border: '1px solid #fde8d8' }}>
          <div className="px-4 py-3 border-b" style={{ background: '#fff8f3', borderColor: '#fde8d8' }}>
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: '#9ca3af' }}>주문 내역</p>
          </div>
          <div className="divide-y" style={{ borderColor: '#fde8d8' }}>
            {state.cart.map((item) => {
              const optionLabel = (item.optionLabels || []).join(' · ')
              return (
                <div key={item.cartItemId} className="px-4 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium" style={{ color: '#374151' }}>
                      {item.displayName}
                      <span className="ml-1 font-bold" style={{ color: '#f4a261' }}>×{item.quantity}</span>
                    </p>
                    {optionLabel && <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>{optionLabel}</p>}
                  </div>
                  <p className="text-sm font-semibold" style={{ color: '#374151' }}>
                    {(item.unitPrice * item.quantity).toLocaleString()}원
                  </p>
                </div>
              )
            })}
          </div>
          <div className="px-4 py-3 space-y-1.5"
            style={{ background: '#fff3ec', borderTop: '1px solid #fde8d8' }}>
            <div className="flex justify-between items-center text-xs" style={{ color: '#9ca3af' }}>
              <span>공급가액</span>
              <span>{vat.net.toLocaleString()}원</span>
            </div>
            <div className="flex justify-between items-center text-xs" style={{ color: '#9ca3af' }}>
              <span>부가세 (10%)</span>
              <span>{vat.tax.toLocaleString()}원</span>
            </div>
            <div className="flex justify-between items-center pt-1.5" style={{ borderTop: '1px solid #fde8d8' }}>
              <span className="font-bold" style={{ color: '#6b7280' }}>총 {totalCount}개</span>
              <span className="text-xl font-black" style={{ color: '#f4a261' }}>{totalPrice.toLocaleString()}원</span>
            </div>
          </div>
        </div>

        {errorMessage && (
          <div className="rounded-2x1 px-4 py-3 font-bold text-sm"
            style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#B91C1C' }}>
            {errorMessage}
          </div>
        )}

        {/* 통신사 할인 안내 */}
        <div className="rounded-2xl px-4 py-3 flex items-center gap-3"
          style={{ background: '#fff3ec', border: '1px solid #fde8d8' }}>
          <span className="text-2xl">🎁</span>
          <p className="text-sm font-medium" style={{ color: '#c2703a' }}>
            통신사 멤버십으로 최대 20% 할인 받으세요!
          </p>
        </div>

        {/* 결제 수단 */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider px-1 mb-3" style={{ color: '#9ca3af' }}>
            결제 수단을 선택해주세요
          </p>
          <div className="space-y-2">
            {PAYMENT_METHODS.map((method) => (
              <button
                key={method.id}
                onClick={() => method.id === 'telecom' ? handleTelecomClick() : handlePay(method)}
                className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl border-2 active:scale-95 transition-all shadow-sm hover:shadow-md"
                style={{ background: '#fff', borderColor: '#e5e7eb', color: '#374151' }}
              >
                <div className="text-left flex-1">
                  <p className="font-bold text-base">{method.label}</p>
                  <p className="text-xs mt-0.5 opacity-80">{method.desc}</p>
                </div>
                {method.discount && (
                  <span className="text-sm font-black px-2 py-1 rounded-full flex-shrink-0"
                    style={{ background: 'rgba(255,255,255,0.3)' }}>
                    -{method.discount * 100}%
                  </span>
                )}
                <span className="text-xl flex-shrink-0 opacity-60">›</span>
              </button>
            ))}
          </div>
        </div>

        <p className="text-center text-xs mt-4" style={{ color: '#9ca3af' }}>
          결제 수단을 탭하면 바로 결제가 시작됩니다
        </p>
      </div>

      {/* 통신사 할인 팝업 */}
      {showTelecomPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowTelecomPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-6"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Step 1 — 통신사 선택 */}
            {telecomStep === 'provider' && (
              <>
                <h2 className="text-xl font-black mb-1" style={{ color: '#374151' }}>통신사 선택</h2>
                <p className="text-sm mb-5" style={{ color: '#9ca3af' }}>이용 중인 통신사를 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  {TELECOM_PROVIDERS.map((provider) => (
                    <button
                      key={provider.id}
                      onClick={() => { setSelectedProvider(provider); setTelecomStep('method') }}
                      className="w-full py-4 rounded-2xl font-bold text-white text-lg flex items-center gap-3 px-5 active:scale-95 transition-all"
                      style={{ background: provider.color }}
                    >
                      <span className="text-2xl">{provider.icon}</span>
                      <span>{provider.label}</span>
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowTelecomPopup(false)}
                  className="w-full mt-4 py-3 rounded-2xl font-bold border-2"
                  style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
                >
                  취소
                </button>
              </>
            )}

            {/* Step 2 — 인증 방법 선택 */}
            {telecomStep === 'method' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('provider')} style={{ color: '#9ca3af' }}>←</button>
                  <h2 className="text-xl font-black" style={{ color: '#374151' }}>
                    {selectedProvider?.label} 할인 인증
                  </h2>
                </div>
                <p className="text-sm mb-5" style={{ color: '#9ca3af' }}>인증 방법을 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => setTelecomStep('phone')}
                    className="w-full py-4 rounded-2xl border-2 font-bold flex items-center gap-4 px-5 active:scale-95 transition-all hover:opacity-80"
                    style={{ borderColor: '#fde8d8', background: '#fff', color: '#374151' }}
                  >
                    <span className="text-3xl">📱</span>
                    <div className="text-left">
                      <p className="font-bold">전화번호 입력</p>
                      <p className="text-xs font-normal" style={{ color: '#9ca3af' }}>등록된 번호로 인증</p>
                    </div>
                  </button>
                  <button
                    onClick={() => setTelecomStep('scan')}
                    className="w-full py-4 rounded-2xl border-2 font-bold flex items-center gap-4 px-5 active:scale-95 transition-all hover:opacity-80"
                    style={{ borderColor: '#fde8d8', background: '#fff', color: '#374151' }}
                  >
                    <span className="text-3xl">🎫</span>
                    <div className="text-left">
                      <p className="font-bold">쿠폰 스캔</p>
                      <p className="text-xs font-normal" style={{ color: '#9ca3af' }}>할인 쿠폰을 카메라에</p>
                    </div>
                  </button>
                </div>
                <button
                  onClick={() => setShowTelecomPopup(false)}
                  className="w-full mt-4 py-3 rounded-2xl font-bold border-2"
                  style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
                >
                  취소
                </button>
              </>
            )}

            {/* Step 3a — 전화번호 입력 */}
            {telecomStep === 'phone' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('method')} style={{ color: '#9ca3af' }}>←</button>
                  <h2 className="text-xl font-black" style={{ color: '#374151' }}>전화번호 입력</h2>
                </div>
                <p className="text-sm mb-3" style={{ color: '#9ca3af' }}>
                  {selectedProvider?.label} 가입 전화번호를 입력해 주세요
                </p>
                <div className="rounded-2xl px-4 py-3 text-center" style={{ background: '#fff3ec' }}>
                  <p className="text-2xl font-black tracking-widest" style={{ color: '#374151' }}>
                    {phoneNumber
                      ? phoneNumber.replace(/(\d{3})(\d{0,4})(\d{0,4})/, (_, a, b, c) => [a, b, c].filter(Boolean).join('-'))
                      : '010-0000-0000'}
                  </p>
                </div>
                <NumPad value={phoneNumber} onChange={setPhoneNumber} maxLength={11} />
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => { setTelecomStep('method'); setPhoneNumber('') }}
                    className="flex-1 py-3 rounded-2xl border-2 font-bold"
                    style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
                  >
                    뒤로
                  </button>
                  <button
                    onClick={() => setTelecomStep('confirm')}
                    disabled={phoneNumber.length < 10}
                    className="flex-1 py-3 rounded-2xl font-bold text-white transition-colors"
                    style={{
                      background: phoneNumber.length >= 10 ? '#f4a261' : '#e5e7eb',
                      color: phoneNumber.length >= 10 ? '#fff' : '#9ca3af',
                    }}
                  >
                    인증
                  </button>
                </div>
              </>
            )}

            {/* Step 3b — 바코드 스캔 */}
            {telecomStep === 'scan' && (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <button onClick={() => setTelecomStep('method')} style={{ color: '#9ca3af' }}>←</button>
                  <h2 className="text-xl font-black" style={{ color: '#374151' }}>바코드 스캔</h2>
                </div>
                <p className="text-sm mb-4" style={{ color: '#9ca3af' }}>
                  카드나 쿠폰의 바코드를 카메라에 가져다 대주세요
                </p>
                <div className="rounded-2xl h-44 flex items-center justify-center mb-4"
                  style={{ background: '#fff3ec', border: '2px dashed #f4a261' }}>
                  <div className="text-center">
                    <p className="text-5xl mb-2">📷</p>
                    <p className="text-sm" style={{ color: '#f4a261' }}>카메라 준비 중...</p>
                    <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>바코드를 화면 중앙에 맞춰주세요</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setTelecomStep('method')}
                    className="flex-1 py-3 rounded-2xl border-2 font-bold"
                    style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
                  >
                    뒤로
                  </button>
                  <button
                    onClick={() => setTelecomStep('confirm')}
                    className="flex-1 py-3 rounded-2xl font-bold text-white"
                    style={{ background: '#f4a261' }}
                  >
                    인식 완료
                  </button>
                </div>
              </>
            )}

            {/* Step 4 — 할인 확인 */}
            {telecomStep === 'confirm' && (
              <>
                <h2 className="text-xl font-black mb-1" style={{ color: '#374151' }}>할인 확인</h2>
                <p className="text-sm mb-5" style={{ color: '#9ca3af' }}>
                  {selectedProvider?.label} 멤버십 할인이 적용됩니다
                </p>

                <div className="rounded-2xl p-5 mb-5" style={{ background: '#fff3ec', border: '1px solid #fde8d8' }}>
                  <div className="flex justify-between items-center mb-2">
                    <span style={{ color: '#9ca3af' }}>원래 금액</span>
                    <span className="line-through" style={{ color: '#9ca3af' }}>{totalPrice.toLocaleString()}원</span>
                  </div>
                  <div className="flex justify-between items-center mb-2">
                    <span style={{ color: '#f4a261' }}>통신사 할인 (20%)</span>
                    <span className="font-bold" style={{ color: '#f4a261' }}>
                      -{Math.floor(totalPrice * 0.2).toLocaleString()}원
                    </span>
                  </div>
                  <div className="border-t pt-2 flex justify-between items-center" style={{ borderColor: '#fde8d8' }}>
                    <span className="font-black text-lg" style={{ color: '#374151' }}>최종 결제 금액</span>
                    <span className="font-black text-2xl" style={{ color: '#f4a261' }}>
                      {Math.floor(totalPrice * 0.8).toLocaleString()}원
                    </span>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setTelecomStep('method')}
                    className="flex-1 py-3 rounded-2xl border-2 font-bold"
                    style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
                  >
                    취소
                  </button>
                  <button
                    onClick={handleTelecomConfirm}
                    className="flex-1 py-3 rounded-2xl font-bold text-white"
                    style={{ background: '#f4a261' }}
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
