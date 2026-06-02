// 중장년 결제 페이지 — 결제 수단 선택 + 할인 선택 팝업
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
  },
  {
    id: 'apple_pay',
    label: '애플페이',
    desc: 'Face ID / Touch ID로 결제',
  },
  {
    id: 'naver_pay',
    label: '네이버페이',
    desc: '네이버페이로 간편 결제',
  },
  {
    id: 'samsung_pay',
    label: '삼성페이',
    desc: '삼성페이로 간편 결제',
  },
  {
    id: 'discount',
    label: '할인 선택',
    desc: '임직원·SKT·LG·기프티콘 할인',
  },
]

const DISCOUNT_OPTIONS = [
  {
    id: 'employee',
    label: '임직원 할인',
    emoji: '👔',
    desc: '임직원 사원증 바코드 인식',
    color: 'bg-blue-50 border-blue-200 hover:border-blue-400',
    discountRate: 0.2,
  },
  {
    id: 'skt',
    label: 'SKT 멤버십',
    emoji: '📶',
    desc: 'T멤버십 바코드 인식',
    color: 'bg-red-50 border-red-200 hover:border-red-400',
    discountRate: 0.2,
  },
  {
    id: 'lg',
    label: 'LG 멤버십',
    emoji: '📡',
    desc: 'LG U+ 멤버십 바코드 인식',
    color: 'bg-pink-50 border-pink-200 hover:border-pink-400',
    discountRate: 0.2,
  },
  {
    id: 'gifticon',
    label: '기프티콘',
    emoji: '🎟️',
    desc: '기프티콘 바코드 인식',
    color: 'bg-amber-50 border-amber-200 hover:border-amber-400',
    discountRate: 0,
  },
]

