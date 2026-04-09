// 브라우저 speechSynthesis 기반 TTS 훅.

import { useCallback, useEffect, useRef, useState } from 'react'

export function useTTS({ lang = 'ko-KR', rate = 1.0 } = {}) {
  const [speaking, setSpeaking] = useState(false)
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const utterRef = useRef(null)

  useEffect(() => () => {
    if (supported) window.speechSynthesis.cancel()
  }, [supported])

  const speak = useCallback((text) => {
    if (!supported || !text) return Promise.resolve()
    return new Promise((resolve) => {
      window.speechSynthesis.cancel()
      const utter = new SpeechSynthesisUtterance(text)
      utter.lang = lang
      utter.rate = rate
      utter.onend = () => { setSpeaking(false); resolve() }
      utter.onerror = () => { setSpeaking(false); resolve() }
      utterRef.current = utter
      setSpeaking(true)
      window.speechSynthesis.speak(utter)
    })
  }, [supported, lang, rate])

  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  return { supported, speaking, speak, cancel }
}
