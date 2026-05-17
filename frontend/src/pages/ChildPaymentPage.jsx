import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const PAYMENT_METHODS = [
  {
    id: 'card',
    label: '카드 결제',
    desc: '카드를 넣거나 찍어주세요',
    bg: '#60A5FA',
  },
  {
    id: 'samsung_pay',
    label: '삼성페이',
    desc: '휴대폰을 가까이 대주세요',
    bg: '#818CF8',
  },
  {
    id: 'apple_pay',
    label: '애플페이',
    desc: 'Face ID로 결제해요',
    bg: '#111827',
  },
]

export default function ChildPaymentPage() {
  const navigate = useNavigate()
  const { state } = useSession()
  const logger = useLogger(state.sessionUuid)

  const [status, setStatus] = useState('idle')
  const [selectedMethod, setSelectedMethod] = useState(null)

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  useEffect(() => {
    const enteredAt = Date.now()

    if (state.sessionUuid) {
      logger.logScreenEnter('child_payment', {
        total_price: totalPrice,
        total_count: totalCount,
      })
    }

    return () => {
      if (state.sessionUuid) {
        logger.logScreenExit('child_payment', Date.now() - enteredAt)
      }
    }
  }, [logger, state.sessionUuid, totalPrice, totalCount])

  const handlePay = useCallback(async (method) => {
    logger.log('payment', 'child_payment', {
      actionName: 'payment_method_select',
      targetType: 'payment_method',
      targetId: method.id,
      targetLabel: method.label,
      payload: {
        total_price: totalPrice,
        total_count: totalCount,
      },
    })

    setSelectedMethod(method)
    setStatus('processing')

    await new Promise((resolve) => setTimeout(resolve, 2000))

    let orderUuid = null
    const orderStartedAt = performance.now()

    try {
      const res = await api.post('/api/v1/orders', {
        session_uuid: state.sessionUuid,
      })

      orderUuid = res.data.order_uuid

      logClientTiming('child_payment.createOrder', performance.now() - orderStartedAt, {
        order_uuid: orderUuid,
      })

      logger.log('order', 'child_payment', {
        actionName: 'order_submit_success',
        targetType: 'order',
        targetId: orderUuid,
        payload: {
          total_price: totalPrice,
          total_count: totalCount,
        },
        source: 'system',
      })
    } catch (err) {
      logClientTiming('child_payment.createOrder.error', performance.now() - orderStartedAt, {
        session_uuid: state.sessionUuid,
      })

      console.error('주문 저장 실패:', err)

      logger.log('order', 'child_payment', {
        actionName: 'order_submit_error',
        payload: {
          message: err?.message || 'order_submit_failed',
        },
        source: 'system',
      })
    }

    setStatus('done')
    await logger.flush()

    navigate('/childcomplete', {
      replace: true,
      state: {
        paymentMethod: method.label,
        totalPrice,
        totalCount,
        orderUuid,
      },
    })
  }, [logger, navigate, state.sessionUuid, totalPrice, totalCount])

  if (status === 'processing') {
    return (
      <div className="fixed inset-0 bg-sky-50 flex flex-col items-center justify-center z-50">
        <div className="w-20 h-20 mb-6 rounded-full bg-sky-100 flex items-center justify-center">
          <span className="text-2xl font-black text-sky-600">결제</span>
        </div>
        <div className="w-14 h-14 border-4 border-sky-400 border-t-transparent rounded-full animate-spin mb-6" />
        <h2 className="text-3xl font-black text-gray-800 mb-2">결제 중이에요!</h2>
        <p className="text-lg text-gray-500">{selectedMethod?.label}로 결제하고 있어요</p>
        <p className="text-3xl font-black text-sky-600 mt-5">{totalPrice.toLocaleString()}원</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#ECFEFF' }}>
      <header className="px-5 py-4 flex items-center gap-3 sticky top-0 z-10 shadow-sm bg-white">
        <button
          onClick={() => navigate('/childkiosk')}
          className="w-11 h-11 rounded-2xl bg-sky-100 text-sky-700 text-2xl font-black"
        >
          ←
        </button>
        <div>
          <h1 className="text-2xl font-black text-gray-800">결제하기</h1>
          <p className="text-sm text-gray-400">결제 방법을 골라주세요</p>
        </div>
      </header>

      <div className="flex-1 px-5 py-6 space-y-5">
        <div className="bg-white rounded-3xl p-5 shadow-sm border-2 border-sky-100">
          <p className="text-lg font-bold text-gray-500">총 결제 금액</p>
          <p className="text-4xl font-black text-sky-600 mt-2">
            {totalPrice.toLocaleString()}원
          </p>
          <p className="text-base text-gray-400 mt-1">총 {totalCount}개 메뉴</p>
        </div>

        <div className="bg-white rounded-3xl overflow-hidden shadow-sm border-2 border-sky-100">
          <div className="px-5 py-4 bg-sky-50 border-b border-sky-100">
            <p className="font-black text-gray-700">주문한 메뉴</p>
          </div>

          <div className="divide-y">
            {state.cart.map((item) => {
              const optionLabel = (item.optionLabels || []).join(' · ')

              return (
                <div key={item.cartItemId} className="px-5 py-4 flex justify-between gap-3">
                  <div>
                    <p className="text-lg font-black text-gray-800">
                      {item.displayName}
                      <span className="text-sky-600 ml-2">×{item.quantity}</span>
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
        </div>

        <div className="space-y-3">
          {PAYMENT_METHODS.map((method) => (
            <button
              key={method.id}
              onClick={() => handlePay(method)}
              className="w-full rounded-3xl px-5 py-5 text-white flex items-center gap-4 active:scale-95 transition-all shadow-md"
              style={{ background: method.bg }}
            >
              <div className="text-left flex-1">
                <p className="text-2xl font-black">{method.label}</p>
                <p className="text-sm opacity-80">{method.desc}</p>
              </div>
              <span className="text-3xl">›</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}