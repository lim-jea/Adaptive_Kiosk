// 랜딩 페이지 — 연령대 직접 선택 or 사용자 인식(카메라) 중 선택

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
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
  const [loadingGroup, setLoadingGroup] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('landing')
    return () => {
      logger.logScreenExit('landing', Date.now() - enteredAt)
    }
  }, [logger])

  const createSession = async () => {
    const sessionRes = await api.post('/api/v1/sessions')
    const { session_uuid } = sessionRes.data
    dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
    sessionStorage.setItem('session_uuid', session_uuid)
    logger.log('session', 'landing', { actionName: 'session_start', source: 'system', payload: { session_uuid } })
    logger.flush(session_uuid).catch(() => {})
    return session_uuid
  }

  const handleAgeGroupSelect = async (group) => {
    if (loading) return
    setLoading(true)
    setLoadingGroup(group.ageGroup)
    setError(null)
    try {
      logger.log('click', 'landing', { actionName: 'age_group_select', targetType: 'button', targetLabel: group.ageGroup })
      await createSession()
      dispatch({
        type: ACTIONS.SET_VISION,
        payload: { ageGroup: group.ageGroup, gender: 'unknown', ageEst: group.ageEst, isSimpleMode: false },
      })
      navigate('/kiosk')
    } catch (err) {
      const status = err?.response?.status
      setError(status === 401 || status === 403
        ? '키오스크 인증 정보가 올바르지 않습니다. 환경변수(VITE_KIOSK_API_KEY)를 확인해주세요.'
        : '시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
    } finally {
      setLoading(false)
      setLoadingGroup(null)
    }
  }

  const handleFaceRecognition = async () => {
    if (loading) return
    setLoading(true)
    setError(null)
    try {
      logger.log('click', 'landing', { actionName: 'face_recognition_click', targetType: 'button', targetLabel: 'camera' })
      await createSession()
      navigate('/camera')
    } catch (err) {
      const status = err?.response?.status
      setError(status === 401 || status === 403
        ? '키오스크 인증 정보가 올바르지 않습니다. 환경변수(VITE_KIOSK_API_KEY)를 확인해주세요.'
        : '시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}>
      {/* 헤더 브랜드 영역 */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pt-12 pb-6">
        {/* 로고 */}
        <div className="mb-2">
          <div className="w-20 h-20 rounded-full bg-amber-500 flex items-center justify-center shadow-2xl shadow-amber-900/50 mb-5 mx-auto">
            <span className="text-4xl">☕</span>
          </div>
          <h1 className="text-4xl font-black text-white tracking-widest text-center">BREW AI</h1>
          <p className="text-amber-400 text-center text-sm font-medium tracking-widest mt-1">CAFÉ & ROASTERY</p>
        </div>

        {/* 구분선 */}
        <div className="flex items-center gap-3 my-6 w-full max-w-sm">
          <div className="flex-1 h-px bg-amber-800/50" />
          <span className="text-amber-600 text-xs tracking-widest">WELCOME</span>
          <div className="flex-1 h-px bg-amber-800/50" />
        </div>

        {/* 에러 */}
        {error && (
          <div className="mb-4 px-4 py-3 bg-red-900/50 border border-red-700 text-red-300 rounded-xl text-sm text-center max-w-sm w-full">
            {error}
          </div>
        )}

        {/* 연령대 선택 */}
        <div className="w-full max-w-sm">
          <p className="text-amber-400/80 text-xs font-medium text-center tracking-widest mb-4 uppercase">
            연령대를 선택해주세요
          </p>
          <div className="grid grid-cols-2 gap-3 mb-6">
            {AGE_GROUPS.map((group) => (
              <button
                key={group.ageGroup}
                onClick={() => handleAgeGroupSelect(group)}
                disabled={loading}
                className={`
                  flex flex-col items-center justify-center
                  min-h-[100px] py-5 px-3
                  rounded-2xl border transition-all duration-200
                  ${loadingGroup === group.ageGroup
                    ? 'border-amber-400 bg-amber-500/20 scale-95'
                    : 'border-amber-800/60 bg-white/5 hover:bg-white/10 hover:border-amber-500/60 active:scale-95'}
                  disabled:opacity-60 disabled:cursor-not-allowed
                `}
              >
                <span className="text-3xl mb-2">{group.emoji}</span>
                <span className="text-base font-bold text-white">{group.label}</span>
                <span className="text-xs text-amber-500/70 mt-0.5">{group.range}</span>
              </button>
            ))}
          </div>

          {/* 구분선 */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-amber-800/40" />
            <span className="text-amber-700 text-xs">또는</span>
            <div className="flex-1 h-px bg-amber-800/40" />
          </div>

          {/* 사용자 인식 버튼 */}
          <button
            onClick={handleFaceRecognition}
            disabled={loading}
            className="
              w-full min-h-[56px] py-4
              bg-amber-500 hover:bg-amber-400 active:bg-amber-600
              disabled:bg-amber-800/50 disabled:cursor-not-allowed
              text-white text-base font-bold
              rounded-2xl shadow-lg shadow-amber-900/40
              transition-all duration-200 active:scale-95
              flex items-center justify-center gap-3
            "
          >
            <span className="text-lg">📷</span>
            <span>{loading && !loadingGroup ? '시작 중...' : '얼굴 인식으로 시작'}</span>
          </button>
          <p className="text-xs text-amber-700/60 text-center mt-3">
            카메라로 연령대를 자동 분석합니다 · 이미지는 즉시 삭제
          </p>
        </div>
      </div>

      {/* 하단 */}
      <div className="px-6 pb-8 text-center">
        <p className="text-xs text-amber-900/60">© BREW AI CAFÉ · 개인정보를 저장하지 않습니다</p>
      </div>
    </div>
  )
}
