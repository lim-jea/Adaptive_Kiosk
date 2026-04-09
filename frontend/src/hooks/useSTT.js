// Web Speech API 기반 STT 훅.
// interimResults=true 로 실시간 인식 결과를 표시할 수 있게 한다.

import { useCallback, useEffect, useRef, useState } from 'react'

const SpeechRecognition =
  typeof window !== 'undefined' &&
  (window.SpeechRecognition || window.webkitSpeechRecognition)

export function useSTT({ lang = 'ko-KR', onFinal } = {}) {
  const recognitionRef = useRef(null)
  const onFinalRef = useRef(onFinal)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)
  const supported = !!SpeechRecognition

  useEffect(() => {
    onFinalRef.current = onFinal
  }, [onFinal])

  useEffect(() => {
    if (!supported) return
    const rec = new SpeechRecognition()
    rec.lang = lang
    rec.continuous = false
    rec.interimResults = true
    rec.maxAlternatives = 1

    rec.onresult = (event) => {
      let interimText = ''
      let finalText = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i]
        if (r.isFinal) finalText += r[0].transcript
        else interimText += r[0].transcript
      }
      if (interimText) setInterim(interimText)
      if (finalText) {
        setInterim('')
        onFinalRef.current?.(finalText.trim())
      }
    }
    rec.onerror = (e) => {
      setError(e.error || 'unknown')
      setListening(false)
    }
    rec.onend = () => {
      setListening(false)
      setInterim('')
    }

    recognitionRef.current = rec
    return () => {
      try { rec.abort() } catch {}
      recognitionRef.current = null
    }
  }, [supported, lang])

  const start = useCallback(() => {
    if (!recognitionRef.current || listening) return
    setError(null)
    setInterim('')
    try {
      recognitionRef.current.start()
      setListening(true)
    } catch (e) {
      setError(e.message)
    }
  }, [listening])

  const stop = useCallback(() => {
    if (!recognitionRef.current) return
    try { recognitionRef.current.stop() } catch {}
  }, [])

  return { supported, listening, interim, error, start, stop }
}
