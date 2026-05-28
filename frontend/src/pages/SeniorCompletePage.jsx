// 시니어 결제 완료 페이지 — 주문번호, 주차/스탬프 팝업, 설문 버튼
import { useEffect, useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { useTTS } from '../hooks/useTTS'

const TOTAL_STAMPS = 10

function getSimulatedStamps() {
  return parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
}

// 숫자 키패드 컴포넌트
function NumPad({ value, onChange, maxLength = 11 }) {
  const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫']
  return (
    <div className="grid grid-cols-3 gap-2 mt-4">
      {keys.map((key, i) => (
        <button
          key={i}
          onClick={() => {
            if (key === '⌫') {
              onChange(value.slice(0, -1))
            } else if (key === '') {
              // 빈 자리
            } else if (value.length < maxLength) {
              onChange(value + key)
            }
          }}
          disabled={key === ''}
          className={`h-14 rounded-2xl text-2xl font-bold transition-all
            ${key === '' ? 'invisible' : 'bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-800'}
            ${key === '⌫' ? 'text-red-500' : ''}`}
        >
          {key}
        </button>
      ))}
    </div>
  )
}

export default function SeniorCompletePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)
  const tts = useTTS({ rate: 0.65 })
  const ttsCalledRef = useRef(false)

  const { paymentMethod, totalPrice, totalCount, isMembership } = location.state || {}

  const [orderNum] = useState(() => Math.floor(Math.random() * 900 + 100))
  const [toast, setToast] = useState(null)

  // 주차 등록 상태
  const [parkingDone, setParkingDone] = useState(false)
  const [showParkingPopup, setShowParkingPopup] = useState(false)
  const [carNumber, setCarNumber] = useState('')
  
  // 스탬프 상태
  const [stampDone, setStampDone] = useState(false)
  const [showStampPopup, setShowStampPopup] = useState(false)
  const [stampMethod, setStampMethod] = useState(null) // null | 'phone' | 'card'
  const [phoneNumber, setPhoneNumber] = useState('')
  
  const prevStamps = getSimulatedStamps()
  const earnedStamps = isMembership ? 2 : 1
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + earnedStamps)
  const isReward = newStamps >= TOTAL_STAMPS

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
        tts.cancel()
    }
  }, [logger, paymentMethod, state.sessionUuid, totalPrice])

  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return
      try {
        logger.log('session', 'completion', {
          actionName: 'session_complete',
          source: 'system',
        })
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
    if (ttsCalledRef.current) return
    ttsCalledRef.current = true
    tts.speak(`결제가 완료되었습니다. 주문번호는 ${orderNum}번입니다. 번호판에 번호가 뜨면 찾아가세요.`)
  }, []) 
  
  const showToast = (icon, message) => {
    setToast({ icon, message })
    setTimeout(() => setToast(null), 3000)
  }

  const handleGoHome = async () => {
    logger.log('navigation', 'completion', {
      actionName: 'go_home',
      targetType: 'button',
      targetLabel: 'home',
    })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  // 주차 등록 확인
  const handleParkingConfirm = () => {
    if (carNumber.length < 4) return
    logger.log('click', 'completion', { actionName: 'parking_register', targetType: 'button', targetLabel: 'parking_register' })
    setParkingDone(true)
    setShowParkingPopup(false)
    setCarNumber('')
    showToast('🚗', `${carNumber} 주차 등록 완료! 1시간 무료`)
    tts.speak('주차 등록이 완료되었습니다.')
  }

  // 스탬프 적립 확인
  const handleStampConfirm = () => {
    if (stampMethod === 'phone' && phoneNumber.length < 10) return
    logger.log('click', 'completion', { actionName: 'stamp_register', targetType: 'button', targetLabel: 'stamp_register' })
    sessionStorage.setItem('stamp_count', String(isReward ? 0 : newStamps))
    setStampDone(true)
    setShowStampPopup(false)
    setStampMethod(null)
    setPhoneNumber('')
    const msg = isReward
      ? '스탬프 가득 찼어요! 다음 방문 시 무료 음료'
      : `스탬프 ${earnedStamps}개 적립! (${newStamps}/${TOTAL_STAMPS})`
    showToast('⭐', msg)
    tts.speak('스탬프 적립이 완료되었습니다.')
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6 py-10">

      {/* 완료 아이콘 + 문구 */}
      <div className="text-6xl mb-4 animate-bounce">✅</div>
      <h1 className="text-3xl font-black text-gray-800 mb-2">주문 완료!</h1>
      <p className="text-xl text-gray-500 mb-8">{paymentMethod}으로 결제되었습니다</p>

      {/* 주문번호 */}
      <div className="bg-white rounded-3xl shadow-md border-2 border-amber-200 px-12 py-8 mb-6 w-full max-w-sm text-center">
        <p className="text-xl font-medium text-gray-400 mb-2">주문번호</p>
        <p className="text-6xl font-black text-amber-500">#{orderNum}</p>
        <p className="text-lg text-gray-400 mt-3">번호판에 번호가 뜨면 찾아가세요</p>
      </div>

      {/* 주문 내역 */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm w-full max-w-sm px-6 py-5 mb-6">
        <p className="text-lg font-bold text-gray-500 mb-3">주문 내역</p>
        <div className="divide-y">
          {(state.cart || []).map((item) => {
            const optionLabel = (item.optionLabels || []).join(' · ')
            return (
              <div key={item.cartItemId} className="py-3 flex justify-between items-center">
                <div>
                  <p className="text-xl font-bold text-gray-800">
                    {item.displayName}
                    <span className="text-amber-500 ml-2">×{item.quantity}</span>
                  </p>
                  {optionLabel && <p className="text-base text-gray-400 mt-0.5">{optionLabel}</p>}
                </div>
                <p className="text-xl font-bold text-gray-700">
                  {(item.unitPrice * item.quantity).toLocaleString()}원
                </p>
              </div>
            )
          })}
        </div>
        <div className="border-t pt-3 mt-1 flex justify-between items-center">
          <span className="text-xl font-bold text-gray-600">총 {totalCount}개</span>
          <span className="text-2xl font-black text-amber-600">{totalPrice?.toLocaleString()}원</span>
        </div>
      </div>

      {/* 주차 + 스탬프 버튼 */}
      <div className="flex gap-4 w-full max-w-sm mb-4">
        <button
          onClick={() => !parkingDone && setShowParkingPopup(true)}
          disabled={parkingDone}
          className={`flex-1 flex flex-col items-center justify-center gap-2 py-5 rounded-2xl border-2 font-bold text-lg transition-all
            ${parkingDone
              ? 'border-green-300 bg-green-50 text-green-600'
              : 'border-gray-200 bg-white text-gray-600 hover:border-amber-300 hover:bg-amber-50 active:scale-95'}`}
        >
          <span className="text-4xl">{parkingDone ? '✅' : '🚗'}</span>
          <span>{parkingDone ? '등록 완료' : '주차 등록'}</span>
        </button>

        <button
          onClick={() => !stampDone && setShowStampPopup(true)}
          disabled={stampDone}
          className={`flex-1 flex flex-col items-center justify-center gap-2 py-5 rounded-2xl border-2 font-bold text-lg transition-all
            ${stampDone
              ? 'border-amber-300 bg-amber-50 text-amber-600'
              : 'border-gray-200 bg-white text-gray-600 hover:border-amber-300 hover:bg-amber-50 active:scale-95'}`}
        >
          <span className="text-4xl">{stampDone ? '✅' : '⭐'}</span>
          <span>{stampDone ? '적립 완료' : '스탬프 적립'}</span>
        </button>
      </div>

      {/* 설문 버튼 */}
      <button
        onClick={() => navigate('/survey')}
        className="w-full max-w-sm py-7 bg-emerald-500 border-2 border-emerald-600 text-white font-black text-3xl rounded-2xl transition-transform shadow-lg hover:bg-emerald-600 active:scale-95 mb-5"
      >
        📝 설문 참여하기
      </button>

      {/* 처음으로 버튼 */}
      <button
        onClick={handleGoHome}
        className="w-full max-w-sm py-6 bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white font-black text-2xl rounded-2xl transition-colors shadow-lg"
      >
        처음으로 돌아가기
      </button>


      {/* 토스트 */}
      {toast && (
        <div className="fixed top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-6 py-4 rounded-2xl shadow-xl flex items-center gap-3 z-50">
          <span className="text-3xl">{toast.icon}</span>
          <span className="font-bold text-lg">{toast.message}</span>
        </div>
      )}

      {/* 주차 등록 팝업 */}
      {showParkingPopup && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowParkingPopup(false)}>
          <div className="bg-white rounded-3xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-black text-gray-800 mb-1">주차 등록</h2>
            <p className="text-base text-gray-400 mb-4">차량 번호를 입력해 주세요</p>

            {/* 번호 표시 */}
            <div className="bg-gray-100 rounded-2xl px-4 py-4 text-center mb-2">
              <p className="text-3xl font-black text-gray-800 tracking-widest">
                {carNumber || '차량 번호 입력'}
              </p>
            </div>

            {/* 키패드 */}
            <NumPad value={carNumber} onChange={setCarNumber} maxLength={9} />

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => { setShowParkingPopup(false); setCarNumber('') }}
                className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
              >
                취소
              </button>
              <button
                onClick={handleParkingConfirm}
                disabled={carNumber.length < 4}
                className={`flex-1 py-4 rounded-2xl text-xl font-bold transition-colors
                  ${carNumber.length >= 4
                    ? 'bg-amber-500 hover:bg-amber-600 text-white'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
              >
                등록
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 스탬프 적립 팝업 */}
      {showStampPopup && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => { setShowStampPopup(false); setStampMethod(null); setPhoneNumber('') }}>
          <div className="bg-white rounded-3xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}>

            {/* 방법 선택 */}
            {!stampMethod && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">스탬프 적립</h2>
                <p className="text-base text-gray-400 mb-6">적립 방법을 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => setStampMethod('phone')}
                    className="w-full py-5 rounded-2xl border-2 border-gray-200 bg-white text-gray-700 text-xl font-bold hover:border-amber-400 hover:bg-amber-50 transition-all flex items-center gap-4 px-5"
                  >
                    <span className="text-3xl">📱</span>
                    <span>전화번호로 적립</span>
                  </button>
                  <button
                    onClick={() => setStampMethod('card')}
                    className="w-full py-5 rounded-2xl border-2 border-gray-200 bg-white text-gray-700 text-xl font-bold hover:border-amber-400 hover:bg-amber-50 transition-all flex items-center gap-4 px-5"
                  >
                    <span className="text-3xl">💳</span>
                    <span>멤버십 카드 스캔</span>
                  </button>
                </div>
                <button
                  onClick={() => setShowStampPopup(false)}
                  className="w-full mt-4 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                >
                  취소
                </button>
              </>
            )}

            {/* 전화번호 입력 */}
            {stampMethod === 'phone' && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">전화번호 입력</h2>
                <p className="text-base text-gray-400 mb-4">등록된 전화번호를 입력해 주세요</p>

                <div className="bg-gray-100 rounded-2xl px-4 py-4 text-center mb-2">
                  <p className="text-3xl font-black text-gray-800 tracking-widest">
                    {phoneNumber
                      ? phoneNumber.replace(/(\d{3})(\d{0,4})(\d{0,4})/, (_, a, b, c) => [a, b, c].filter(Boolean).join('-'))
                      : '010-0000-0000'}
                  </p>
                </div>

                <NumPad value={phoneNumber} onChange={setPhoneNumber} maxLength={11} />

                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => setStampMethod(null)}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                  >
                    뒤로
                  </button>
                  <button
                    onClick={handleStampConfirm}
                    disabled={phoneNumber.length < 10}
                    className={`flex-1 py-4 rounded-2xl text-xl font-bold transition-colors
                      ${phoneNumber.length >= 10
                        ? 'bg-amber-500 hover:bg-amber-600 text-white'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
                  >
                    적립
                  </button>
                </div>
              </>
            )}

            {/* 카드 스캔 */}
            {stampMethod === 'card' && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">멤버십 카드 스캔</h2>
                <p className="text-base text-gray-400 mb-6">카드의 바코드를 카메라에 가져다 대주세요</p>

                <div className="bg-gray-100 rounded-2xl h-40 flex items-center justify-center mb-6">
                  <div className="text-center">
                    <p className="text-5xl mb-2">📷</p>
                    <p className="text-gray-400">카메라 준비 중...</p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setStampMethod(null)}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                  >
                    뒤로
                  </button>
                  <button
                    onClick={handleStampConfirm}
                    className="flex-1 py-4 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white text-xl font-bold"
                  >
                    완료
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
