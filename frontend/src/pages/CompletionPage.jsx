// 결제 완료 페이지 — 스탬프 적립 + 주차 등록 + 카운트다운
import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

// 스탬프 카드 시뮬레이션 (실제 DB 연동은 추후)
const TOTAL_STAMPS = 10
const REWARD_STAMP = 10  // 10개 모이면 무료 음료

function getSimulatedStamps() {
  // 세션스토리지에서 누적 스탬프 수 가져오기 (새로고침해도 유지)
  const saved = parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
  return saved
}

export default function CompletionPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()

  const { paymentMethod, totalPrice, isMembership } = location.state || {}

  // 마운트 시 세션을 ended 상태로 PATCH (한 번만)
  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return
      try {
        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, {
          status: 'ended',
          end_reason: 'completed',
        })
      } catch (err) {
        console.warn('세션 종료 실패 (무시):', err.message)
      }
    }
    endSession()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [countdown, setCountdown] = useState(30)
  const [parkingDone, setParkingDone] = useState(false)
  const [parkingToast, setParkingToast] = useState(false)
  const [showStampAnim, setShowStampAnim] = useState(false)

  // 스탬프 계산
  const prevStamps = getSimulatedStamps()
  const earnedStamps = isMembership ? 2 : 1
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + earnedStamps)
  const isReward = newStamps >= TOTAL_STAMPS

  // 주문 번호 (랜덤 3자리)
  const [orderNum] = useState(() => Math.floor(Math.random() * 900 + 100))

  useEffect(() => {
    // 스탬프 업데이트
    sessionStorage.setItem('stamp_count', String(isReward ? 0 : newStamps))
    // 스탬프 애니메이션
    const t = setTimeout(() => setShowStampAnim(true), 400)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 30초 카운트다운 → 홈
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(timer)
          handleGoHome()
          return 0
        }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoHome = () => {
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleParking = () => {
    if (parkingDone) return
    setParkingDone(true)
    setParkingToast(true)
    setTimeout(() => setParkingToast(false), 3000)
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col">
      {/* 상단 성공 배너 */}
      <div className="bg-amber-500 px-4 pt-12 pb-8 text-center text-white">
        <div className="text-5xl mb-3">✅</div>
        <h1 className="text-2xl font-black mb-1">결제 완료!</h1>
        <p className="text-amber-100 text-sm">
          {paymentMethod}으로 {totalPrice?.toLocaleString()}원 결제되었어요
        </p>
        <div className="mt-3 inline-block bg-white/20 rounded-full px-4 py-1.5">
          <span className="text-sm font-bold">주문번호 #{orderNum}</span>
        </div>
      </div>

      <div className="flex-1 px-4 py-5 space-y-4">

        {/* 스탬프 카드 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <div>
              <p className="font-bold text-gray-800">스탬프 카드</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {isReward
                  ? '🎉 무료 음료 적립 완료!'
                  : `${REWARD_STAMP - newStamps}개 더 모으면 무료 음료`}
              </p>
            </div>
            {isMembership && (
              <span className="bg-purple-100 text-purple-700 text-xs font-bold px-2 py-1 rounded-full">
                멤버십 2배
              </span>
            )}
          </div>
          <div className="px-4 py-5">
            {/* 스탬프 그리드 */}
            <div className="grid grid-cols-5 gap-2 mb-4">
              {Array.from({ length: TOTAL_STAMPS }).map((_, i) => {
                const wasFilled = i < prevStamps
                const isNew = i >= prevStamps && i < newStamps
                const isFilled = i < newStamps

                return (
                  <div
                    key={i}
                    className={`
                      aspect-square rounded-full border-2 flex items-center justify-center text-lg
                      transition-all duration-500
                      ${isFilled
                        ? isNew && showStampAnim
                          ? 'border-amber-500 bg-amber-500 scale-110 shadow-lg shadow-amber-200'
                          : 'border-amber-400 bg-amber-400'
                        : 'border-gray-200 bg-gray-50'}
                    `}
                    style={{
                      transitionDelay: isNew ? `${(i - prevStamps) * 150}ms` : '0ms',
                    }}
                  >
                    {isFilled ? (
                      <span className={isNew && showStampAnim ? 'animate-bounce' : ''}>☕</span>
                    ) : (
                      <span className="text-gray-300 text-xs">{i + 1}</span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* 적립 안내 */}
            <div className="bg-amber-50 rounded-xl px-4 py-2.5 flex items-center gap-2">
              <span className="text-lg">🎁</span>
              <div>
                <p className="text-sm font-bold text-amber-800">
                  {earnedStamps}개 적립 완료
                  {isMembership && <span className="text-purple-600 ml-1">(멤버십 2배!)</span>}
                </p>
                <p className="text-xs text-amber-600">
                  현재 {newStamps} / {TOTAL_STAMPS} 스탬프
                  {isReward && ' · 다음 방문 시 무료 음료!'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 주차 등록 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-4 py-3 border-b">
            <p className="font-bold text-gray-800">주차 등록</p>
            <p className="text-xs text-gray-400 mt-0.5">구매 시 1시간 무료 주차</p>
          </div>
          <div className="px-4 py-4">
            {parkingDone ? (
              <div className="flex items-center gap-3 bg-green-50 rounded-xl px-4 py-3">
                <span className="text-2xl">✅</span>
                <div>
                  <p className="font-bold text-green-700">주차 등록 완료</p>
                  <p className="text-xs text-green-500">1시간 무료 주차가 적용되었습니다</p>
                </div>
              </div>
            ) : (
              <button
                onClick={handleParking}
                className="w-full py-4 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-amber-400 hover:text-amber-600 hover:bg-amber-50 transition-all flex items-center justify-center gap-3 font-semibold"
              >
                <span className="text-2xl">🚗</span>
                <div className="text-left">
                  <p className="font-bold">주차 등록하기</p>
                  <p className="text-xs font-normal opacity-70">차량 번호판 자동 인식</p>
                </div>
              </button>
            )}
          </div>
        </div>

        {/* 영수증 / 영양정보 (장식용) */}
        <div className="flex gap-3">
          <button className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm py-3 flex flex-col items-center gap-1 text-gray-500 hover:bg-gray-50 transition-colors">
            <span className="text-xl">🧾</span>
            <span className="text-xs font-medium">영수증</span>
          </button>
          <button className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm py-3 flex flex-col items-center gap-1 text-gray-500 hover:bg-gray-50 transition-colors">
            <span className="text-xl">🍃</span>
            <span className="text-xs font-medium">영양정보</span>
          </button>
          <button className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm py-3 flex flex-col items-center gap-1 text-gray-500 hover:bg-gray-50 transition-colors">
            <span className="text-xl">⭐</span>
            <span className="text-xs font-medium">리뷰 작성</span>
          </button>
        </div>
      </div>

      {/* 하단 홈으로 버튼 + 카운트다운 */}
      <div className="px-4 pb-8 pt-2">
        <button
          onClick={handleGoHome}
          className="w-full py-4 bg-amber-500 hover:bg-amber-600 text-white font-bold text-lg rounded-2xl transition-colors"
        >
          처음으로 돌아가기
        </button>
        <p className="text-center text-xs text-gray-400 mt-2">
          {countdown}초 후 자동으로 처음 화면으로 이동합니다
        </p>
      </div>

      {/* 주차 완료 토스트 */}
      {parkingToast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 bg-green-600 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-2 z-50 animate-bounce">
          <span>🚗</span>
          <span className="font-bold text-sm">주차 등록 완료! 1시간 무료</span>
        </div>
      )}
    </div>
  )
}
