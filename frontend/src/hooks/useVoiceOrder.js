// 음성 주문 통합 훅.
// STT → /voice/messages → 액션 실행 → TTS 의 사이클을 관리한다.
//
// onAction 콜백을 통해 KioskPage 등 외부 컴포넌트가 NavigateAction/CartAddAction 등을
// 실제 화면 상태에 반영하게 한다.

import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../utils/api'
import { useSTT } from './useSTT'
import { useTTS } from './useTTS'

// 음성 주문 시작/종료 알림음 — Web Audio API 로 짧은 두 음 연속 재생 (외부 파일 불필요).
// 시작: 660Hz → 880Hz (상승, "딩-딩"), 종료: 880Hz → 660Hz (하강, "딩-딩")
function playCueTone(direction = 'up') {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const tones = direction === 'up' ? [660, 880] : [880, 660]
    const now = ctx.currentTime
    tones.forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      const start = now + i * 0.13
      const stop = start + 0.12
      // 부드러운 envelope: 0 → 0.18 → 0
      gain.gain.setValueAtTime(0.0001, start)
      gain.gain.exponentialRampToValueAtTime(0.18, start + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, stop)
      osc.connect(gain).connect(ctx.destination)
      osc.start(start)
      osc.stop(stop + 0.02)
    })
    setTimeout(() => { try { ctx.close() } catch {} }, 400)
  } catch (e) {
    // 자동 재생 정책 등으로 실패해도 음성 주문 자체에 영향 없게 무시
  }
}

