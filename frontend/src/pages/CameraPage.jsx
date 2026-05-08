// 카메라 페이지 — 얼굴 촬영
// 사용자 개입 없이: 카메라 시작 → 안정화 대기 → 자동 5장 캡처 → AnalyzingPage 이동

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCamera } from '../hooks/useCamera'
import api from '../utils/api'
import { useLogger } from '../hooks/useLogger'

const STABILIZE_MS = 1200  // 카메라 안정화 대기 시간

export default function CameraPage() {
  const navigate = useNavigate()
  const { videoRef, error, startCamera, captureFrames, stopCamera } = useCamera()
  const sessionUuid = typeof window !== 'undefined' ? sessionStorage.getItem('session_uuid') : null
  const logger = useLogger(sessionUuid)

  const [phase, setPhase] = useState('starting')  // starting | scanning | capturing | error
  const [progress, setProgress] = useState(0)
  const [camError, setCamError] = useState(null)
  const didRun = useRef(false)

  const secureContext = typeof window !== 'undefined' ? window.isSecureContext : true
  const currentOrigin = typeof window !== 'undefined' ? window.location.origin : ''

  const runCapture = useCallback(async () => {
    try {
      // 카메라 시작
      setPhase('starting')
      await startCamera()

      // 카메라 안정화 대기 (노출·초점 자동 조정)
      setPhase('scanning')
      await new Promise((r) => setTimeout(r, STABILIZE_MS))

      // 자동 촬영 시작
      setPhase('capturing')
      setProgress(0)
      logger.log('camera', 'camera', {
        actionName: 'auto_capture_start',
        targetType: 'system',
        targetLabel: 'auto',
      })

      let sessionUuid = sessionStorage.getItem('session_uuid')
      if (!sessionUuid) {
        const sessionRes = await api.post('/api/v1/sessions')
        sessionUuid = sessionRes.data.session_uuid
        sessionStorage.setItem('session_uuid', sessionUuid)
      }

      // 진행 바 (200ms * 5장 = 1초)
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 20, 100))
      }, 200)

      const captureResult = await captureFrames(5, 200)
      clearInterval(progressInterval)
      setProgress(100)

      await new Promise((r) => setTimeout(r, 300))

      logger.log('camera', 'camera', {
        actionName: 'auto_capture_complete',
        payload: { frame_count: captureResult.frames?.length || 0 },
      })
      await logger.flush(sessionUuid)

      navigate('/analyzing', { state: { ...captureResult, sessionUuid } })
    } catch (err) {
      console.error('카메라/촬영 오류:', err)
      logger.log('camera', 'camera', {
        actionName: 'capture_error',
        payload: { message: err?.message || 'capture_failed' },
      })
      setCamError(err.message || '카메라를 시작할 수 없습니다.')
      setPhase('error')
    }
  }, [captureFrames, logger, navigate, startCamera])

  useEffect(() => {
    if (didRun.current) return
    didRun.current = true

    const enteredAt = Date.now()
    if (sessionUuid) logger.logScreenEnter('camera')

    runCapture()

    return () => {
      if (sessionUuid) logger.logScreenExit('camera', Date.now() - enteredAt)
      stopCamera()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRetry = useCallback(async () => {
    logger.log('click', 'camera', {
      actionName: 'camera_retry',
      targetType: 'button',
      targetLabel: 'camera_retry',
    })
    setCamError(null)
    stopCamera()
    didRun.current = false
    await runCapture()
  }, [logger, runCapture, stopCamera])

  // ── 에러 화면 ──────────────────────────────────────────────
  if (phase === 'error') {
    const errorMessage =
      camError ||
      (error === 'not_allowed'
        ? '카메라 권한이 거부되었습니다. 브라우저 설정에서 허용해주세요.'
        : error === 'not_found'
          ? '카메라를 찾을 수 없습니다. 장치 연결을 확인해주세요.'
          : error === 'not_readable'
            ? '카메라가 다른 앱에서 사용 중입니다.'
            : error === 'insecure_context'
              ? 'HTTPS 또는 localhost 환경에서만 사용할 수 있습니다.'
              : '카메라를 시작할 수 없습니다.')

    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center px-6"
        style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
      >
        <div className="text-5xl mb-6">📷</div>
        <p className="text-white text-xl font-bold mb-2 text-center">카메라를 사용할 수 없어요</p>
        <p className="text-amber-400/70 text-sm text-center mb-8 max-w-xs">{errorMessage}</p>

        <button
          onClick={handleRetry}
          className="w-full max-w-xs py-4 bg-amber-500 hover:bg-amber-600 text-white text-lg font-bold rounded-2xl mb-3 transition-colors"
        >
          다시 시도
        </button>
        <button
          onClick={() => navigate('/select-age')}
          className="w-full max-w-xs py-3 text-amber-400/60 hover:text-amber-400 text-sm transition-colors"
        >
          연령대 직접 선택하기
        </button>

        {import.meta.env.DEV && (
          <p className="mt-6 text-xs text-amber-900/50 font-mono">
            {currentOrigin} · 보안 컨텍스트: {secureContext ? 'yes' : 'no'}
          </p>
        )}
      </div>
    )
  }

  // ── 로딩/촬영 화면 ─────────────────────────────────────────
  const phaseLabel = {
    starting:  '카메라 시작 중...',
    scanning:  '얼굴을 인식하고 있어요',
    capturing: '촬영 중...',
  }[phase] ?? ''

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      {/* 배경 글로우 */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: 480,
          height: 480,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      />

      {/* 로고 (상단 소형) */}
      <div className="flex items-center gap-2 mb-6">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)' }}
        >
          <span className="text-base">☕</span>
        </div>
        <span className="text-white font-black tracking-widest text-sm">BREW AI</span>
      </div>

      {/* 카메라 원형 프리뷰 */}
      <div className="relative mb-6" style={{ width: 260, height: 260 }}>
        {/* 외부 회전 링 */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none"
          style={{
            border: '2px solid transparent',
            borderTopColor: '#f59e0b',
            borderRightColor: 'rgba(245,158,11,0.35)',
            animation: 'spin 1.5s linear infinite',
            zIndex: 10,
          }}
        />
        {/* 원형 클립 영역 */}
        <div
          className="absolute rounded-full overflow-hidden"
          style={{ inset: 6, background: '#000' }}
        >
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
            style={{ transform: 'scaleX(-1)' }}
          />
          {/* 촬영 중 플래시 오버레이 */}
          {phase === 'capturing' && (
            <div
              className="absolute inset-0"
              style={{ background: 'rgba(245,158,11,0.15)', animation: 'flash 0.2s ease-in-out infinite' }}
            />
          )}
        </div>
        {/* 얼굴 가이드 점선 원 */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            inset: 20,
            border: '1.5px dashed rgba(245,158,11,0.40)',
            zIndex: 10,
          }}
        />
        {/* starting 단계: 카메라 준비 중 오버레이 */}
        {phase === 'starting' && (
          <div
            className="absolute rounded-full flex items-center justify-center pointer-events-none"
            style={{ inset: 6, background: 'rgba(0,0,0,0.65)', zIndex: 11 }}
          >
            <div
              style={{
                width: 32, height: 32, borderRadius: '50%',
                border: '2px solid rgba(245,158,11,0.2)',
                borderTopColor: '#f59e0b',
                animation: 'spin 0.8s linear infinite',
              }}
            />
          </div>
        )}
      </div>

      {/* 상태 텍스트 */}
      <p className="text-white text-xl font-bold mb-2 text-center" style={{ minHeight: 28 }}>
        {phaseLabel}
      </p>
      <p className="text-amber-400/60 text-sm mb-8 text-center">
        {phase === 'scanning' ? '카메라 앞에 얼굴을 맞춰주세요' : '잠시만 기다려 주세요'}
      </p>

      {/* 진행 바 (capturing 단계에서만) */}
      {phase === 'capturing' && (
        <div className="w-48 bg-amber-900/30 rounded-full h-1.5 mb-8">
          <div
            className="bg-amber-400 h-1.5 rounded-full transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* 도트 인디케이터 (scanning 단계) */}
      {phase !== 'capturing' && (
        <div className="flex gap-2 mb-8">
          {[0, 0.2, 0.4].map((delay, i) => (
            <div
              key={i}
              style={{
                width: 6, height: 6, borderRadius: '50%',
                background: 'rgba(245,158,11,0.5)',
                animation: `pulse 1.2s ${delay}s ease-in-out infinite`,
              }}
            />
          ))}
        </div>
      )}

      {/* 하단 개인정보 안내 */}
      <p
        className="absolute bottom-5 text-center"
        style={{ fontSize: 11, color: 'rgba(120,60,20,0.5)', letterSpacing: '0.03em' }}
      >
        이미지는 즉시 삭제 · 개인정보 미저장
      </p>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.2} }
        @keyframes flash { 0%,100%{opacity:0.15} 50%{opacity:0.35} }
      `}</style>
    </div>
  )
}
