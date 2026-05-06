// 할인 선택 페이지 — 결제 전 할인 수단 선택
// 할인 항목 클릭 시 2초간 "바코드 인식 중" 화면 → PaymentPage 이동

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const DISCOUNT_OPTIONS = [
  {
    id: 'employee',
    label: '임직원 할인',
    emoji: '👔',
    desc: '임직원 사원증 바코드 인식',
    color: 'bg-blue-50 border-blue-200 hover:border-blue-400',
    badgeColor: 'bg-blue-100 text-blue-600',
  },
  {
    id: 'skt',
    label: 'SKT 멤버십',
    emoji: '📶',
    desc: 'T멤버십 바코드 인식',
    color: 'bg-red-50 border-red-200 hover:border-red-400',
    badgeColor: 'bg-red-100 text-red-600',
  },
  {
    id: 'lg',
    label: 'LG 멤버십',
    emoji: '📡',
    desc: 'LG U+ 멤버십 바코드 인식',
    color: 'bg-pink-50 border-pink-200 hover:border-pink-400',
    badgeColor: 'bg-pink-100 text-pink-600',
  },
  {
    id: 'gifticon',
    label: '기프티콘',
    emoji: '🎟️',
    desc: '기프티콘 바코드 인식',
    color: 'bg-amber-50 border-amber-200 hover:border-amber-400',
    badgeColor: 'bg-amber-100 text-amber-600',
  },
]

export default function DiscountPage() {
  const navigate = useNavigate()
  const { state } = useSession()
  const logger = useLogger(state.sessionUuid)

  // 'idle' | 'scanning' | 'done'
  const [scanStatus, setScanStatus] = useState('idle')
  const [selectedDiscount, setSelectedDiscount] = useState(null)

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)

  useEffect(() => {
    if (state.cart.length === 0) {
      navigate('/kiosk', { replace: true })
    }
  }, [state.cart.length, navigate])

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('discount')
    return () => logger.logScreenExit('discount', Date.now() - enteredAt)
  }, [logger])

  const handleDiscountSelect = (discount) => {
    logger.log('click', 'discount', {
      actionName: 'discount_select',
      targetType: 'button',
      targetLabel: discount.id,
    })
    setSelectedDiscount(discount)
    setScanStatus('scanning')

    setTimeout(() => {
      navigate('/payment', { state: { discountType: discount.id, discountLabel: discount.label } })
    }, 2000)
  }

  const handleSkip = () => {
    logger.log('click', 'discount', {
      actionName: 'skip_discount',
      targetType: 'button',
      targetLabel: 'no_discount',
    })
    navigate('/payment', { state: { discountType: null, discountLabel: null } })
  }

  // 바코드 인식 중 오버레이
  if (scanStatus === 'scanning') {
    return (
      <div className="fixed inset-0 bg-gray-900/95 flex flex-col items-center justify-center z-50">
        <div className="text-7xl mb-6 animate-pulse">{selectedDiscount?.emoji}</div>

        {/* 스캔 애니메이션 */}
        <div className="relative w-48 h-1.5 bg-gray-700 rounded-full mb-8 overflow-hidden">
          <div className="absolute inset-y-0 left-0 w-1/2 bg-amber-400 rounded-full animate-[scan_1s_ease-in-out_infinite]" />
        </div>

        <h2 className="text-2xl font-black text-white mb-2">바코드 인식 중</h2>
        <p className="text-gray-400 text-sm">{selectedDiscount?.label} 바코드를 인식하고 있어요</p>

        <style>{`
          @keyframes scan {
            0%   { left: 0%;   width: 40%; }
            50%  { left: 60%;  width: 40%; }
            100% { left: 0%;   width: 40%; }
          }
        `}</style>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f9f5f0' }}>

      {/* 헤더 */}
      <header className="bg-white shadow-sm px-5 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button
          onClick={() => navigate('/cart-review')}
          className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-500 hover:bg-gray-100 active:bg-gray-200 transition-colors"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-800">할인 선택</h1>
          <p className="text-xs text-gray-400">결제 전 할인 수단을 선택하세요</p>
        </div>
      </header>

      <div className="flex-1 px-4 py-5 pb-36">
        {/* 결제 금액 요약 */}
        <div className="bg-white rounded-2xl px-5 py-4 mb-6 shadow-sm border border-gray-100 flex justify-between items-center">
          <span className="text-gray-500 text-sm font-medium">현재 결제 금액</span>
          <span className="text-xl font-black text-amber-600">{totalPrice.toLocaleString()}원</span>
        </div>

        <p className="text-xs font-bold text-gray-400 uppercase tracking-widest px-1 mb-4">
          할인 수단
        </p>

        {/* 할인 옵션 2×2 그리드 */}
        <div className="grid grid-cols-2 gap-3">
          {DISCOUNT_OPTIONS.map((option) => (
            <button
              key={option.id}
              onClick={() => handleDiscountSelect(option)}
              className={`
                flex flex-col items-center justify-center
                min-h-[140px] py-6 px-3
                rounded-2xl border-2
                ${option.color}
                active:scale-95 transition-all duration-150
                bg-white
              `}
            >
              <span className="text-4xl mb-3">{option.emoji}</span>
              <span className="font-bold text-gray-800 text-base">{option.label}</span>
              <span className="text-xs text-gray-400 mt-1 text-center leading-relaxed">{option.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 하단 — 할인 없이 결제 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 shadow-xl px-4 pt-4 pb-6">
        <button
          onClick={handleSkip}
          className="
            w-full min-h-[54px] rounded-2xl
            bg-gray-800 hover:bg-gray-700 active:bg-gray-900
            text-white font-bold text-base
            active:scale-95 transition-all duration-150
          "
        >
          할인 없이 결제 진행
        </button>
        <p className="text-center text-xs text-gray-400 mt-3">할인 수단이 없으면 위 버튼을 누르세요</p>
      </div>
    </div>
  )
}
