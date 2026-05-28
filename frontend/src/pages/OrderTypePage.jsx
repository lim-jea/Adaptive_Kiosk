// 포장/매장 선택 페이지 — 나이에 따라 키오스크 모드 분기
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { useCallback } from 'react'
import { getKioskRoute } from '../utils/routes'

export default function OrderTypePage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const kioskRoute = useCallback(() => getKioskRoute(state.ageGroup), [state.ageGroup])

  const handleSelect = useCallback((orderType) => {
    logger.log('click', 'ordertype', {
      actionName: 'order_type_select',
      targetType: 'button',
      targetLabel: orderType,
      payload: { age_group: state.ageGroup },
    })
    dispatch({
      type: ACTIONS.SET_ORDER_TYPE,
      payload: { orderType },
    })
    navigate(kioskRoute())
  }, [logger, dispatch, ACTIONS, navigate, kioskRoute, state.ageGroup])

  const isSenior = state.ageGroup === '노년'

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">

      {/* 로고 */}
      <div className="mb-10 text-center">
        <div className="w-16 h-16 rounded-full bg-amber-500 flex items-center justify-center shadow-xl mx-auto mb-4">
          <span className="text-3xl">☕</span>
        </div>
        <h1 className="text-2xl font-black text-amber-900 tracking-widest">BREW AI</h1>
      </div>

      {/* 안내 문구 */}
      <div className="mb-8 text-center">
        <p className={`font-bold text-gray-800 ${isSenior ? 'text-3xl' : 'text-2xl'}`}>
          어떻게 이용하시겠어요?
        </p>
        <p className={`text-gray-400 mt-2 ${isSenior ? 'text-xl' : 'text-base'}`}>
          포장 또는 매장 이용을 선택해 주세요
        </p>
      </div>

      {/* 선택 버튼 */}
      <div className="flex flex-col gap-4 w-full max-w-sm">
        <button
          onClick={() => handleSelect('dine_in')}
          className={`w-full bg-white rounded-3xl border-2 border-gray-200 shadow-sm
            hover:border-amber-400 hover:shadow-md active:scale-95 transition-all
            flex items-center gap-5
            ${isSenior ? 'px-8 py-8' : 'px-6 py-6'}`}
        >
          <span className={isSenior ? 'text-6xl' : 'text-5xl'}>🪑</span>
          <div className="text-left">
            <p className={`font-black text-gray-800 ${isSenior ? 'text-3xl' : 'text-2xl'}`}>
              매장 이용
            </p>
            <p className={`text-gray-400 mt-1 ${isSenior ? 'text-xl' : 'text-base'}`}>
              카페 안에서 드실 분
            </p>
          </div>
        </button>

        <button
          onClick={() => handleSelect('takeout')}
          className={`w-full bg-amber-500 hover:bg-amber-600 active:bg-amber-700 rounded-3xl
            shadow-sm hover:shadow-md active:scale-95 transition-all
            flex items-center gap-5
            ${isSenior ? 'px-8 py-8' : 'px-6 py-6'}`}
        >
          <span className={isSenior ? 'text-6xl' : 'text-5xl'}>🛍️</span>
          <div className="text-left">
            <p className={`font-black text-white ${isSenior ? 'text-3xl' : 'text-2xl'}`}>
              포장
            </p>
            <p className={`text-amber-100 mt-1 ${isSenior ? 'text-xl' : 'text-base'}`}>
              가지고 가실 분
            </p>
          </div>
        </button>
      </div>

      {/* 뒤로가기 */}
      <button
        onClick={() => navigate(-1)}
        className={`mt-8 text-gray-400 hover:text-gray-600 transition-colors
          ${isSenior ? 'text-xl' : 'text-base'}`}
      >
        ← 뒤로가기
      </button>
    </div>
  )
}
