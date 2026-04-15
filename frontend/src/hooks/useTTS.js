// TTS 훅 — 1순위 인라인 audio_b64, 2순위 브라우저 speechSynthesis.
// Gemini TTS 백엔드 호출은 현재 비활성(quota 한도)이라 제거.

import { useCallback, useEffect, useRef, useState } from 'react'

const VOICE_PREFERENCES = [
  /microsoft.*online.*\(natural\)/i,
  /natural/i,
  /neural/i,
  /google.*한국|google.*korean/i,
  /^ko[-_]kr/i,
]

function pickBestKoreanVoice(voices) {
  const ko = voices.filter((v) => /ko/i.test(v.lang))
  if (!ko.length) return null
  for (const re of VOICE_PREFERENCES) {
    const hit = ko.find((v) => re.test(v.name) || re.test(v.lang))
    if (hit) return hit
  }
  return ko[0]
}

export function useTTS({ lang = 'ko-KR', rate = 0.8, pitch = 1.0 } = {}) {
  const [speaking, setSpeaking] = useState(false)
  const [browserVoice, setBrowserVoice] = useState(null)
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const audioRef = useRef(null)

  useEffect(() => {
    if (!supported) return
    const load = () => setBrowserVoice(pickBestKoreanVoice(window.speechSynthesis.getVoices()))
    load()
    window.speechSynthesis.addEventListener?.('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener?.('voiceschanged', load)
  }, [supported])

  useEffect(() => () => {
    if (supported) window.speechSynthesis.cancel()
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = '' }
  }, [supported])

  const looksLikeWav = (u8) => {
    if (!u8 || u8.length < 12) return false
    // 'RIFF'....'WAVE'
    return (
      u8[0] === 0x52 && u8[1] === 0x49 && u8[2] === 0x46 && u8[3] === 0x46 &&
      u8[8] === 0x57 && u8[9] === 0x41 && u8[10] === 0x56 && u8[11] === 0x45
    )
  }

  // base64 WAV → Audio 재생 (성공 여부 boolean 반환)
  const playBase64 = useCallback((b64) => {
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
      if (!looksLikeWav(bytes)) return Promise.resolve(false)

      const blob = new Blob([bytes], { type: 'audio/wav' })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      setSpeaking(true)
      return new Promise((resolve) => {
        audio.onended = () => { setSpeaking(false); URL.revokeObjectURL(url); resolve(true) }
        audio.onerror = () => { setSpeaking(false); URL.revokeObjectURL(url); resolve(false) }
        audio.play().catch(() => { setSpeaking(false); URL.revokeObjectURL(url); resolve(false) })
      })
    } catch {
      return Promise.resolve(false)
    }
  }, [])

  // 브라우저 speechSynthesis
  const speakBrowser = useCallback((text) => {
    if (!supported || !text) return Promise.resolve()
    return new Promise((resolve) => {
      window.speechSynthesis.cancel()
      const utter = new SpeechSynthesisUtterance(text)
      utter.lang = lang
      utter.rate = rate
      utter.pitch = pitch
      if (browserVoice) utter.voice = browserVoice
      utter.onend = () => { setSpeaking(false); resolve() }
      utter.onerror = () => { setSpeaking(false); resolve() }
      setSpeaking(true)
      window.speechSynthesis.speak(utter)
    })
  }, [supported, lang, rate, pitch, browserVoice])

  /**
   * @param {string} text - TTS 텍스트
   * @param {string=} audioB64 - 서버가 인라인으로 보낸 base64 WAV (있으면 즉시 재생)
   */
  const speak = useCallback(async (text, audioB64) => {
    if (!text && !audioB64) return
    if (audioB64) {
      const ok = await playBase64(audioB64)
      if (ok) return
    }
    await speakBrowser(text)
  }, [playBase64, speakBrowser])

  const cancel = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = '' }
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  return { supported, speaking, speak, cancel }
}
