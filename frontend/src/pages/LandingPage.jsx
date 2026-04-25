// 랜딩 페이지 — 연령대 직접 선택 or 사용자 인식(카메라) 중 선택

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const AGE_GROUPS = [
  { label: '어린이', emoji: '🧒', range: '0 ~ 12세',  ageGroup: '어린이', ageEst: 6  },
  { label: '청년',   emoji: '😊', range: '13 ~ 30세', ageGroup: '청년',   ageEst: 20 },
  { label: '중년',   emoji: '🙂', range: '31 ~ 60세', ageGroup: '중년',   ageEst: 45 },
  { label: '노년',   emoji: '👴', range: '61세 이후',  ageGroup: '노년',   ageEst: 65 },
]

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

  const createSession = async () => {
    const startedAt = performance.now()
    const sessionRes = await api.post('/api/v1/sessions')
    const { session_uuid } = sessionRes.data
    dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
    sessionStorage.setItem('session_uuid', session_uuid)
    logger.log('session', 'landing', {
      actionName: 'session_start',
      source: 'system',
      payload: { session_uuid },
    })
    // 로그 flush는 네비게이션을 막을 필요 없음 — fire-and-forget
    logger.flush(session_uuid).catch(() => {})
    logClientTiming('landing.createSession', performance.now() - startedAt, {
      session_uuid,
    })
    return session_uuid
  }

  const handleAgeGroupSelect = async (group) => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      logger.log('click', 'landing', {
        actionName: 'age_group_select',
        targetType: 'button',
        targetLabel: group.ageGroup,
      })
      await createSession()
      dispatch({
        type: ACTIONS.SET_VISION,
        payload: {
          ageGroup: group.ageGroup,
          gender: 'unknown',
          ageEst: group.ageEst,
          isSimpleMode: false,
        },
      })
      navigate('/kiosk')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        setError('키오스크 인증 정보가 올바르지 않습니다. 환경변수(VITE_KIOSK_API_KEY)를 확인해주세요.')
      } else {
        setError('시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleFaceRecognition = async () => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      logger.log('click', 'landing', {
        actionName: 'face_recognition_click',
        targetType: 'button',
        targetLabel: 'camera',
      })
      await createSession()
      navigate('/camera')
    } catch (err) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        setError('키오스크 인증 정보가 올바르지 않습니다. 환경변수(VITE_KIOSK_API_KEY)를 확인해주세요.')
      } else {
        setError('시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6 py-10">
      {/* 카페 로고 영역 */}
      <div className="mb-8 text-center">
        <div className="text-6xl mb-4">☕</div>
        <h1 className="text-3xl md:text-4xl font-bold text-amber-900">Cafe AI Kiosk</h1>
        <div className="mt-1 h-1 w-24 bg-amber-500 mx-auto rounded-full" />
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-100 border border-red-300 text-red-700 rounded-xl text-sm text-center max-w-sm w-full">
          {error}
        </div>
      )}

      {/* 연령대 직접 선택 */}
      <div className="w-full max-w-sm mb-6">
        <p className="text-sm font-semibold text-amber-700 mb-3 text-center">
          연령대를 직접 선택해주세요
        </p>
        <div className="grid grid-cols-2 gap-3">
          {AGE_GROUPS.map((group) => (
            <button
              key={group.ageGroup}
              onClick={() => handleAgeGroupSelect(group)}
              disabled={loading}
              className="
                flex flex-col items-center justify-center
                min-h-[96px] py-4 px-3
                bg-white border-2 border-amber-200
                hover:border-amber-400 hover:bg-amber-50
                active:bg-amber-100
                disabled:opacity-50 disabled:cursor-not-allowed
                rounded-2xl shadow-sm
                transition-colors duration-150
              "
            >
              <span className="text-3xl mb-1">{group.emoji}</span>
              <span className="text-base font-bold text-amber-900">{group.label}</span>
              <span className="text-xs text-amber-500 mt-0.5">{group.range}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 구분선 */}
      <div className="flex items-center w-full max-w-sm mb-6">
        <div className="flex-1 h-px bg-amber-200" />
        <span className="mx-3 text-xs text-amber-400 font-medium">또는</span>
        <div className="flex-1 h-px bg-amber-200" />
      </div>

      {/* 사용자 인식 버튼 */}
      <div className="w-full max-w-sm">
        <p className="text-sm font-semibold text-amber-700 mb-3 text-center">
          카메라로 자동 인식
        </p>
        <button
          onClick={handleFaceRecognition}
          disabled={loading}
          className="
            w-full min-h-[56px] py-4
            bg-amber-500 hover:bg-amber-600 active:bg-amber-700
            disabled:bg-amber-300
            text-white text-lg font-bold
            rounded-2xl shadow-lg
            transition-colors duration-150
            flex items-center justify-center gap-2
          "
        >
          <span>📷</span>
          <span>{loading ? '시작 중...' : '사용자 인식'}</span>
        </button>
        <p className="text-xs text-amber-500 text-center mt-2">
          얼굴을 촬영해 연령대를 자동으로 분석합니다 · 이미지는 즉시 삭제됩니다
        </p>
      </div>

      {/* 하단 안내 */}
      <p className="mt-8 text-xs text-amber-400 text-center">
        이 서비스는 개인정보를 저장하지 않습니다
      </p>
    </div>
  )
}