export default function MiddlePaymentPage() {
  const navigate = useNavigate()
  const { state } = useSession()
  const logger = useLogger(state.sessionUuid)

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | processing | done
  const [errorMessage, setErrorMessage] = useState('')

  // 할인 팝업 상태
  const [showDiscountPopup, setShowDiscountPopup] = useState(false)
  // 선택된 할인 옵션 (스캔 오버레이 및 결제에 사용)
  const [scanningDiscount, setScanningDiscount] = useState(null)
  const [selectedDiscount, setSelectedDiscount] = useState(null)

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

  const handlePay = useCallback(async (method, discountOption = null) => {
    const discount = discountOption?.discountRate ?? null
    const discountedPrice = discount ? Math.floor(totalPrice * (1 - discount)) : totalPrice

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
        total_price: discountedPrice,
        original_price: totalPrice,
        discount_amount: discount ? totalPrice - discountedPrice : 0,
        total_count: totalCount,
        discount_rate: discount || 0,
        discount_type: discountOption ? discountOption.id : null,
        order_type: state.orderType,
        used_recommendation: state.cart.some((item) => item.fromRecommendation),
      },
    })

    setSelectedMethod(method.id)
    setStatus('processing')
    setErrorMessage('')

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    const orderStartedAt = performance.now()
    try {
      const discountAmount = discount ? totalPrice - discountedPrice : 0
      const res = await api.post('/api/v1/orders', buildOrderPayload(state.sessionUuid, state.cart, {
        orderType: state.orderType,
        discountType: discountOption ? discountOption.id : null,
        discountAmount,
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
        paymentMethod: discountOption
          ? `${discountOption.label} 할인`
          : method.label,
        totalPrice: discountedPrice,
        totalCount,
        orderUuid,
        discountAmount: discount ? totalPrice - discountedPrice : 0,
        discountLabel: discountOption && discount
          ? `${discountOption.label} (${Math.round(discount * 100)}% 할인)`
          : null,
      },
    })
  }, [logger, navigate, state, totalCount, totalPrice])

  // 할인 옵션 선택 → 스캔 오버레이 → 결제 페이지로 복귀 (할인 적용 상태)
  const handleDiscountSelect = (option) => {
    logger.log('click', 'payment', {
      actionName: 'discount_select',
      targetType: 'button',
      targetLabel: option.id,
      payload: { discount_rate: option.discountRate, total_price: totalPrice },
    })
    setShowDiscountPopup(false)
    setScanningDiscount(option)
    setTimeout(() => {
      setScanningDiscount(null)
      setSelectedDiscount(option)
    }, 2000)
  }

  // 바코드 인식 중 오버레이
  if (scanningDiscount) {
    return (
      <div className="fixed inset-0 bg-gray-900/95 flex flex-col items-center justify-center z-50">
        <div className="text-7xl mb-6 animate-pulse">{scanningDiscount.emoji}</div>
        <div className="relative w-48 h-1.5 bg-gray-700 rounded-full mb-8 overflow-hidden">
          <div className="absolute inset-y-0 left-0 w-1/2 bg-amber-400 rounded-full animate-[scan_1s_ease-in-out_infinite]" />
        </div>
        <h2 className="text-2xl font-black text-white mb-2">바코드 인식 중</h2>
        <p className="text-gray-400 text-sm">{scanningDiscount.label} 바코드를 인식하고 있어요</p>
        <style>{`
          @keyframes scan {
            0%   { left: 0%;  width: 40%; }
            50%  { left: 60%; width: 40%; }
            100% { left: 0%;  width: 40%; }
          }
        `}</style>
      </div>
    )
  }

  // 결제 중 오버레이
  if (status === 'processing') {
    const method = PAYMENT_METHODS.find((m) => m.id === selectedMethod)
    const discount = selectedDiscount?.discountRate ?? null
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
          {selectedMethod === 'discount'
            ? `${selectedDiscount?.label} 할인으로 처리하고 있어요`
            : `${method?.label}으로 처리하고 있어요`}
        </p>
        {discount ? (
          <div className="mt-4 text-center">
            <p className="line-through text-sm" style={{ color: '#9ca3af' }}>
              {totalPrice.toLocaleString()}원
            </p>
            <p className="text-xl font-bold" style={{ color: '#f4a261' }}>
              {discountedPrice.toLocaleString()}원
              <span className="text-sm ml-1">({Math.round(discount * 100)}% 할인)</span>
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
            {selectedDiscount?.discountRate > 0 ? (
              <>
                <div className="flex justify-between items-center text-xs" style={{ color: '#9ca3af' }}>
                  <span>원래 금액</span>
                  <span className="line-through">{totalPrice.toLocaleString()}원</span>
                </div>
                <div className="flex justify-between items-center text-xs font-bold" style={{ color: '#16a34a' }}>
                  <span>{selectedDiscount.label} ({Math.round(selectedDiscount.discountRate * 100)}% 할인)</span>
                  <span>-{Math.floor(totalPrice * selectedDiscount.discountRate).toLocaleString()}원</span>
                </div>
                <div className="flex justify-between items-center pt-1.5" style={{ borderTop: '1px solid #fde8d8' }}>
                  <span className="font-bold" style={{ color: '#6b7280' }}>총 {totalCount}개</span>
                  <span className="text-xl font-black" style={{ color: '#f4a261' }}>
                    {Math.floor(totalPrice * (1 - selectedDiscount.discountRate)).toLocaleString()}원
                  </span>
                </div>
              </>
            ) : (
              <>
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
              </>
            )}
          </div>
        </div>

        {errorMessage && (
          <div className="rounded-2xl px-4 py-3 font-bold text-sm"
            style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#B91C1C' }}>
            {errorMessage}
          </div>
        )}

        {/* 할인 적용 배너 */}
        {selectedDiscount && (
          <div className="rounded-2xl px-4 py-3 flex items-center justify-between"
            style={{ background: '#f0fdf4', border: '1px solid #86efac' }}>
            <div className="flex items-center gap-2">
              <span className="text-xl">{selectedDiscount.emoji}</span>
              <div>
                <p className="text-sm font-bold" style={{ color: '#15803d' }}>
                  {selectedDiscount.label} 적용됨
                </p>
                {selectedDiscount.discountRate > 0 && (
                  <p className="text-xs" style={{ color: '#16a34a' }}>
                    {Math.round(selectedDiscount.discountRate * 100)}% 할인 →&nbsp;
                    <span className="font-bold">
                      {Math.floor(totalPrice * (1 - selectedDiscount.discountRate)).toLocaleString()}원
                    </span>
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => {
                logger.log('click', 'payment', { actionName: 'discount_remove', targetType: 'button', targetLabel: selectedDiscount?.id })
                setSelectedDiscount(null)
              }}
              className="text-xs font-bold px-2 py-1 rounded-lg"
              style={{ color: '#6b7280', background: '#f3f4f6' }}
            >
              취소
            </button>
          </div>
        )}

        {/* 할인 선택 */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider px-1 mb-3" style={{ color: '#9ca3af' }}>
            할인 수단
          </p>
          <button
            onClick={() => {
              logger.log('click', 'payment', { actionName: 'discount_popup_open', targetType: 'button', targetLabel: 'discount' })
              setShowDiscountPopup(true)
            }}
            className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl border-2 active:scale-95 transition-all shadow-sm hover:shadow-md"
            style={{ background: '#fffbeb', borderColor: '#fcd34d', color: '#374151' }}
          >
            <span className="text-2xl">🎟️</span>
            <div className="text-left flex-1">
              <p className="font-bold text-base" style={{ color: '#92400e' }}>할인 선택</p>
              <p className="text-xs mt-0.5" style={{ color: '#b45309' }}>임직원·SKT·LG·기프티콘 할인</p>
            </div>
            <span className="text-xl flex-shrink-0 opacity-60">›</span>
          </button>
        </div>

        {/* 구분선 */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px" style={{ background: '#fde8d8' }} />
          <p className="text-xs font-bold" style={{ color: '#d1a07a' }}>결제 수단</p>
          <div className="flex-1 h-px" style={{ background: '#fde8d8' }} />
        </div>

        {/* 결제 수단 */}
        <div className="space-y-2">
          {PAYMENT_METHODS.filter((m) => m.id !== 'discount').map((method) => (
            <button
              key={method.id}
              onClick={() => handlePay(method, selectedDiscount)}
              className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl border-2 active:scale-95 transition-all shadow-sm hover:shadow-md"
              style={{ background: '#fff', borderColor: '#e5e7eb', color: '#374151' }}
            >
              <div className="text-left flex-1">
                <p className="font-bold text-base">{method.label}</p>
                <p className="text-xs mt-0.5 opacity-80">{method.desc}</p>
              </div>
              <span className="text-xl flex-shrink-0 opacity-60">›</span>
            </button>
          ))}
        </div>

        <p className="text-center text-xs mt-4" style={{ color: '#9ca3af' }}>
          결제 수단을 탭하면 바로 결제가 시작됩니다
        </p>
      </div>

      {/* 할인 선택 팝업 */}
      {showDiscountPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-end justify-center"
          onClick={() => setShowDiscountPopup(false)}
        >
          <div
            className="w-full max-w-lg rounded-t-3xl p-6 pb-8"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-black" style={{ color: '#374151' }}>할인 선택</h2>
                <p className="text-sm mt-0.5" style={{ color: '#9ca3af' }}>적용할 할인 수단을 선택해 주세요</p>
              </div>
              <button
                onClick={() => setShowDiscountPopup(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:bg-gray-100"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              {DISCOUNT_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  onClick={() => handleDiscountSelect(option)}
                  className={`relative flex flex-col items-center justify-center min-h-[120px] py-5 px-3 rounded-2xl border-2 active:scale-95 transition-all bg-white ${option.color}`}
                >
                  {option.discountRate > 0 && (
                    <span className="absolute top-2 right-2 bg-green-500 text-white text-[10px] font-black px-2 py-0.5 rounded-full">
                      {Math.round(option.discountRate * 100)}% 할인
                    </span>
                  )}
                  <span className="text-3xl mb-2">{option.emoji}</span>
                  <span className="font-bold text-sm text-gray-800">{option.label}</span>
                  <span className="text-xs text-gray-400 mt-1 text-center leading-relaxed">{option.desc}</span>
                </button>
              ))}
            </div>

            <button
              onClick={() => {
                logger.log('click', 'payment', { actionName: 'discount_popup_cancel', targetType: 'button', targetLabel: 'cancel' })
                setShowDiscountPopup(false)
              }}
              className="w-full py-3 rounded-2xl font-bold border-2"
              style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
            >
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
