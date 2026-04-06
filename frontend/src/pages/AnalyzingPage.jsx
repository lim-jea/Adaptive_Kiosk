// 분석 페이지 — POST /api/v1/face/analyze 호출 + 로딩 화면

import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

export default function AnalyzingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { dispatch, ACTIONS } = useSession()

  // CameraPage에서 전달된 데이터
  const { frames, sessionUuid } = location.state || {}

  const [error, setError] = useState(null)
  const [dots, setDots] = useState('')

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'))
    }, 500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!frames || !sessionUuid) {
      navigate('/', { replace: true })
      return
    }

    const analyze = async () => {
      try {
        const response = await api.post('/api/v1/face/analyze', {
          session_uuid: sessionUuid,
          frames,
        })

        const {
          age_group,
          gender,
          age_est,
          should_use_simple_mode,
        } = response.data

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
        const message = err.response?.data?.error?.message
            || err.response?.data?.detail
            || '분석 중 오류가 발생했습니다.'
        setError(message)
        console.error('얼굴 분석 실패:', err)
      }
    }

    analyze()
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
