// 나이 선택 제거, 카메라 자동 인식
import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const NOTICE_DURATION_MS = 4000  // 공지 자동 넘김 시간

export default function LandingPage() {
  const navigate = useNavigate()
  const { dispatch, ACTIONS } = useSession()
  const logger = useLogger()

  const [phase, setPhase] = useState('notice')  // notice | loading
  const noticeTimer = useRef(null)

  // 공지 → 로딩 전환 + 세션 생성 + 카메라 이동
  const proceed = useCallback(async () => {
    if (phase !== 'notice') return
    clearTimeout(noticeTimer.current)
    setPhase('loading')

    try {
      logger.log('click', 'landing', { actionName: 'notice_confirm', source: 'user_or_timer' })

      const sessionRes = await api.post('/api/v1/sessions')
      const { session_uuid } = sessionRes.data

      dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
      sessionStorage.setItem('session_uuid', session_uuid)

      logger.log('session', 'landing', {
        actionName: 'session_start',
        source: 'system',
        payload: { session_uuid },
      })
      logger.flush(session_uuid).catch(() => {})

      navigate('/camera')
    } catch (err) {
      const status = err?.response?.status
      navigate('/select-age', {
        state: {
          error: status === 401 || status === 403
            ? '키오스크 인증 정보가 올바르지 않습니다.'
            : '시작할 수 없습니다. 잠시 후 다시 시도해주세요.',
        },
      })
    }
  }, [phase, dispatch, ACTIONS, logger, navigate])

  // 공지 화면 자동 타이머
  useEffect(() => {
    const enteredAt = Date.now()
    logger.logScreenEnter('landing')

    noticeTimer.current = setTimeout(() => {
      proceed()
    }, NOTICE_DURATION_MS)

    return () => {
      clearTimeout(noticeTimer.current)
      logger.logScreenExit('landing', Date.now() - enteredAt)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      onClick={proceed}
      className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden cursor-pointer select-none"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      {/* 배경 글로우 */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)',
          top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        }}
      />

      {/* 로고 */}
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-5"
        style={{
          background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)',
          boxShadow: '0 0 48px rgba(245,158,11,0.25)',
        }}
      >
        <span className="text-5xl">☕</span>
      </div>

      <h1 className="text-white font-black tracking-widest mb-1" style={{ fontSize: 28, letterSpacing: '0.25em' }}>
        BREW AI
      </h1>
      <p className="text-amber-400 font-medium mb-8" style={{ fontSize: 11, letterSpacing: '0.3em' }}>
        CAFÉ &amp; ROASTERY
      </p>

      {/* ── 공지 화면 ── */}
      {phase === 'notice' && (
        <div
          className="w-full max-w-sm mx-auto px-4"
          style={{ animation: 'fadeUp 0.4s ease both' }}
        >
          {/* 공지 카드 */}
          <div
            className="rounded-2xl p-5 mb-4"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(245,158,11,0.20)',
            }}
          >
            {/* 카메라 안내 */}
            <div className="flex items-start gap-3 mb-4">
              <span className="text-xl mt-0.5 flex-shrink-0">📷</span>
              <div>
                <p className="text-amber-400 font-bold text-sm mb-0.5">카메라 사용 안내</p>
                <p className="text-white/75 text-xs leading-relaxed">
                  맞춤 메뉴 추천을 위해 카메라로 연령대를 자동 분석합니다.
                </p>
              </div>
            </div>

            <div className="h-px bg-amber-900/30 mb-4" />

            {/* 개인정보 */}
            <div className="flex items-start gap-3">
              <span className="text-xl mt-0.5 flex-shrink-0">🔒</span>
              <div>
                <p className="text-amber-400 font-bold text-sm mb-0.5">개인정보 보호</p>
                <p className="text-white/75 text-xs leading-relaxed">
                  촬영 이미지는 분석 즉시 삭제되며 저장·전송되지 않습니다.
                </p>
              </div>
            </div>

            <div className="h-px bg-amber-900/30 mt-4 mb-3" />

            <p className="text-amber-600/50 text-xs text-center">
              화면을 터치하거나 잠시 기다리시면 자동으로 시작됩니다
            </p>
          </div>

          {/* 카운트다운 바 */}
          <div
            className="h-0.5 rounded-full overflow-hidden"
            style={{ background: 'rgba(245,158,11,0.15)' }}
          >
            <div
              className="h-full bg-amber-400 rounded-full"
              style={{ animation: `shrink ${NOTICE_DURATION_MS}ms linear forwards` }}
            />
          </div>
        </div>
      )}

      {/* ── 로딩 화면 ── */}
      {phase === 'loading' && (
        <div
          className="flex flex-col items-center gap-4"
          style={{ animation: 'fadeUp 0.4s ease both' }}
        >
          <div
            style={{
              width: 40, height: 40, borderRadius: '50%',
              border: '2px solid rgba(245,158,11,0.20)',
              borderTopColor: '#f59e0b',
              animation: 'spin 0.8s linear infinite',
            }}
          />
          <div className="flex gap-1.5">
            {[0, 0.2, 0.4].map((delay, i) => (
              <div
                key={i}
                style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: 'rgba(245,158,11,0.50)',
                  animation: `pulse 1.2s ${delay}s ease-in-out infinite`,
                }}
              />
            ))}
          </div>
          <p className="text-amber-600" style={{ fontSize: 13, letterSpacing: '0.05em' }}>
            잠시만 기다려 주세요...
          </p>
        </div>
      )}

      {/* 하단 */}
      <p
        className="absolute bottom-5 text-center"
        style={{ fontSize: 11, color: 'rgba(120,60,20,0.50)', letterSpacing: '0.03em' }}
      >
        © BREW AI CAFÉ · 개인정보를 저장하지 않습니다
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes shrink { from{width:100%} to{width:0%} }
      `}</style>
    </div>
  )
}