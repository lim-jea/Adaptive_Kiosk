// 이용 방법 선택 페이지 — 매장 이용 or 포장·픽업
// 얼굴 인식 경로(ResultPage)와 직접 선택 경로(LandingPage) 모두 여기로 합류

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const ORDER_TYPES = [
  {
    type: 'dine-in',
    label: '매장 이용',
    emoji: '🪑',
    description: '매장 내에서\n편안하게 즐기세요',
  },
  {
    type: 'pickup',
    label: '포장 / 픽업',
    emoji: '🛍️',
    description: '포장하여\n가져가세요',
  },
]

export default function OrderTypePage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  useEffect(() => {
    if (!state.ageGroup) {
      navigate('/', { replace: true })
    }
  }, [state.ageGroup, navigate])

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('order_type')
    return () => {
      logger.logScreenExit('order_type', Date.now() - enteredAt)
    }
  }, [logger])

  const handleSelect = (orderType) => {
    logger.log('click', 'order_type', {
      actionName: 'order_type_select',
      targetType: 'button',
      targetLabel: orderType,
    })
    dispatch({ type: ACTIONS.SET_ORDER_TYPE, payload: { orderType } })
    navigate('/kiosk')
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}>

      {/* 헤더 */}
      <div className="text-center mb-10">
        <div className="w-16 h-16 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">☕</span>
        </div>
        <h2 className="text-2xl font-black text-white tracking-wide mb-2">이용 방법을 선택해 주세요</h2>
        <p className="text-amber-400/70 text-sm">매장 이용 또는 포장 중 하나를 선택하세요</p>
      </div>

      {/* 선택 카드 */}
      <div className="grid grid-cols-2 gap-4 w-full max-w-sm">
        {ORDER_TYPES.map(({ type, label, emoji, description }) => (
          <button
            key={type}
            onClick={() => handleSelect(type)}
            className="
              flex flex-col items-center justify-center
              min-h-[180px] py-8 px-4
              rounded-3xl border-2 border-amber-800/50
              bg-white/5
              hover:bg-amber-500/15 hover:border-amber-400/80
              active:scale-95 active:bg-amber-500/25
              transition-all duration-200
              group
            "
          >
            <span className="text-5xl mb-4 group-hover:scale-110 transition-transform duration-200">
              {emoji}
            </span>
            <span className="text-white font-bold text-lg mb-2">{label}</span>
            <span className="text-amber-400/60 text-xs text-center leading-relaxed whitespace-pre-line">
              {description}
            </span>
          </button>
        ))}
      </div>

      {/* 하단 안내 */}
      <p className="mt-8 text-amber-900/50 text-xs">
        선택 후 메뉴 화면으로 이동합니다
      </p>
    </div>
  )
}
