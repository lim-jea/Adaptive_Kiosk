// Web Speech API 기반 STT 훅.
// interimResults=true 로 실시간 인식 결과를 표시할 수 있게 한다.
// continuous=true + 침묵 타이머로 발화가 끝나면 자동 커밋한다.
//
// 추후 인식률을 더 높이려면 Deepgram Nova-3 ($200 무료 크레딧, 한국어, 소음 환경 강함)
// 으로 교체를 권장. WebSocket 스트리밍으로 동일 인터페이스 유지 가능.

import { useCallback, useEffect, useRef, useState } from 'react'

const SpeechRecognition =
  typeof window !== 'undefined' &&
  (window.SpeechRecognition || window.webkitSpeechRecognition)

// 마지막 interim 이후 이 시간(ms) 동안 새 결과가 없으면 현재까지의 interim을 final로 커밋
const SILENCE_COMMIT_MS = 1800

export function useSTT({ lang = 'ko-KR', onFinal } = {}) {
  const recognitionRef = useRef(null)
  const onFinalRef = useRef(onFinal)
  const [listening, setListening] = useState(false)
  const listeningRef = useRef(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)
  const supported = !!SpeechRecognition

  // 침묵 감지 타이머
  const silenceTimer = useRef(null)
  const latestInterim = useRef('')

  useEffect(() => { onFinalRef.current = onFinal }, [onFinal])

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current)
      silenceTimer.current = null
    }
  }, [])

  // 침묵 타이머에 의한 수동 커밋
  const commitInterim = useCallback(() => {
    const text = latestInterim.current.trim()
    if (text) {
      setInterim('')
      latestInterim.current = ''
      onFinalRef.current?.(text)
    }
    // recognition을 stop하면 onend에서 listening=false가 됨
    try { recognitionRef.current?.stop() } catch {}
  }, [])

  useEffect(() => {
    if (!supported) return
    const rec = new SpeechRecognition()
    rec.lang = lang
    rec.continuous = true       // 발화 중간에 끊기지 않도록
    rec.interimResults = true
    rec.maxAlternatives = 5

    rec.onresult = (event) => {
      let interimText = ''
      let finalText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i]
        if (r.isFinal) {
          let best = r[0].transcript
          for (let k = 1; k < r.length; k++) {
            if (r[k].transcript.length > best.length) best = r[k].transcript
          }
          finalText += best
        } else {
          interimText += r[0].transcript
        }
      }

      if (finalText) {
        clearSilenceTimer()
        setInterim('')
        latestInterim.current = ''
        onFinalRef.current?.(finalText.trim())
        // continuous 모드에서 final이 오면 stop해서 다음 turn으로 넘긴다
        try { rec.stop() } catch {}
        return
      }

      if (interimText) {
        setInterim(interimText)
        latestInterim.current = interimText
        // 침묵 타이머 리셋 — 새 interim이 올 때마다 연장
        clearSilenceTimer()
        silenceTimer.current = setTimeout(commitInterim, SILENCE_COMMIT_MS)
      }
    }

    rec.onerror = (e) => {
      clearSilenceTimer()
      const transient = ['no-speech', 'aborted', 'audio-capture']
      if (!transient.includes(e.error)) {
        setError(e.error || 'unknown')
      }
      setListening(false)
      listeningRef.current = false
    }

    rec.onend = () => {
      clearSilenceTimer()
      setListening(false)
      listeningRef.current = false
      setInterim('')
      latestInterim.current = ''
    }

    recognitionRef.current = rec
    return () => {
      clearSilenceTimer()
      try { rec.abort() } catch {}
      recognitionRef.current = null
    }
  }, [supported, lang, clearSilenceTimer, commitInterim])

  const start = useCallback(() => {
    if (!recognitionRef.current || listeningRef.current) return
    setError(null)
    setInterim('')
    latestInterim.current = ''

    // InvalidStateError: 이전 recognition 세션이 아직 정리 중일 때 발생.
    // TTS 종료 직후 start() 시 Chrome에서 종종 터지므로 짧은 간격으로 재시도한다.
    const tryStart = (retriesLeft) => {
      if (!recognitionRef.current || listeningRef.current) return
      try {
        recognitionRef.current.start()
        listeningRef.current = true
        setListening(true)
      } catch (e) {
        if (e.name === 'InvalidStateError' && retriesLeft > 0) {
          setTimeout(() => tryStart(retriesLeft - 1), 150)
        } else if (e.name !== 'InvalidStateError') {
          setError(e.message)
        }
      }
    }
    tryStart(3)
  }, [])

  const stop = useCallback(() => {
    clearSilenceTimer()
    if (!recognitionRef.current) return
    try { recognitionRef.current.stop() } catch {}
  }, [clearSilenceTimer])

  return { supported, listening, interim, error, start, stop }
}
