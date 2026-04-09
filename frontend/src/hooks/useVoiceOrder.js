// 음성 주문 통합 훅.
// STT → /voice/messages → 액션 실행 → TTS 의 사이클을 관리한다.
//
// onAction 콜백을 통해 KioskPage 등 외부 컴포넌트가 NavigateAction/CartAddAction 등을
// 실제 화면 상태에 반영하게 한다.

import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../utils/api'
import { useSTT } from './useSTT'
import { useTTS } from './useTTS'

export function useVoiceOrder({ sessionUuid, cartSnapshot, onAction, autoStart = false }) {
  const [status, setStatus] = useState('idle') // idle | starting | listening | thinking | speaking | error | ended
  const [persona, setPersona] = useState('unknown')
  const [stage, setStage] = useState('greeting')
  const [lastResponseText, setLastResponseText] = useState('')
  const [lastUserText, setLastUserText] = useState('')
  const [error, setError] = useState(null)

  const onActionRef = useRef(onAction)
  const cartSnapshotRef = useRef(cartSnapshot)
  const handleAIResponseRef = useRef(null)
  const startedRef = useRef(false)

  useEffect(() => { onActionRef.current = onAction }, [onAction])
  useEffect(() => { cartSnapshotRef.current = cartSnapshot }, [cartSnapshot])

  const tts = useTTS({ rate: 1.0 })

  const dispatchActions = useCallback((actions) => {
    for (const a of actions || []) {
      if (a.type === 'speak') continue // TTS는 별도 처리
      try { onActionRef.current?.(a) } catch (e) { console.error('[voice action]', e) }
    }
  }, [])

  // sendMessage는 useSTT에 onFinal로 들어가야 해서 stt보다 먼저 정의되어야 한다.
  // handleAIResponse는 stt.start()를 써야 하므로, 순환을 끊기 위해 ref로 우회.
  const sendMessage = useCallback(async (text) => {
    if (!sessionUuid || !text) return
    setLastUserText(text)
    setStatus('thinking')
    try {
      const cart = (cartSnapshotRef.current || []).map((i) => ({
        menu_name: i.menuName,
        quantity: i.quantity,
        unit_price: i.unitPrice,
        option_names: i.optionLabels || [],
      }))
      const { data } = await api.post('/api/v1/voice/messages', {
        session_uuid: sessionUuid,
        content: text,
        cart_snapshot: cart,
      })
      setPersona(data.persona)
      setStage(data.current_stage)
      await handleAIResponseRef.current?.(data.response)
    } catch (e) {
      setError(e.response?.data?.detail?.message || e.message)
      setStatus('error')
    }
  }, [sessionUuid])

  const stt = useSTT({ onFinal: sendMessage })

  // stt가 준비된 뒤에 handleAIResponse 정의 — 안전하게 stt.start() 호출 가능
  const handleAIResponse = useCallback(async (resp) => {
    if (!resp) return
    setStage(resp.next_stage || 'greeting')
    setLastResponseText(resp.response_text || '')
    dispatchActions(resp.actions)

    if (resp.response_text) {
      setStatus('speaking')
      await tts.speak(resp.response_text)
    }

    if (resp.end_conversation) {
      setStatus('ended')
      return
    }
    if (resp.requires_user_input) {
      // 짧은 지연으로 onend가 발생할 시간을 준다 (start 충돌 방지).
      setTimeout(() => {
        try { stt.start() } catch (e) { console.error(e) }
      }, 50)
    }
  }, [dispatchActions, tts, stt])

  useEffect(() => {
    handleAIResponseRef.current = handleAIResponse
  }, [handleAIResponse])

  const start = useCallback(async () => {
    if (!sessionUuid || startedRef.current) return
    startedRef.current = true
    setStatus('starting')
    setError(null)
    try {
      const { data } = await api.post('/api/v1/voice/start', { session_uuid: sessionUuid })
      setPersona(data.persona)
      setStage(data.current_stage)
      await handleAIResponseRef.current?.(data.greeting)
    } catch (e) {
      setError(e.response?.data?.detail?.message || e.message)
      setStatus('error')
      startedRef.current = false
    }
  }, [sessionUuid])

  const stop = useCallback(async () => {
    stt.stop()
    tts.cancel()
    if (sessionUuid && startedRef.current) {
      try { await api.post('/api/v1/voice/end', { session_uuid: sessionUuid }) } catch {}
    }
    startedRef.current = false
    setStatus('ended')
  }, [sessionUuid, stt, tts])

  useEffect(() => {
    if (autoStart && sessionUuid && !startedRef.current) {
      start()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, sessionUuid])

  // STT 상태에 따라 status 동기화
  useEffect(() => {
    if (stt.listening) setStatus('listening')
  }, [stt.listening])

  return {
    status,
    persona,
    stage,
    lastUserText,
    lastResponseText,
    interim: stt.interim,
    sttSupported: stt.supported,
    ttsSupported: tts.supported,
    error,
    start,
    stop,
    sendMessage,
  }
}
