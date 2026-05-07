// 중장년 결제 완료 페이지
// 스탬프 카드 시각화, 주차 등록 팝업, 영수증 선택, 설문 버튼
import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const TOTAL_STAMPS = 10
const REWARD_STAMP = 10

function getSimulatedStamps() {
  return parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
}

// 숫자 키패드
function NumPad({ value, onChange, maxLength = 9 }) {
  const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫']
  return (
    <div className="grid grid-cols-3 gap-2 mt-4">
      {keys.map((key, i) => (
        <button
          key={i}
          onClick={() => {
            if (key === '⌫') onChange(value.slice(0, -1))
            else if (key === '') return
            else if (value.length < maxLength) onChange(value + key)
          }}
          disabled={key === ''}
          className={`h-12 rounded-xl text-xl font-bold transition-all
            ${key === '' ? 'invisible' : 'hover:opacity-80 active:scale-95'}
            ${key === '⌫' ? 'text-red-400' : 'text-gray-700'}`}
          style={{ background: key === '' ? 'transparent' : '#fff3ec', border: '1px solid #fde8d8' }}
        >
          {key}
        </button>
      ))}
    </div>
  )
}

export default function MiddleCompletePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { paymentMethod, totalPrice, totalCount, isMembership, orderUuid, discount, originalPrice } = location.state || {}

  const [orderNum] = useState(() => Math.floor(Math.random() * 900 + 100))
  const [countdown, setCountdown] = useState(30)
  const [showStampAnim, setShowStampAnim] = useState(false)

  // 주차 팝업
  const [showParkingPopup, setShowParkingPopup] = useState(false)
  const [parkingDone, setParkingDone] = useState(false)
  const [carNumber, setCarNumber] = useState('')
  const [parkingToast, setParkingToast] = useState(false)

  // 스탬프 계산
  const prevStamps = getSimulatedStamps()
  const earnedStamps = isMembership ? 2 : 1
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + earnedStamps)
  const isReward = newStamps >= TOTAL_STAMPS

  // 영수증 상태 추가
  const [showReceiptPopup, setShowReceiptPopup] = useState(false)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('completion', {
        payment_method: paymentMethod,
        total_price: totalPrice,
      })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('completion', Date.now() - enteredAt)
    }
  }, [logger, paymentMethod, state.sessionUuid, totalPrice])

  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return
      try {
        logger.log('session', 'completion', { actionName: 'session_complete', source: 'system' })
        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, {
          status: 'ended',
          end_reason: 'completed',
        })
        await logger.flush()
      } catch (err) {
        console.warn('세션 종료 실패 (무시):', err.message)
      }
    }
    endSession()
  }, []) 

  useEffect(() => {
    sessionStorage.setItem('stamp_count', String(isReward ? 0 : newStamps))
    const t = setTimeout(() => setShowStampAnim(true), 400)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timer); handleGoHome(); return 0 }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, []) 

  const handleGoHome = async () => {
    logger.log('navigation', 'completion', { actionName: 'go_home', targetType: 'button', targetLabel: 'home' })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleParkingConfirm = () => {
    if (carNumber.length < 4) return
    logger.log('click', 'completion', { actionName: 'parking_register', targetType: 'button', targetLabel: 'parking_register' })
    setParkingDone(true)
    setShowParkingPopup(false)
    setCarNumber('')
    setParkingToast(true)
    setTimeout(() => setParkingToast(false), 3000)
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#fdf6f0' }}>

      {/* 상단 성공 배너 */}
      <div className="px-4 pt-12 pb-8 text-center text-white" style={{ background: '#f4a261' }}>
        <div className="text-5xl mb-3">✅</div>
        <h1 className="text-2xl font-black mb-1">결제 완료!</h1>

        {/* 할인 적용 시 */}
        {discount ? (
          <div>
            <p className="line-through text-sm opacity-70">
              {originalPrice?.toLocaleString()}원
            </p>
            <p className="text-xl font-black">
              {totalPrice?.toLocaleString()}원
              <span className="text-sm ml-1 opacity-80">({discount * 100}% 할인 적용)</span>
            </p>
          </div>
        ) : (
          <p className="text-sm opacity-80">
            {paymentMethod}으로 {totalPrice?.toLocaleString()}원 결제되었어요
          </p>
        )}

        <div className="mt-3 inline-block rounded-full px-4 py-1.5" style={{ background: 'rgba(255,255,255,0.2)' }}>
          <span className="text-sm font-bold">주문번호 #{orderNum}</span>
        </div>
      </div>

      <div className="flex-1 px-4 py-5 space-y-4">

        {/* 스탬프 카드 */}
        <div className="rounded-2xl shadow-sm overflow-hidden" style={{ background: '#fff', border: '1px solid #fde8d8' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#fde8d8', background: '#fff8f3' }}>
            <div>
              <p className="font-bold" style={{ color: '#374151' }}>스탬프 카드</p>
              <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>
                {isReward ? '🎉 무료 음료 적립 완료!' : `${REWARD_STAMP - newStamps}개 더 모으면 무료 음료`}
              </p>
            </div>
            {isMembership && (
              <span className="text-xs font-bold px-2 py-1 rounded-full" style={{ background: '#ede9fe', color: '#7c3aed' }}>
                멤버십 2배
              </span>
            )}
          </div>
          <div className="px-4 py-5">
            <div className="grid grid-cols-5 gap-2 mb-4">
              {Array.from({ length: TOTAL_STAMPS }).map((_, i) => {
                const isNew = i >= prevStamps && i < newStamps
                const isFilled = i < newStamps
                return (
                  <div
                    key={i}
                    className="aspect-square rounded-full border-2 flex items-center justify-center text-lg transition-all duration-500"
                    style={{
                      borderColor: isFilled ? '#f4a261' : '#fde8d8',
                      background: isFilled
                        ? isNew && showStampAnim ? '#f4a261' : '#fbbf7a'
                        : '#fff8f3',
                      transform: isNew && showStampAnim ? 'scale(1.1)' : 'scale(1)',
                      transitionDelay: isNew ? `${(i - prevStamps) * 150}ms` : '0ms',
                    }}
                  >
                    {isFilled ? (
                      <span className={isNew && showStampAnim ? 'animate-bounce' : ''}>☕</span>
                    ) : (
                      <span className="text-xs" style={{ color: '#fde8d8' }}>{i + 1}</span>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="rounded-xl px-4 py-2.5 flex items-center gap-2" style={{ background: '#fff3ec' }}>
              <span className="text-lg">🎁</span>
              <div>
                <p className="text-sm font-bold" style={{ color: '#c2703a' }}>
                  {earnedStamps}개 적립 완료
                  {isMembership && <span className="ml-1" style={{ color: '#7c3aed' }}>(멤버십 2배!)</span>}
                </p>
                <p className="text-xs" style={{ color: '#f4a261' }}>
                  현재 {newStamps} / {TOTAL_STAMPS} 스탬프
                  {isReward && ' · 다음 방문 시 무료 음료!'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 주차 등록 */}
        <div className="rounded-2xl shadow-sm overflow-hidden" style={{ background: '#fff', border: '1px solid #fde8d8' }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: '#fde8d8', background: '#fff8f3' }}>
            <p className="font-bold" style={{ color: '#374151' }}>주차 등록</p>
            <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>구매 시 1시간 무료 주차</p>
          </div>
          <div className="px-4 py-4">
            {parkingDone ? (
              <div className="flex items-center gap-3 rounded-xl px-4 py-3" style={{ background: '#f0fdf4' }}>
                <span className="text-2xl">✅</span>
                <div>
                  <p className="font-bold" style={{ color: '#15803d' }}>주차 등록 완료</p>
                  <p className="text-xs" style={{ color: '#16a34a' }}>1시간 무료 주차가 적용되었습니다</p>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowParkingPopup(true)}
                className="w-full py-4 rounded-xl border-2 border-dashed transition-all flex items-center justify-center gap-3 font-semibold"
                style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
              >
                <span className="text-2xl">🚗</span>
                <div className="text-left">
                  <p className="font-bold">주차 등록하기</p>
                  <p className="text-xs font-normal opacity-70">차량 번호 직접 입력</p>
                </div>
              </button>
            )}
          </div>
        </div>

        {/* 영수증 + 설문 */}
        <div className="flex gap-3">
          <button
            onClick={() => setShowReceiptPopup(true)}
            className="flex-1 rounded-2xl py-3 flex flex-col items-center gap-1 transition-colors hover:opacity-80"
            style={{ background: '#fff', border: '1px solid #fde8d8', color: '#6b7280' }}
          >
            <span className="text-xl">🧾</span>
            <span className="text-xs font-medium">영수증</span>
          </button>
          <button
            onClick={() => navigate('/survey')}
            className="flex-1 rounded-2xl py-3 flex flex-col items-center gap-1 transition-colors hover:opacity-80"
            style={{ background: '#fff3ec', border: '1px solid #f4a261', color: '#c2703a' }}
          >
            <span className="text-xl">📝</span>
            <span className="text-xs font-medium">설문 참여하기</span>
          </button>
        </div>
      </div>

      {/* 하단 홈으로 버튼 */}
      <div className="px-4 pb-8 pt-2">
        <button
          onClick={handleGoHome}
          className="w-full py-4 text-white font-bold text-lg rounded-2xl transition-colors"
          style={{ background: '#f4a261' }}
        >
          처음으로 돌아가기
        </button>
        <p className="text-center text-xs mt-2" style={{ color: '#9ca3af' }}>
          {countdown}초 후 자동으로 처음 화면으로 이동합니다
        </p>
      </div>

      {/* 주차 등록 팝업 */}
      {showParkingPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowParkingPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-6"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-black mb-1" style={{ color: '#374151' }}>주차 등록</h2>
            <p className="text-sm mb-4" style={{ color: '#9ca3af' }}>차량 번호를 입력해 주세요</p>

            <div className="rounded-2xl px-4 py-4 text-center mb-2" style={{ background: '#fff3ec' }}>
              <p className="text-2xl font-black tracking-widest" style={{ color: '#374151' }}>
                {carNumber || '차량 번호 입력'}
              </p>
            </div>

            <NumPad value={carNumber} onChange={setCarNumber} maxLength={9} />

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => { setShowParkingPopup(false); setCarNumber('') }}
                className="flex-1 py-3 rounded-2xl border-2 font-bold"
                style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
              >
                취소
              </button>
              <button
                onClick={handleParkingConfirm}
                disabled={carNumber.length < 4}
                className="flex-1 py-3 rounded-2xl font-bold text-white transition-colors"
                style={{
                  background: carNumber.length >= 4 ? '#f4a261' : '#e5e7eb',
                  color: carNumber.length >= 4 ? '#fff' : '#9ca3af',
                }}
              >
                등록
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 영수증 팝업 */}
      {showReceiptPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowReceiptPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-8 text-center"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-5xl mb-4 animate-bounce">🖨️</div>
            <h2 className="text-xl font-black mb-2" style={{ color: '#374151' }}>영수증 출력 중</h2>
            <p className="text-sm mb-6" style={{ color: '#9ca3af' }}>
              영수증이 출력되고 있습니다.<br />잠시만 기다려 주세요.
            </p>
            <button
              onClick={() => setShowReceiptPopup(false)}
              className="w-full py-3 rounded-2xl font-bold text-white"
              style={{ background: '#f4a261' }}
            >
              확인
            </button>
          </div>
        </div>
      )}

      {/* 주차 완료 토스트 */}
      {parkingToast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-2 z-50 animate-bounce"
          style={{ background: '#16a34a' }}>
          <span>🚗</span>
          <span className="font-bold text-sm">주차 등록 완료! 1시간 무료</span>
        </div>
      )}
    </div>
  )
}