export function useVoiceOrder({
  sessionUuid,
  selectedCategory,
  selectedMenuName,
  onAction,
  onVoiceEvent,
  autoStart = false,
  ttsRate = 0.8,
}) {
  const [status, setStatus] = useState('idle') // idle | starting | listening | thinking | speaking | error | ended
  const [persona, setPersona] = useState('unknown')
  const [stage, setStage] = useState('greeting')
  const [lastResponseText, setLastResponseText] = useState('')
  const [lastUserText, setLastUserText] = useState('')
  const [error, setError] = useState(null)

  const onActionRef = useRef(onAction)
  const onVoiceEventRef = useRef(onVoiceEvent)
  const selectedCategoryRef = useRef(selectedCategory)
  const selectedMenuNameRef = useRef(selectedMenuName)
  const handleAIResponseRef = useRef(null)
  const startedRef = useRef(false)

  useEffect(() => { onActionRef.current = onAction }, [onAction])
  useEffect(() => { onVoiceEventRef.current = onVoiceEvent }, [onVoiceEvent])
  useEffect(() => { selectedCategoryRef.current = selectedCategory }, [selectedCategory])
  useEffect(() => { selectedMenuNameRef.current = selectedMenuName }, [selectedMenuName])

  const tts = useTTS({ rate: ttsRate })

  const dispatchActions = useCallback((actions) => {
    for (const a of actions || []) {
      if (a.type === 'speak') continue // TTS는 별도 처리
      try { onActionRef.current?.(a) } catch (e) { console.error('[voice action]', e) }
    }
  }, [])

  // sendMessage는 useSTT에 onFinal로 들어가야 해서 stt보다 먼저 정의되어야 한다.
  // handleAIResponse는 stt.start()를 써야 하므로, 순환을 끊기 위해 ref로 우회.
  //
  // 중복 호출 가드:
  //  - inFlightRef: 동일한 sendMessage 가 끝나기 전에 또 호출되는 것을 차단
  //  - lastSentRef: STT 가 같은 final 결과를 짧은 간격으로 두 번 emit 하는 케이스 차단
  const inFlightRef = useRef(false)
  const lastSentRef = useRef({ text: '', at: 0 })
  const sendMessage = useCallback(async (text) => {
    if (!sessionUuid || !text) return
    if (inFlightRef.current) {
      console.warn('[voice] sendMessage skipped — previous call in flight:', text)
      return
    }
    const now = Date.now()
    if (text === lastSentRef.current.text && now - lastSentRef.current.at < 1500) {
      console.warn('[voice] sendMessage skipped — duplicate STT final within 1.5s:', text)
      return
    }
    lastSentRef.current = { text, at: now }
    inFlightRef.current = true

    setLastUserText(text)
    try { onVoiceEventRef.current?.('transcript_submitted', { content: text }) } catch {}
    setStatus('thinking')
    try {
      const { data } = await api.post('/api/v1/voice/messages', {
        session_uuid: sessionUuid,
        content: text,
        selected_category: selectedCategoryRef.current || null,
        selected_menu_name: selectedMenuNameRef.current || null,
      })
      setPersona(data.persona)
      setStage(data.current_stage)
      try {
        onVoiceEventRef.current?.('response_received', {
          matched_by: data.matched_by,
          current_stage: data.current_stage,
          intent: data.response?.intent,
          action_types: (data.response?.actions || []).map((action) => action.type),
        })
      } catch {}
      await handleAIResponseRef.current?.(data.response, data.audio_b64)
    } catch (e) {
      setError(e.response?.data?.detail?.message || e.message)
      setStatus('error')
    } finally {
      inFlightRef.current = false
    }
  }, [sessionUuid])

  const stt = useSTT({ onFinal: sendMessage })

  // stt가 준비된 뒤에 handleAIResponse 정의 — 안전하게 stt.start() 호출 가능
  const handleAIResponse = useCallback(async (resp, audioB64) => {
    if (!resp) return
    setStage(resp.next_stage || 'greeting')
    setLastResponseText(resp.response_text || '')
    dispatchActions(resp.actions)
    try {
      onVoiceEventRef.current?.('actions_applied', {
        next_stage: resp.next_stage || 'greeting',
        action_types: (resp.actions || []).map((action) => action.type),
      })
    } catch {}

    // TTS 재생 전에 STT를 확실히 끈다 — 스피커 출력이 마이크로 피드백되는 것 방지
    try { stt.stop() } catch {}

    if (resp.response_text) {
      setStatus('speaking')
      await tts.speak(resp.response_text, audioB64)
    }

    if (resp.end_conversation) {
      setStatus('ended')
      return
    }
    if (resp.requires_user_input) {
      // TTS 종료 후 잔향(에코)이 마이크에 잡히지 않도록 충분한 지연 후 STT 시작.
      // 느린 TTS(노년층, rate ≤ 0.7)는 발음이 길어져 에코가 더 오래 남으므로 딜레이 증가.
      const restartDelay = ttsRate <= 0.7 ? 1000 : 600
      setTimeout(() => {
        try { stt.start() } catch (e) { console.error(e) }
      }, restartDelay)
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
    // 음성 주문 시작 알림음 (상승 톤)
    playCueTone('up')
    try {
      const { data } = await api.post('/api/v1/voice/start', { session_uuid: sessionUuid })
      setPersona(data.persona)
      setStage(data.current_stage)
      try {
        onVoiceEventRef.current?.('start', {
          persona: data.persona,
          current_stage: data.current_stage,
        })
      } catch {}
      await handleAIResponseRef.current?.(data.greeting, data.audio_b64)
    } catch (e) {
      setError(e.response?.data?.detail?.message || e.message)
      setStatus('error')
      startedRef.current = false
    }
  }, [sessionUuid])

  const stop = useCallback(async () => {
    stt.stop()
    tts.cancel()             // 재생 중인 음성 즉시 끊기 + await 강제 해제
    // dedup 가드 리셋 — stop 후 다시 음성 주문 시작 시 첫 sendMessage 가 막히지 않도록
    inFlightRef.current = false
    lastSentRef.current = { text: '', at: 0 }
    // 음성 주문 종료 알림음 (하강 톤)
    playCueTone('down')
    if (sessionUuid && startedRef.current) {
      try { await api.post('/api/v1/voice/end', { session_uuid: sessionUuid }) } catch {}
    }
    try { onVoiceEventRef.current?.('end', {}) } catch {}
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
