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

  // CameraPage에서 전달된 데이터
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

        // 백엔드 "중장년" → 프론트 통일 레이블 "중년"으로 정규화
        const age_group = raw_age_group === '중장년' ? '중년' : raw_age_group

        // 전역 상태에 비전 결과 저장
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
          payload: {
            age_group,
            gender,
            age_est,
            should_use_simple_mode,
          },
        })
        logger.logScreenExit('analyzing', Date.now() - enteredAt, {
          reason: 'analysis_complete',
        })
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
        const message = err.response?.data?.error?.message
            || err.response?.data?.detail
            || '분석 중 오류가 발생했습니다.'
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
      if (sessionUuid) {
        logger.logScreenExit('analyzing', Date.now() - enteredAt)
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">
      {error ? (
        <div className="text-center">
          <div className="text-5xl mb-6">😔</div>
          <p className="text-xl font-semibold text-gray-800 mb-2">분석에 실패했습니다</p>
          <p className="text-gray-500 mb-8 text-sm">{error}</p>
          <button
            onClick={() => navigate('/camera')}
            className="min-h-[56px] px-10 py-4 bg-amber-500 hover:bg-amber-600 text-white text-lg font-bold rounded-2xl shadow-md transition-colors duration-150"
          >
            다시 시도
          </button>
          <button
            onClick={() => navigate('/')}
            className="block mt-4 text-gray-400 hover:text-gray-600 text-sm mx-auto py-2"
          >
            처음으로
          </button>
        </div>
      ) : (
        <div className="text-center">
          <div className="mb-8 relative">
            <div className="w-24 h-24 border-4 border-amber-200 border-t-amber-500 rounded-full animate-spin mx-auto" />
            <div className="absolute inset-0 flex items-center justify-center text-3xl">☕</div>
          </div>
          <p className="text-xl md:text-2xl font-semibold text-amber-900 mb-2">
            잠시만 기다려 주세요{dots}
          </p>
          <p className="text-gray-500 text-sm">AI가 맞춤 메뉴를 분석하고 있습니다</p>
        </div>
      )}
    </div>
  )
}
