// 카메라 페이지 — 얼굴 촬영
// 웹캠 미리보기 + 가이드 오버레이 + 촬영 버튼

import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCamera } from '../hooks/useCamera'
import api from '../utils/api'
import { useLogger } from '../hooks/useLogger'

export default function CameraPage() {
  const navigate = useNavigate()
  const { videoRef, error, startCamera, captureFrames, stopCamera } = useCamera()
  const sessionUuid = typeof window !== 'undefined' ? sessionStorage.getItem('session_uuid') : null
  const logger = useLogger(sessionUuid)

  const [isCapturing, setIsCapturing] = useState(false)  // 촬영 중 상태
  const [progress, setProgress] = useState(0)            // 진행 바 (0~100)
  const [camError, setCamError] = useState(null)         // 카메라 에러 메시지

  const secureContext = typeof window !== 'undefined' ? window.isSecureContext : true
  const currentOrigin = typeof window !== 'undefined' ? window.location.origin : ''

  // 컴포넌트 마운트 시 카메라 시작
  useEffect(() => {
    const enteredAt = Date.now()
    if (sessionUuid) logger.logScreenEnter('camera')

    startCamera().catch((err) => {
      setCamError(err.message)
    })

    // 언마운트 시 카메라 정리
    return () => {
      if (sessionUuid) logger.logScreenExit('camera', Date.now() - enteredAt)
      stopCamera()
    }
  }, [logger, sessionUuid, startCamera, stopCamera])

  const handleRetryCamera = useCallback(async () => {
    logger.log('click', 'camera', {
      actionName: 'camera_retry',
      targetType: 'button',
      targetLabel: 'camera_retry',
    })
    setCamError(null)
    stopCamera()
    try {
      await startCamera()
    } catch (err) {
      setCamError(err.message)
    }
  }, [logger, startCamera, stopCamera])

  /**
   * 촬영 시작 — 5장 캡처 후 AnalyzingPage로 이동
   */
  const handleCapture = useCallback(async () => {
    if (isCapturing) return
    setIsCapturing(true)
    setProgress(0)
    logger.log('camera', 'camera', {
      actionName: 'capture_start',
      targetType: 'button',
      targetLabel: 'capture_start',
    })

    try {
      // session_uuid는 LandingPage에서 이미 발급됨
      let sessionUuid = sessionStorage.getItem('session_uuid')
      if (!sessionUuid) {
        const sessionRes = await api.post('/api/v1/sessions')
        sessionUuid = sessionRes.data.session_uuid
        sessionStorage.setItem('session_uuid', sessionUuid)
      }

      // 진행 바 애니메이션 (200ms * 5장 = 1초)
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 20, 100))
      }, 200)

      // 5장 캡처 + AES-256-GCM 암호화 (또는 평문 모드)
      const captureResult = await captureFrames(5, 200)

      clearInterval(progressInterval)
      setProgress(100)
      await new Promise((r) => setTimeout(r, 300))
      logger.log('camera', 'camera', {
        actionName: 'capture_complete',
        payload: { frame_count: captureResult.frames?.length || 0 },
      })
      await logger.flush(sessionUuid)

      navigate('/analyzing', { state: { ...captureResult, sessionUuid } })
    } catch (err) {
      console.error('촬영 오류:', err)
      logger.log('camera', 'camera', {
        actionName: 'capture_error',
        payload: { message: err?.message || 'capture_failed' },
      })
      setCamError('촬영 중 오류가 발생했습니다. 다시 시도해주세요.')
      setIsCapturing(false)
      setProgress(0)
    }
  }, [captureFrames, isCapturing, logger, navigate])

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center">
      {/* 상단 안내 텍스트 */}
      <p className="text-white text-lg md:text-xl mb-6 font-medium">
        얼굴을 원 안에 맞춰주세요
      </p>

      {/* 카메라 + 오버레이 컨테이너 */}
      <div className="relative">
        {/* 웹캠 비디오 */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-[320px] h-[320px] md:w-[400px] md:h-[400px] object-cover rounded-full"
          style={{ transform: 'scaleX(-1)' }} // 거울 반전 (셀카 방향)
        />

        {/* 얼굴 가이드 원형 테두리 오버레이 */}
        <div
          className="absolute inset-0 rounded-full border-4 border-amber-400 pointer-events-none"
          style={{
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.6)',
          }}
        />

        {/* 촬영 중 오버레이 */}
        {isCapturing && (
          <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black bg-opacity-30">
            <div className="text-white text-4xl">📸</div>
          </div>
        )}
      </div>

      {/* 진행 바 */}
      {isCapturing && (
        <div className="mt-6 w-64 bg-gray-700 rounded-full h-2">
          <div
            className="bg-amber-400 h-2 rounded-full transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* 에러 메시지 */}
      {(camError || error) && (
        <div className="mt-4 flex flex-col items-center gap-2">
          <div className="px-4 py-3 bg-red-900 text-red-200 rounded-xl text-sm text-center max-w-xs">
            {camError || (
              error === 'not_allowed'
                ? '카메라 권한이 거부되었습니다. 브라우저 설정에서 허용해주세요.'
                : error === 'not_found'
                  ? '카메라를 찾을 수 없습니다. 장치 연결을 확인해주세요.'
                  : error === 'not_readable'
                    ? '카메라가 다른 앱에서 사용 중입니다. 다른 앱을 종료 후 다시 시도해주세요.'
                    : error === 'insecure_context'
                      ? 'HTTPS 또는 localhost 환경에서만 카메라를 사용할 수 있습니다.'
                      : '카메라 초기화 중 알 수 없는 오류가 발생했습니다.'
            )}
          </div>

          <button
            onClick={handleRetryCamera}
            disabled={isCapturing}
            className="text-sm px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-60"
          >
            카메라 다시 연결
          </button>

          <div className="text-xs text-gray-400 text-center">
            <div>접속 주소: {currentOrigin}</div>
            <div>보안 컨텍스트: {secureContext ? '예' : '아니오'}</div>
          </div>
        </div>
      )}

      {/* 촬영 시작 버튼 */}
      <button
        onClick={handleCapture}
        disabled={isCapturing || !!error}
        className="
          mt-8 min-h-[56px] px-12 py-4
          bg-amber-500 hover:bg-amber-600 active:bg-amber-700
          disabled:bg-gray-600 disabled:cursor-not-allowed
          text-white text-lg font-bold
          rounded-2xl shadow-lg
          transition-colors duration-150
          w-64
        "
      >
        {isCapturing ? '촬영 중...' : '촬영 시작'}
      </button>

      {/* 뒤로가기 */}
      <button
        onClick={async () => {
          logger.log('navigation', 'camera', {
            actionName: 'back_home',
            targetType: 'button',
            targetLabel: 'home',
          })
          await logger.flush()
          navigate('/')
        }}
        disabled={isCapturing}
        className="mt-4 text-gray-400 hover:text-gray-200 text-sm py-2 px-4"
      >
        ← 돌아가기
      </button>
    </div>
  )
}
