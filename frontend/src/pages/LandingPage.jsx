// 랜딩 페이지 — 얼굴 인식(상단 메인 CTA) or 연령대 직접 선택(하단)

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { setSessionToken } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import ConsentModal from '../components/ConsentModal'

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
  const [consentOpen, setConsentOpen] = useState(false)

  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('landing')
    return () => {
      logger.logScreenExit('landing', Date.now() - enteredAt)
    }
  }, [logger])

  const createSession = async () => {
    const sessionRes = await api.post('/api/v1/sessions')
    const { session_uuid, access_token, expires_in } = sessionRes.data
    // 백엔드가 발급한 단기 토큰 저장 — 이후 모든 호출이 X-Session-Token 사용
    setSessionToken(access_token, expires_in)
    dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
    sessionStorage.setItem('session_uuid', session_uuid)
    sessionStorage.removeItem('stamp_before_payment_done')
    sessionStorage.removeItem('stamp_before_payment_skipped')
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

  // ── 히든 어드민 진입 — 로고를 1.5초 안에 5번 연속 탭 ──
  const adminTapCountRef = useRef(0)
  const adminLastTapRef = useRef(0)
  const handleLogoTap = () => {
    const now = Date.now()
    if (now - adminLastTapRef.current > 1500) {
      adminTapCountRef.current = 1
    } else {
      adminTapCountRef.current += 1
    }
    adminLastTapRef.current = now
    if (adminTapCountRef.current >= 5) {
      adminTapCountRef.current = 0
      navigate('/admin/login')
    }
  }

  const handleFaceRecognition = () => {
    if (loading) return
    setError(null)
    logger.log('click', 'landing', { actionName: 'face_recognition_click', targetType: 'button', targetLabel: 'camera' })
    logger.log('consent', 'landing', { actionName: 'consent_view', targetType: 'modal', targetLabel: 'face_consent' })
    setConsentOpen(true)
  }

  const handleConsentAccept = async (consentAt) => {
    setConsentOpen(false)
    if (loading) return
    setLoading(true)
    try {
      logger.log('consent', 'landing', {
        actionName: 'consent_accepted',
        targetType: 'modal',
        targetLabel: 'face_consent',
        payload: { consent_at: consentAt, scope: 'face_analysis' },
      })
      sessionStorage.setItem('face_consent_at', consentAt)
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

  const handleConsentDecline = () => {
    setConsentOpen(false)
    logger.log('consent', 'landing', {
      actionName: 'consent_declined',
      targetType: 'modal',
      targetLabel: 'face_consent',
      payload: { scope: 'face_analysis' },
    })
  }

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-10">

        {/* 로고 — 1.5초 안에 5번 연속 탭하면 관리자 로그인 진입 (손님에게는 보이지 않는 히든 동작) */}
        <div className="text-center mb-8" onClick={handleLogoTap} style={{ cursor: 'default' }}>
          <svg
            width="110"
            height="110"
            viewBox="0 0 110 110"
            xmlns="http://www.w3.org/2000/svg"
            className="mx-auto mb-3 select-none"
            style={{ filter: 'drop-shadow(0 8px 24px rgba(245,158,11,0.5))' }}
          >
            {/* 외곽 원형 배지 */}
            <circle cx="55" cy="55" r="52" fill="url(#bgGrad)" />
            <circle cx="55" cy="55" r="52" fill="none" stroke="#f59e0b" strokeWidth="2.5" opacity="0.7" />
            <circle cx="55" cy="55" r="46" fill="none" stroke="#fde047" strokeWidth="1" opacity="0.35" />

            {/* 커피 컵 몸체 */}
            <path d="M34 48 L38 76 Q38 80 42 80 L68 80 Q72 80 72 76 L76 48 Z" fill="#1a0800" stroke="#f59e0b" strokeWidth="1.5" />
            {/* 컵 상단 테두리 */}
            <rect x="32" y="44" width="46" height="6" rx="3" fill="#f59e0b" />
            {/* 컵 손잡이 */}
            <path d="M72 55 Q84 55 84 63 Q84 71 72 71" fill="none" stroke="#f59e0b" strokeWidth="3" strokeLinecap="round" />
            {/* 커피 액체 */}
            <path d="M38 50 L72 50 L70 70 Q70 72 68 72 L42 72 Q40 72 40 70 Z" fill="#7c3a00" opacity="0.7" />
            {/* 컵 하이라이트 */}
            <path d="M42 54 Q44 60 43 68" stroke="#f59e0b" strokeWidth="1.2" fill="none" opacity="0.4" strokeLinecap="round" />

            {/* 스팀 연기 */}
            <path d="M44 40 Q42 34 44 28 Q46 22 44 16" fill="none" stroke="#fde047" strokeWidth="2" strokeLinecap="round" opacity="0.75" />
            <path d="M55 38 Q53 32 55 26 Q57 20 55 14" fill="none" stroke="#fde047" strokeWidth="2" strokeLinecap="round" opacity="0.75" />
            <path d="M66 40 Q64 34 66 28 Q68 22 66 16" fill="none" stroke="#fde047" strokeWidth="2" strokeLinecap="round" opacity="0.75" />

            {/* 그라디언트 정의 */}
            <defs>
              <radialGradient id="bgGrad" cx="40%" cy="35%" r="65%">
                <stop offset="0%" stopColor="#3b1a08" />
                <stop offset="100%" stopColor="#1a0800" />
              </radialGradient>
            </defs>
          </svg>

          <h1 className="text-4xl font-black text-white tracking-widest select-none">BREW AI</h1>
          <p className="text-amber-400 text-sm font-medium tracking-widest mt-1 select-none">CAFÉ & ROASTERY</p>
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
              rounded-3xl overflow-hidden border-4 border-yellow-200
              disabled:opacity-60 disabled:cursor-not-allowed
              active:scale-95 transition-all duration-150
              flex flex-col items-center gap-3
            "
            style={{
              background: 'linear-gradient(135deg, #fde047 0%, #f59e0b 48%, #ea580c 100%)',
              boxShadow: '0 0 0 6px rgba(254,240,138,0.22), 0 0 56px rgba(250,204,21,0.62), 0 12px 36px rgba(0,0,0,0.45)',
            }}
          >
            {/* 배경 광택 효과 */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{ background: 'linear-gradient(160deg, rgba(255,255,255,0.15) 0%, transparent 60%)' }}
            />

            <span className="text-white text-2xl font-black tracking-wide relative z-10">
              {loading && !loadingGroup ? '시작 중...' : '눌러서 얼굴 인식 시작'}
            </span>
            <span className="text-white/90 text-sm font-bold relative z-10">
              버튼을 누르면 카메라 화면으로 이동합니다
            </span>

            {/* 하단 안내 배지 */}
            <div className="relative z-10 mt-1 px-4 py-1.5 bg-black/25 rounded-full border border-white/20">
              <span className="text-white/90 text-xs font-bold">촬영 이미지는 즉시 삭제 · 개인정보 미저장</span>
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

      <ConsentModal
        open={consentOpen}
        onAccept={handleConsentAccept}
        onDecline={handleConsentDecline}
      />
    </div>
  )
}
