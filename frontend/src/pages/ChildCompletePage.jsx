import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

export default function ChildCompletePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { paymentMethod, totalPrice, totalCount } = location.state || {}

  const [orderNum] = useState(() => Math.floor(Math.random() * 900 + 100))
  const [countdown, setCountdown] = useState(30)

  useEffect(() => {
    const enteredAt = Date.now()

    if (state.sessionUuid) {
      logger.logScreenEnter('child_complete', {
        payment_method: paymentMethod,
        total_price: totalPrice,
      })
    }

    return () => {
      if (state.sessionUuid) {
        logger.logScreenExit('child_complete', Date.now() - enteredAt)
      }
    }
  }, [logger, state.sessionUuid, paymentMethod, totalPrice])

  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return

      try {
        logger.log('session', 'child_complete', {
          actionName: 'session_complete',
          source: 'system',
        })

        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, {
          status: 'ended',
          end_reason: 'completed',
        })

        await logger.flush()
      } catch (err) {
        console.warn('세션 종료 실패:', err.message)
      }
    }

    endSession()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          clearInterval(timer)
          handleGoHome()
          return 0
        }

        return current - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoHome = async () => {
    logger.log('navigation', 'child_complete', {
      actionName: 'go_home',
      targetType: 'button',
      targetLabel: 'home',
    })

    await logger.flush()

    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleGoSurvey = async () => {
    logger.log('navigation', 'child_complete', {
      actionName: 'go_survey',
      targetType: 'button',
      targetLabel: 'survey',
    })

    await logger.flush()
    navigate('/survey')
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-10" style={{ background: '#ECFEFF' }}>
      <div className="text-7xl mb-5 animate-bounce">🎉</div>

      <h1 className="text-4xl font-black text-gray-800 mb-3">주문 완료!</h1>

      <p className="text-lg text-gray-500 mb-8">
        {paymentMethod}으로 결제되었어요
      </p>

      <div className="bg-white rounded-[32px] shadow-md border-4 border-sky-200 px-10 py-8 w-full max-w-sm text-center mb-6">
        <p className="text-xl font-bold text-gray-400 mb-2">주문번호</p>
        <p className="text-7xl font-black text-sky-500">#{orderNum}</p>
        <p className="text-base text-gray-400 mt-3">
          번호가 나오면 음료를 받아가세요
        </p>
      </div>

      <div className="bg-white rounded-3xl border-2 border-sky-100 shadow-sm w-full max-w-sm px-6 py-5 mb-6">
        <p className="text-lg font-black text-gray-500 mb-3">주문 내역</p>

        <div className="divide-y">
          {(state.cart || []).map((item) => {
            const optionLabel = (item.optionLabels || []).join(' · ')

            return (
              <div key={item.cartItemId} className="py-3 flex justify-between gap-3">
                <div>
                  <p className="text-xl font-black text-gray-800">
                    {item.displayName}
                    <span className="text-sky-500 ml-2">×{item.quantity}</span>
                  </p>

                  {optionLabel && (
                    <p className="text-sm text-gray-400 mt-1">{optionLabel}</p>
                  )}
                </div>

                <p className="text-lg font-bold text-gray-700">
                  {(item.unitPrice * item.quantity).toLocaleString()}원
                </p>
              </div>
            )
          })}
        </div>

        <div className="border-t pt-3 mt-2 flex justify-between items-center">
          <span className="text-lg font-bold text-gray-600">총 {totalCount}개</span>
          <span className="text-2xl font-black text-sky-600">
            {totalPrice?.toLocaleString()}원
          </span>
        </div>
      </div>

      <button
        onClick={handleGoSurvey}
        className="w-full max-w-sm py-5 bg-white border-4 border-violet-300 text-violet-600 font-black text-2xl rounded-3xl mb-4 active:scale-95 transition-all"
      >
        📝 의견 남기기
      </button>

      <button
        onClick={handleGoHome}
        className="w-full max-w-sm py-6 bg-sky-500 hover:bg-sky-600 text-white font-black text-2xl rounded-3xl shadow-lg active:scale-95 transition-all"
      >
        처음으로 돌아가기
      </button>

      <p className="text-base text-gray-400 mt-4">
        {countdown}초 후 처음 화면으로 이동합니다
      </p>
    </div>
  )
}