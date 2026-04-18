// 랜딩 페이지 — 키오스크 시작 화면
// "시작하기" 버튼 클릭 시 세션 시작(X-API-Key) 후 CameraPage 이동

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

export default function LandingPage() {
  const navigate = useNavigate()
  const { dispatch, ACTIONS } = useSession()
  const logger = useLogger()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('landing')
    return () => {
      logger.logScreenExit('landing', Date.now() - enteredAt)
    }
  }, [logger])

  const handleStart = async () => {
    setLoading(true)
    setError(null)

    try {
      logger.log('click', 'landing', {
        actionName: 'start_click',
        targetType: 'button',
        targetLabel: 'start',
      })
      // 세션 생성 (X-API-Key는 axios 인터셉터에서 자동 첨부)
      const sessionRes = await api.post('/api/v1/sessions')
      const { session_uuid } = sessionRes.data

      dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
      sessionStorage.setItem('session_uuid', session_uuid)
      logger.log('session', 'landing', {
        actionName: 'session_start',
        source: 'system',
        payload: { session_uuid },
      })
      await logger.flush(session_uuid)

      navigate('/camera')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        setError('키오스크 인증 정보가 올바르지 않습니다. 프론트엔드 환경변수(VITE_KIOSK_API_KEY)를 확인해주세요.')
      } else {
        setError('시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">
      {/* 카페 로고 영역 */}
      <div className="mb-10 text-center">
        <div className="text-6xl mb-4">☕</div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-amber-900">
          Cafe AI Kiosk
        </h1>
        <div className="mt-1 h-1 w-24 bg-amber-500 mx-auto rounded-full" />
      </div>

      {/* 메인 문구 */}
      <p className="text-lg md:text-xl lg:text-2xl text-amber-800 text-center mb-2 font-medium">
        AI가 당신에게 맞는
      </p>
      <p className="text-lg md:text-xl lg:text-2xl text-amber-800 text-center mb-10 font-medium">
        메뉴를 추천해드립니다
      </p>

      {/* 안내 문구 */}
      <p className="text-sm md:text-base text-amber-600 text-center mb-8 max-w-sm">
        얼굴을 1초 동안 촬영하여 연령대와 성별을 분석합니다.
        <br />
        이미지는 분석 후 즉시 삭제됩니다.
      </p>

      {/* 에러 메시지 */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-100 border border-red-300 text-red-700 rounded-xl text-sm text-center max-w-sm">
          {error}
        </div>
      )}

      {/* 시작하기 버튼 — 터치 친화적 최소 48px */}
      <button
        onClick={handleStart}
        disabled={loading}
        className="
          min-h-[56px] px-12 py-4
          bg-amber-500 hover:bg-amber-600 active:bg-amber-700
          disabled:bg-amber-300
          text-white text-lg md:text-xl font-bold
          rounded-2xl shadow-lg
          transition-colors duration-150
          w-full max-w-xs
        "
      >
        {loading ? '시작 중...' : '시작하기'}
      </button>

      {/* 하단 안내 */}
      <p className="mt-8 text-xs text-amber-500 text-center">
        이 서비스는 개인정보를 저장하지 않습니다
      </p>
    </div>
  )
}
