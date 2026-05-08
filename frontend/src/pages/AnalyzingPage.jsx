// 분석 페이지 — POST /api/v1/face/analyze 호출 + 로딩 화면

import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

export default function AnalyzingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { dispatch, ACTIONS } = useSession()

  const { frames, sessionUuid } = location.state || {}
  const logger = useLogger(sessionUuid)

  const [error, setError] = useState(null)
  const [dots, setDots] = useState('')

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'))
    }, 500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const enteredAt = Date.now()
    if (sessionUuid) logger.logScreenEnter('analyzing')

    if (!frames || !sessionUuid) {
      navigate('/', { replace: true })
      return
    }

    const analyze = async () => {
      const startedAt = performance.now()
      try {
        logger.log('vision', 'analyzing', {
          actionName: 'face_analysis_start',
          source: 'system',
          payload: { frame_count: frames.length },
        })

        const response = await api.post('/api/v1/face/analyze', {
          session_uuid: sessionUuid,
          frames,
        })
        logClientTiming('analyzing.faceAnalyze', performance.now() - startedAt, {
          frame_count: frames.length,
        })

        const {
          age_group: raw_age_group,
          gender,
          age_est,
          should_use_simple_mode,
        } = response.data

        const age_group = raw_age_group === '중장년' ? '중년' : raw_age_group

        dispatch({
          type: ACTIONS.SET_VISION,
          payload: {
            ageGroup: age_group,
            gender,
            ageEst: age_est,
            isSimpleMode: should_use_simple_mode,
          },
        })

        logger.log('vision', 'analyzing', {
          actionName: 'face_analysis_complete',
          source: 'system',
          payload: { age_group, gender, age_est, should_use_simple_mode },
        })
        logger.logScreenExit('analyzing', Date.now() - enteredAt, { reason: 'analysis_complete' })

        const flushStartedAt = performance.now()
        await logger.flush()
        logClientTiming('analyzing.loggerFlush', performance.now() - flushStartedAt, {
          session_uuid: sessionUuid,
        })

        navigate('/result', {
          replace: true,
          state: {
            age_group,
            gender,
            age_est,
            should_use_simple_mode,
            sessionUuid,
          },
        })
      } catch (err) {
        logClientTiming('analyzing.faceAnalyze.error', performance.now() - startedAt, {
          frame_count: frames.length,
        })
        const message =
          err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          '분석 중 오류가 발생했습니다.'
        setError(message)
        console.error('얼굴 분석 실패:', err)
        logger.log('vision', 'analyzing', {
          actionName: 'face_analysis_error',
          source: 'system',
          payload: { message },
        })
      }
    }

    analyze()
    return () => {
      if (sessionUuid) logger.logScreenExit('analyzing', Date.now() - enteredAt)
    }
  }, []) 

  // ── 에러 화면 ──────────────────────────────────────────────
  if (error) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center px-6"
        style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
      >
        <div className="text-5xl mb-6">😔</div>
        <p className="text-white text-xl font-bold mb-2 text-center">분석에 실패했습니다</p>
        <p className="text-amber-400/70 text-sm text-center mb-8 max-w-xs">{error}</p>

        <button
          onClick={() => navigate('/camera', { replace: true })}
          className="w-full max-w-xs py-4 bg-amber-500 hover:bg-amber-600 text-white text-lg font-bold rounded-2xl mb-3 transition-colors"
        >
          다시 시도
        </button>
        <button
          onClick={() => navigate('/select-age', { replace: true })}
          className="w-full max-w-xs py-3 text-amber-400/60 hover:text-amber-400 text-sm transition-colors"
        >
          연령대 직접 선택하기
        </button>
      </div>
    )
  }

  // ── 분석 중 화면 ───────────────────────────────────────────
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      {/* 배경 글로우 */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: 400,
          height: 400,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      />

      {/* 로고 */}
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-8 relative"
        style={{
          background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)',
          boxShadow: '0 0 40px rgba(245,158,11,0.25)',
        }}
      >
        <div
          className="absolute inset-0 rounded-full"
          style={{
            border: '2px solid transparent',
            borderTopColor: 'rgba(255,255,255,0.6)',
            animation: 'spin 1s linear infinite',
          }}
        />
        <span className="text-4xl relative z-10">☕</span>
      </div>

      <p className="text-white text-xl font-bold mb-2 text-center">
        AI가 분석 중이에요{dots}
      </p>
      <p className="text-amber-400/60 text-sm text-center">맞춤 메뉴를 준비하고 있습니다</p>

      <p
        className="absolute bottom-5 text-center"
        style={{ fontSize: 11, color: 'rgba(120,60,20,0.50)', letterSpacing: '0.03em' }}
      >
        이미지는 즉시 삭제 · 개인정보 미저장
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}