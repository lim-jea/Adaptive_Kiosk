// 자동으로 화면 전환
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

export default function LandingPage() {
  const navigate = useNavigate()
  const { dispatch, ACTIONS } = useSession()
  const logger = useLogger()
  const didRun = useRef(false)

  useEffect(() => {
    // StrictMode 이중 실행 방지
    if (didRun.current) return
    didRun.current = true

    const enteredAt = Date.now()
    logger.logScreenEnter('landing')

    const start = async () => {
      try {
        logger.log('click', 'landing', {
          actionName: 'auto_start',
          targetType: 'system',
          targetLabel: 'auto',
        })

        const sessionRes = await api.post('/api/v1/sessions')
        const { session_uuid } = sessionRes.data

        dispatch({
          type: ACTIONS.SET_SESSION,
          payload: { sessionUuid: session_uuid },
        })
        sessionStorage.setItem('session_uuid', session_uuid)

        logger.log('session', 'landing', {
          actionName: 'session_start',
          source: 'system',
          payload: { session_uuid },
        })
        logger.flush(session_uuid).catch(() => {})

        logger.logScreenExit('landing', Date.now() - enteredAt)
        navigate('/camera')
      } catch (err) {
        // 세션 생성 실패 시 수동 선택 페이지로 fallback
        logger.logScreenExit('landing', Date.now() - enteredAt)
        navigate('/select-age', { state: { error: err } })
      }
    }

    start()
  }, []) 

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden"
      style={{
        background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)',
      }}
    >
      {/* 배경 글로우 */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: 400,
          height: 400,
          borderRadius: '50%',
          background:
            'radial-gradient(circle, rgba(245,158,11,0.10) 0%, transparent 70%)',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      />

      {/* 로고 */}
      <div
        className="w-24 h-24 rounded-full flex items-center justify-center mb-5"
        style={{
          background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)',
          boxShadow: '0 0 48px rgba(245,158,11,0.30)',
          animation: 'fadeUp 0.5s ease both',
        }}
      >
        <span className="text-5xl">☕</span>
      </div>

      {/* 브랜드 */}
      <div
        className="text-center mb-14"
        style={{ animation: 'fadeUp 0.5s 0.1s ease both', opacity: 0 }}
      >
        <h1
          className="text-white font-black tracking-widest"
          style={{ fontSize: 28, letterSpacing: '0.25em' }}
        >
          BREW AI
        </h1>
        <p
          className="text-amber-400 font-medium mt-1"
          style={{ fontSize: 11, letterSpacing: '0.3em' }}
        >
          CAFÉ &amp; ROASTERY
        </p>
      </div>

      {/* 로딩 인디케이터 */}
      <div
        className="flex flex-col items-center gap-4"
        style={{ animation: 'fadeUp 0.5s 0.22s ease both', opacity: 0 }}
      >
        {/* 스피너 */}
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            border: '2px solid rgba(245,158,11,0.20)',
            borderTopColor: '#f59e0b',
            animation: 'spin 0.8s linear infinite',
          }}
        />

        {/* 도트 */}
        <div className="flex gap-1.5">
          {[0, 0.2, 0.4].map((delay, i) => (
            <div
              key={i}
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'rgba(245,158,11,0.50)',
                animation: `pulse 1.2s ${delay}s ease-in-out infinite`,
              }}
            />
          ))}
        </div>

        <p
          className="text-amber-600"
          style={{ fontSize: 13, letterSpacing: '0.05em' }}
        >
          잠시만 기다려 주세요...
        </p>
      </div>

      {/* 하단 개인정보 */}
      <p
        className="absolute bottom-5 text-center"
        style={{ fontSize: 11, color: 'rgba(120,60,20,0.55)', letterSpacing: '0.03em' }}
      >
        이미지는 즉시 삭제 · 개인정보 미저장
      </p>

      {/* 키프레임 */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}