// 랜딩 페이지 — 키오스크 시작 화면
// "시작하기" 버튼 클릭 시 세션 시작(X-API-Key) + 카메라 권한 요청 → CameraPage 이동

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

export default function LandingPage() {
  const navigate = useNavigate()
  const { dispatch, ACTIONS } = useSession()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleStart = async () => {
    setLoading(true)
    setError(null)

    try {
      // 세션 생성 (X-API-Key는 axios 인터셉터에서 자동 첨부)
      const sessionRes = await api.post('/api/v1/sessions')
      const { session_uuid } = sessionRes.data

      dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid: session_uuid } })
      sessionStorage.setItem('session_uuid', session_uuid)

      // 카메라 권한 사전 요청
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      })
      // 권한 확인 후 스트림 즉시 정리 (CameraPage에서 다시 시작)
      stream.getTracks().forEach((t) => t.stop())

      navigate('/camera')
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('카메라 권한이 필요합니다. 브라우저 설정에서 카메라 접근을 허용해주세요.')
      } else if (err.name === 'NotFoundError') {
        setError('카메라를 찾을 수 없습니다. 카메라가 연결되어 있는지 확인해주세요.')
      } else {
        setError('카메라를 시작할 수 없습니다. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">
      {/* 카페 로고 영역 */}
      <div className="mb-10 text-center">
        <div className="text-6xl mb-4">☕</div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-amber-900">
          Cafe AI Kiosk
        </h1>
        <div className="mt-1 h-1 w-24 bg-amber-500 mx-auto rounded-full" />
      </div>

      {/* 메인 문구 */}
      <p className="text-lg md:text-xl lg:text-2xl text-amber-800 text-center mb-2 font-medium">
        AI가 당신에게 맞는
      </p>
      <p className="text-lg md:text-xl lg:text-2xl text-amber-800 text-center mb-10 font-medium">
        메뉴를 추천해드립니다
      </p>

      {/* 안내 문구 */}
      <p className="text-sm md:text-base text-amber-600 text-center mb-8 max-w-sm">
        얼굴을 1초 동안 촬영하여 연령대와 성별을 분석합니다.
        <br />
        이미지는 분석 후 즉시 삭제됩니다.
      </p>

      {/* 에러 메시지 */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-100 border border-red-300 text-red-700 rounded-xl text-sm text-center max-w-sm">
          {error}
        </div>
      )}

      {/* 시작하기 버튼 — 터치 친화적 최소 48px */}
      <button
        onClick={handleStart}
        disabled={loading}
        className="
          min-h-[56px] px-12 py-4
          bg-amber-500 hover:bg-amber-600 active:bg-amber-700
          disabled:bg-amber-300
          text-white text-lg md:text-xl font-bold
          rounded-2xl shadow-lg
          transition-colors duration-150
          w-full max-w-xs
        "
      >
        {loading ? '카메라 시작 중...' : '시작하기'}
      </button>

      {/* 하단 안내 */}
      <p className="mt-8 text-xs text-amber-500 text-center">
        이 서비스는 개인정보를 저장하지 않습니다
      </p>
    </div>
  )
}
