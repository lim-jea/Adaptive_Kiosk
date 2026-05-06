// 랜딩 페이지 — 얼굴 인식(상단 메인 CTA) or 연령대 직접 선택(하단)

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
      navigate('/order-type')
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
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-10">

        {/* 로고 */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 rounded-full bg-amber-500 flex items-center justify-center shadow-2xl shadow-amber-900/50 mb-4 mx-auto">
            <span className="text-4xl">☕</span>
          </div>
          <h1 className="text-4xl font-black text-white tracking-widest">BREW AI</h1>
          <p className="text-amber-400 text-sm font-medium tracking-widest mt-1">CAFÉ & ROASTERY</p>
        </div>

        {/* 에러 */}
        {error && (
          <div className="mb-4 px-4 py-3 bg-red-900/50 border border-red-700 text-red-300 rounded-xl text-sm text-center w-full max-w-sm">
            {error}
          </div>
        )}

        {/* ── 메인 CTA: 얼굴 인식 버튼 ── */}
        <div className="w-full max-w-sm mb-8">
          <button
            onClick={handleFaceRecognition}
            disabled={loading}
            className="
              relative w-full py-9 px-6
              rounded-3xl overflow-hidden
              disabled:opacity-60 disabled:cursor-not-allowed
              active:scale-95 transition-transform duration-150
              flex flex-col items-center gap-3
            "
            style={{
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 60%, #b45309 100%)',
              boxShadow: '0 0 40px rgba(245,158,11,0.45), 0 8px 32px rgba(0,0,0,0.4)',
            }}
          >
            {/* 배경 광택 효과 */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{ background: 'linear-gradient(160deg, rgba(255,255,255,0.15) 0%, transparent 60%)' }}
            />

            <span className="text-6xl relative z-10 drop-shadow-md">📷</span>
            <span className="text-white text-2xl font-black tracking-wide relative z-10">
              {loading && !loadingGroup ? '시작 중...' : '얼굴 인식으로 시작'}
            </span>
            <span className="text-amber-100/75 text-sm relative z-10">
              카메라로 연령대를 자동 분석합니다
            </span>

            {/* 하단 안내 배지 */}
            <div className="relative z-10 mt-1 px-3 py-1 bg-black/20 rounded-full">
              <span className="text-amber-200/80 text-xs">이미지는 즉시 삭제 · 개인정보 미저장</span>
            </div>
          </button>
        </div>

        {/* 구분선 */}
        <div className="flex items-center gap-3 mb-6 w-full max-w-sm">
          <div className="flex-1 h-px bg-amber-800/40" />
          <span className="text-amber-600/70 text-xs tracking-widest">또는 직접 선택</span>
          <div className="flex-1 h-px bg-amber-800/40" />
        </div>

        {/* ── 연령대 직접 선택 ── */}
        <div className="w-full max-w-sm">
          <p className="text-amber-500/60 text-xs font-medium text-center tracking-widest mb-4 uppercase">
            연령대를 선택해주세요
          </p>
          <div className="grid grid-cols-4 gap-2">
            {AGE_GROUPS.map((group) => (
              <button
                key={group.ageGroup}
                onClick={() => handleAgeGroupSelect(group)}
                disabled={loading}
                className={`
                  flex flex-col items-center justify-center
                  py-4 px-1
                  rounded-2xl border transition-all duration-200
                  ${loadingGroup === group.ageGroup
                    ? 'border-amber-400 bg-amber-500/20 scale-95'
                    : 'border-amber-800/50 bg-white/5 hover:bg-white/10 hover:border-amber-600/60 active:scale-95'}
                  disabled:opacity-60 disabled:cursor-not-allowed
                `}
              >
                <span className="text-2xl mb-1">{group.emoji}</span>
                <span className="text-sm font-bold text-white">{group.label}</span>
                <span className="text-xs text-amber-500/60 mt-0.5 text-center leading-tight">{group.range}</span>
              </button>
            ))}
          </div>
        </div>

      </div>

      {/* 하단 */}
      <div className="px-6 pb-6 text-center">
        <p className="text-xs text-amber-900/50">© BREW AI CAFÉ · 개인정보를 저장하지 않습니다</p>
      </div>
    </div>
  )
}
