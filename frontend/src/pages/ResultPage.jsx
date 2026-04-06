// 결과 페이지 — 얼굴 분석 결과 표시 + 주문 진입

import { useNavigate, useLocation } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'

const GENDER_LABEL = {
  male: '남성',
  female: '여성',
  unknown: '알 수 없음',
}

const AGE_GROUP_EMOJI = {
  어린이: '🧒',
  청년: '😊',
  중장년: '🙂',
  노년: '👴',
}

export default function ResultPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { dispatch, ACTIONS } = useSession()

  const {
    age_group,
    gender,
    age_est,
    should_use_simple_mode,
    sessionUuid,
  } = location.state || {}

  if (!age_group) {
    navigate('/', { replace: true })
    return null
  }

  const handleOrder = () => {
    dispatch({
      type: ACTIONS.SET_VISION,
      payload: {
        ageGroup: age_group,
        gender,
        ageEst: age_est,
        isSimpleMode: should_use_simple_mode,
      },
    })
    navigate('/kiosk')
  }

  const handleRetry = () => {
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">
      <div className="bg-white rounded-3xl shadow-xl px-8 py-10 w-full max-w-sm text-center">
        <div className="text-6xl mb-4">{AGE_GROUP_EMOJI[age_group] || '😊'}</div>
        <h2 className="text-2xl font-bold text-gray-800 mb-1">분석 완료!</h2>
        <p className="text-gray-400 text-sm mb-8">AI가 당신을 분석했어요</p>

        <div className="space-y-4 text-left">
          <ResultRow label="연령대" value={age_group} />
          <ResultRow label="성별" value={GENDER_LABEL[gender] || gender} />
          <ResultRow label="추정 나이" value={`${age_est}세`} />
          {should_use_simple_mode && (
            <ResultRow label="모드" value="간편 모드" />
          )}
        </div>

        <div className="my-8 border-t border-gray-100" />

        <button
          onClick={handleOrder}
          className="w-full min-h-[56px] py-4 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white text-lg font-bold rounded-2xl shadow-md transition-colors duration-150 mb-3"
        >
          주문하러 가기 →
        </button>
        <button
          onClick={handleRetry}
          className="w-full min-h-[48px] py-3 bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-600 text-base font-medium rounded-2xl transition-colors duration-150"
        >
          다시 시도
        </button>
      </div>

      {import.meta.env.DEV && sessionUuid && (
        <p className="mt-6 text-xs text-gray-400 font-mono">
          session: {sessionUuid.slice(0, 8)}...
        </p>
      )}
    </div>
  )
}

function ResultRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-3 px-4 bg-amber-50 rounded-xl">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="text-gray-800 font-semibold">{value}</span>
    </div>
  )
}
