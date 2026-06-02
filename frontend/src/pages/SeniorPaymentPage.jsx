// 결제 페이지 — 결제 수단 선택 → 결제 중 → 완료 처리
import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { useTTS } from '../hooks/useTTS'
import { buildOrderPayload } from '../utils/orderPayload'
import { splitVAT } from '../utils/price'
import PaymentMethodGrid from '../components/PaymentMethodGrid'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== 'false'
const TOTAL_STAMPS = 10

function getSimulatedStamps() {
  return parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
}

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

export default function SeniorPaymentPage() {
  const navigate = useNavigate()
  const { state } = useSession()
  const logger = useLogger(state.sessionUuid)
  const tts = useTTS({ rate: 0.65 })
  const ttsCalledRef = useRef(false)

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | selecting | processing | done
  const [errorMessage, setErrorMessage] = useState('')

  // 할인 팝업 상태
  const [showDiscountPopup, setShowDiscountPopup] = useState(false)
  const [scanningDiscount, setScanningDiscount] = useState(null)
  const [selectedDiscount, setSelectedDiscount] = useState(null)
  const [stampDone, setStampDone] = useState(sessionStorage.getItem('stamp_before_payment_done') === '1')
  const [stampSkipped, setStampSkipped] = useState(sessionStorage.getItem('stamp_before_payment_skipped') === '1')
  const [showStampPopup, setShowStampPopup] = useState(false)
  const [phoneNumber, setPhoneNumber] = useState('')

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)
  const prevStamps = getSimulatedStamps()
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + 1)
  const vat = splitVAT(totalPrice)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('payment', { total_price: totalPrice, total_count: totalCount })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('payment', Date.now() - enteredAt)
      tts.cancel()
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
        discount_type: discountOption ? discountOption.id : null,
        order_type: state.orderType,
        used_recommendation: state.cart.some((item) => item.fromRecommendation),
      },
    })

    setSelectedMethod(method.id)
    setStatus('processing')
    setErrorMessage('')

    await tts.speak(`${discountOption ? discountOption.label + ' 할인으로' : method.label + '로'} 결제를 시작합니다.`)
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
    tts.cancel()
    await logger.flush()
    navigate('/seniorcomplete', {
      replace: true,
      state: {
        paymentMethod: discountOption ? `${discountOption.label} 할인` : method.label,
        totalPrice: discountedPrice,
        totalCount,
        orderUuid,
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
      tts.speak(`${option.label}이 적용되었습니다. 결제 수단을 선택해 주세요.`)
    }, 2000)
  }

  const handleProceedToPayment = () => {
    if (!stampDone && !stampSkipped) {
      setShowStampPopup(true)
      return
    }
    setStatus('selecting')
  }

  const handleStampConfirm = () => {
    if (phoneNumber.length < 10) return
    sessionStorage.setItem('stamp_count', String(newStamps >= TOTAL_STAMPS ? 0 : newStamps))
    sessionStorage.setItem('stamp_before_payment_done', '1')
    sessionStorage.removeItem('stamp_before_payment_skipped')
    logger.log('click', 'payment', {
      actionName: 'stamp_register',
      targetType: 'button',
      targetLabel: 'stamp_register_before_payment',
      payload: { stamp_count: newStamps },
    })
    setStampDone(true)
    setStampSkipped(false)
    setShowStampPopup(false)
    setPhoneNumber('')
    tts.speak('스탬프 적립이 완료되었습니다. 결제를 진행해 주세요.')
  }

  const handleStampSkip = () => {
    sessionStorage.setItem('stamp_before_payment_skipped', '1')
    sessionStorage.removeItem('stamp_before_payment_done')
    logger.log('click', 'payment', {
      actionName: 'stamp_skip',
      targetType: 'button',
      targetLabel: 'stamp_skip_before_payment',
    })
    setStampSkipped(true)
    setShowStampPopup(false)
    setPhoneNumber('')
    setStatus('selecting')
  }

  // 바코드 인식 중 오버레이
  if (scanningDiscount) {
    return (
      <div className="fixed inset-0 bg-gray-900/95 flex flex-col items-center justify-center z-50">
        <div className="text-8xl mb-6 animate-pulse">{scanningDiscount.emoji}</div>
        <div className="relative w-56 h-2 bg-gray-700 rounded-full mb-10 overflow-hidden">
          <div className="absolute inset-y-0 left-0 w-1/2 bg-amber-400 rounded-full animate-[scan_1s_ease-in-out_infinite]" />
        </div>
        <h2 className="text-3xl font-black text-white mb-3">바코드 인식 중</h2>
        <p className="text-gray-400 text-xl">{scanningDiscount.label} 바코드를 인식하고 있어요</p>
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
        <div className="w-12 h-12 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">결제 중...</h2>
        <p className="text-gray-400 text-lg">
          {selectedMethod === 'discount'
            ? `${selectedDiscount?.label} 할인으로 처리하고 있어요`
            : `${method?.label}으로 처리하고 있어요`}
        </p>
        {discount ? (
          <div className="mt-4 text-center">
            <p className="line-through text-lg text-gray-400">{totalPrice.toLocaleString()}원</p>
            <p className="text-amber-600 font-bold text-2xl">
              {discountedPrice.toLocaleString()}원
              <span className="text-base ml-1">({Math.round(discount * 100)}% 할인)</span>
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

          <div className={`rounded-2xl border-2 px-5 py-5 shadow-sm
            ${stampDone
              ? 'bg-green-50 border-green-300'
              : stampSkipped
                ? 'bg-gray-50 border-gray-200'
                : 'bg-blue-50 border-blue-300'}`}
          >
            <div className="flex items-center gap-4">
              <span className="text-4xl">{stampDone ? '✅' : '⭐'}</span>
              <div className="flex-1">
                <p className={`text-2xl font-black ${stampDone ? 'text-green-700' : 'text-blue-800'}`}>
                  {stampDone ? '스탬프 적립 완료' : stampSkipped ? '스탬프 적립 건너뜀' : '결제 전 스탬프 적립'}
                </p>
                <p className="text-base text-gray-500 mt-1">
                  {stampDone
                    ? `${newStamps}/${TOTAL_STAMPS}개가 모였습니다.`
                    : '전화번호로 적립하고 결제를 진행할 수 있어요.'}
                </p>
              </div>
              {!stampDone && (
                <button
                  onClick={() => setShowStampPopup(true)}
                  className="px-5 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xl font-black"
                >
                  적립하기
                </button>
              )}
            </div>
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
                      {optionLabel && <p className="text-lg text-gray-400 mt-1">{optionLabel}</p>}
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
                <span>공급가액</span><span>{vat.net.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center text-lg text-gray-500">
                <span>부가세 (10%)</span><span>{vat.tax.toLocaleString()}원</span>
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
            onClick={handleProceedToPayment}
            className="flex-1 py-6 rounded-2xl bg-green-600 hover:bg-green-700 text-white text-2xl font-black transition-colors shadow-lg shadow-green-200"
          >
            {stampDone || stampSkipped ? '결제하기' : '스탬프 확인 후 결제'}
          </button>
        </div>
        {showStampPopup && (
          <div
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
            onClick={() => setShowStampPopup(false)}
          >
            <div
              className="bg-white rounded-3xl w-full max-w-sm p-6"
              onClick={(event) => event.stopPropagation()}
            >
              <h2 className="text-2xl font-black text-gray-800 mb-1">스탬프 적립</h2>
              <p className="text-base text-gray-400 mb-4">전화번호를 입력하면 결제 전에 스탬프가 적립됩니다.</p>

              <input
                value={phoneNumber}
                onChange={(event) => setPhoneNumber(event.target.value.replace(/\D/g, '').slice(0, 11))}
                inputMode="numeric"
                placeholder="010-0000-0000"
                className="w-full rounded-2xl bg-gray-100 px-4 py-4 text-center text-3xl font-black text-gray-800 tracking-wider outline-none focus:ring-4 focus:ring-blue-200"
              />
              <p className="text-center text-gray-400 text-sm mt-2">
                현재 {prevStamps}/{TOTAL_STAMPS}개 · 적립 후 {newStamps}/{TOTAL_STAMPS}개
              </p>

              <div className="grid grid-cols-2 gap-3 mt-5">
                <button
                  onClick={handleStampSkip}
                  className="py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                >
                  건너뛰기
                </button>
                <button
                  onClick={handleStampConfirm}
                  disabled={phoneNumber.length < 10}
                  className={`py-4 rounded-2xl text-xl font-bold transition-colors
                    ${phoneNumber.length >= 10
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
                >
                  적립
                </button>
              </div>
            </div>
          </div>
        )}
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
          {selectedDiscount?.discountRate > 0 ? (
            <>
              <div className="flex justify-between items-center text-lg text-gray-400">
                <span>원래 금액</span>
                <span className="line-through">{totalPrice.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center text-lg text-green-600 font-bold">
                <span>{selectedDiscount.label} ({Math.round(selectedDiscount.discountRate * 100)}% 할인)</span>
                <span>-{Math.floor(totalPrice * selectedDiscount.discountRate).toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center pt-2 border-t border-gray-100">
                <span className="text-2xl font-bold text-gray-700">최종 금액</span>
                <span className="text-3xl font-black text-amber-600">
                  {Math.floor(totalPrice * (1 - selectedDiscount.discountRate)).toLocaleString()}원
                </span>
              </div>
            </>
          ) : (
            <>
              <div className="flex justify-between items-center text-lg text-gray-500">
                <span>공급가액</span><span>{vat.net.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center text-lg text-gray-500">
                <span>부가세 (10%)</span><span>{vat.tax.toLocaleString()}원</span>
              </div>
              <div className="flex justify-between items-center pt-2 border-t border-gray-100">
                <span className="text-2xl font-bold text-gray-700">총 금액</span>
                <span className="text-3xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
              </div>
            </>
          )}
        </div>

        {errorMessage && (
          <div className="bg-red-50 border-2 border-red-200 rounded-2xl px-5 py-4 text-red-700 text-xl font-bold">
            {errorMessage}
          </div>
        )}

        {/* 할인 적용 배너 */}
        {selectedDiscount && (
          <div className="rounded-2xl px-5 py-4 flex items-center justify-between bg-green-50 border-2 border-green-300">
            <div className="flex items-center gap-3">
              <span className="text-4xl">{selectedDiscount.emoji}</span>
              <div>
                <p className="text-xl font-bold text-green-700">
                  {selectedDiscount.label} 적용됨
                </p>
                {selectedDiscount.discountRate > 0 && (
                  <p className="text-lg text-green-600">
                    {Math.round(selectedDiscount.discountRate * 100)}% 할인 →&nbsp;
                    <span className="font-black text-amber-600">
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
              className="text-base font-bold px-3 py-2 rounded-xl text-gray-500 bg-gray-100"
            >
              취소
            </button>
          </div>
        )}

        {/* 할인 선택 */}
        <div>
          <p className="text-sm font-bold uppercase tracking-wider px-1 mb-3 text-gray-400">할인 수단</p>
          <button
            onClick={() => {
              logger.log('click', 'payment', { actionName: 'discount_popup_open', targetType: 'button', targetLabel: 'discount' })
              setShowDiscountPopup(true)
            }}
            className="w-full flex items-center gap-5 px-6 py-6 rounded-2xl border-2 active:scale-95 transition-all shadow-sm hover:shadow-md bg-amber-50 border-amber-300"
          >
            <span className="text-4xl">🎟️</span>
            <div className="text-left flex-1">
              <p className="font-bold text-2xl text-amber-800">할인 선택</p>
              <p className="text-lg mt-1 text-amber-600">임직원·SKT·LG·기프티콘 할인</p>
            </div>
            <span className="text-3xl flex-shrink-0 text-amber-300">›</span>
          </button>
        </div>

        {/* 구분선 */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-amber-200" />
          <p className="text-sm font-bold text-amber-400">결제 수단</p>
          <div className="flex-1 h-px bg-amber-200" />
        </div>

        {/* 결제 수단 */}
        <PaymentMethodGrid
          methods={PAYMENT_METHODS.filter((m) => m.id !== 'discount')}
          onSelect={(method) => handlePay(method, selectedDiscount)}
          variant="senior"
        />
      </div>

      {/* 할인 선택 팝업 */}
      {showDiscountPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-end justify-center"
          onClick={() => setShowDiscountPopup(false)}
        >
          <div
            className="w-full max-w-lg rounded-t-3xl p-6 pb-8 bg-white"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-2xl font-black text-gray-800">할인 선택</h2>
                <p className="text-lg text-gray-400 mt-1">적용할 할인 수단을 선택해 주세요</p>
              </div>
              <button
                onClick={() => setShowDiscountPopup(false)}
                className="w-10 h-10 rounded-full flex items-center justify-center text-gray-400 hover:bg-gray-100 text-xl"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-5">
              {DISCOUNT_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  onClick={() => handleDiscountSelect(option)}
                  className={`relative flex flex-col items-center justify-center min-h-[140px] py-6 px-3 rounded-2xl border-2 active:scale-95 transition-all bg-white ${option.color}`}
                >
                  {option.discountRate > 0 && (
                    <span className="absolute top-2 right-2 bg-green-500 text-white text-xs font-black px-2 py-0.5 rounded-full">
                      {Math.round(option.discountRate * 100)}% 할인
                    </span>
                  )}
                  <span className="text-4xl mb-3">{option.emoji}</span>
                  <span className="font-bold text-base text-gray-800">{option.label}</span>
                  <span className="text-sm text-gray-400 mt-1 text-center leading-relaxed">{option.desc}</span>
                </button>
              ))}
            </div>

            <button
              onClick={() => {
                logger.log('click', 'payment', { actionName: 'discount_popup_cancel', targetType: 'button', targetLabel: 'cancel' })
                setShowDiscountPopup(false)
              }}
              className="w-full py-4 rounded-2xl font-bold border-2 border-gray-300 text-gray-500 text-xl"
            >
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
