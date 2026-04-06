// 결제 페이지 — 결제 수단 선택 → 결제 중 → 완료 처리
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

const PAYMENT_METHODS = [
  {
    id: 'apple_pay',
    label: 'Apple Pay',
    icon: '🍎',
    bg: 'bg-black',
    text: 'text-white',
    border: 'border-black',
    desc: 'Face ID / Touch ID로 결제',
  },
  {
    id: 'samsung_pay',
    label: 'Samsung Pay',
    icon: '📱',
    bg: 'bg-blue-600',
    text: 'text-white',
    border: 'border-blue-600',
    desc: '삼성 Pay로 간편 결제',
  },
  {
    id: 'membership',
    label: '멤버십 카드',
    icon: '⭐',
    bg: 'bg-purple-600',
    text: 'text-white',
    border: 'border-purple-600',
    desc: '스탬프 2배 적립',
  },
  {
    id: 'card',
    label: '신용 / 체크카드',
    icon: '💳',
    bg: 'bg-white',
    text: 'text-gray-800',
    border: 'border-gray-300',
    desc: 'IC칩 또는 마그네틱 결제',
  },
]

export default function PaymentPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()

  const [selectedMethod, setSelectedMethod] = useState(null)
  const [status, setStatus] = useState('idle') // idle | processing | done

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  // 결제 수단 선택 → 2초 처리 → 주문 API → 완료 페이지
  const handlePay = useCallback(async (method) => {
    setSelectedMethod(method.id)
    setStatus('processing')

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    try {
      // 주문 생성 (백엔드: 가격 재검증 + 옵션 스냅샷 저장)
      const res = await api.post('/api/v1/orders', {
        session_uuid: state.sessionUuid,
        items: state.cart.map((item) => ({
          menu_name: item.menuName,
          quantity: item.quantity,
          unit_price: item.unitPrice,
          from_recommendation: false,
          selected_options: item.selectedOptions || [],
        })),
        used_recommendation: false,
      })
      orderUuid = res.data.order_uuid
    } catch (err) {
      console.error('주문 저장 실패:', err)
      // 데모용: 실패해도 완료 화면으로 진행
    }

    setStatus('done')
    navigate('/complete', {
      replace: true,
      state: {
        paymentMethod: method.label,
        totalPrice,
        totalCount,
        isMembership: method.id === 'membership',
        orderUuid,
      },
    })
  }, [state, navigate, totalPrice, totalCount])

  // 결제 중 오버레이
  if (status === 'processing') {
    const method = PAYMENT_METHODS.find((m) => m.id === selectedMethod)
    return (
      <div className="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <div className="text-6xl mb-6 animate-bounce">{method?.icon}</div>
        <div className="w-12 h-12 border-4 border-amber-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-2xl font-bold text-gray-800 mb-2">결제 중...</h2>
        <p className="text-gray-400">{method?.label}으로 처리하고 있어요</p>
        <p className="text-amber-600 font-bold mt-4 text-xl">{totalPrice.toLocaleString()}원</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 헤더 */}
      <header className="bg-white shadow-sm px-4 py-3 flex items-center sticky top-0 z-10">
        <button
          onClick={() => navigate('/kiosk')}
          className="text-gray-500 hover:text-gray-700 p-2 -ml-2 mr-2"
        >
          ← 뒤로
        </button>
        <h1 className="text-lg font-bold text-gray-800">결제</h1>
      </header>

      <div className="flex-1 px-4 py-6 space-y-4 pb-8">
        {/* 주문 요약 */}
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
          <div className="px-4 py-3 bg-amber-50 flex justify-between items-center border-t border-amber-100">
            <span className="font-bold text-gray-700">총 {totalCount}개</span>
            <span className="text-xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
          </div>
        </div>

        {/* 결제 수단 선택 */}
        <div>
          <p className="text-xs font-bold text-gray-400 uppercase tracking-wider px-1 mb-3">
            결제 수단을 선택해주세요
          </p>
          <div className="space-y-2">
            {PAYMENT_METHODS.map((method) => (
              <button
                key={method.id}
                onClick={() => handlePay(method)}
                className={`
                  w-full flex items-center gap-4 px-5 py-4 rounded-2xl border-2
                  ${method.bg} ${method.text} ${method.border}
                  active:scale-98 transition-all shadow-sm hover:shadow-md
                `}
              >
                <span className="text-3xl flex-shrink-0">{method.icon}</span>
                <div className="text-left flex-1">
                  <p className="font-bold text-base">{method.label}</p>
                  <p className={`text-xs mt-0.5 ${method.id === 'card' ? 'text-gray-400' : 'opacity-75'}`}>
                    {method.desc}
                  </p>
                </div>
                <span className={`text-xl flex-shrink-0 ${method.id === 'card' ? 'text-gray-400' : 'opacity-60'}`}>
                  ›
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* 안내 문구 */}
        <p className="text-center text-xs text-gray-400 mt-4">
          결제 수단을 탭하면 바로 결제가 시작됩니다
        </p>
      </div>
    </div>
  )
}
