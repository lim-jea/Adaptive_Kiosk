// TTS 훅 — 1순위 Gemini Flash TTS(서버), 실패 시 브라우저 speechSynthesis 폴백.

import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../utils/api'

// ─── 브라우저 폴백용 음성 선택 ──────────────────────────────────────────────
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

export function useTTS({ lang = 'ko-KR', rate = 0.95, pitch = 1.05 } = {}) {
  const [speaking, setSpeaking] = useState(false)
  const [browserVoice, setBrowserVoice] = useState(null)
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const audioRef = useRef(null)

  // 브라우저 음성 목록 비동기 로드
  useEffect(() => {
    if (!supported) return
    const load = () => {
      const v = window.speechSynthesis.getVoices()
      const best = pickBestKoreanVoice(v)
      if (best) setBrowserVoice(best)
    }
    load()
    window.speechSynthesis.addEventListener?.('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener?.('voiceschanged', load)
  }, [supported])

  useEffect(() => () => {
    if (supported) window.speechSynthesis.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
    }
  }, [supported])

  // ─── 인라인 base64 WAV 재생 (가장 빠름 — 별도 HTTP 호출 없음) ──────────────
  const playAudioBlob = useCallback((blob) => {
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audioRef.current = audio
    setSpeaking(true)
    return new Promise((resolve) => {
      audio.onended = () => { setSpeaking(false); URL.revokeObjectURL(url); resolve() }
      audio.onerror = () => { setSpeaking(false); URL.revokeObjectURL(url); resolve() }
      audio.play().catch(() => { setSpeaking(false); resolve() })
    })
  }, [])

  const speakBase64 = useCallback(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
    const blob = new Blob([bytes], { type: 'audio/wav' })
    return playAudioBlob(blob)
  }, [playAudioBlob])

  // ─── 폴백 1: Gemini TTS 별도 호출 ────────────────────────────────────────
  const speakWithGemini = useCallback(async (text) => {
    const res = await api.post('/api/v1/voice/tts', { text }, { responseType: 'blob' })
    return playAudioBlob(res.data)
  }, [playAudioBlob])

  // ─── 폴백: 브라우저 speechSynthesis ────────────────────────────────────────
  const speakWithBrowser = useCallback((text) => {
    if (!supported) return Promise.resolve()
    return new Promise((resolve) => {
      window.speechSynthesis.cancel()
      const friendly = text
        .replace(/([.!?])\s*/g, '$1 ')
        .replace(/([,;:])\s*/g, '$1 ')
      const utter = new SpeechSynthesisUtterance(friendly)
      utter.lang = lang
      utter.rate = rate
      utter.pitch = pitch
      utter.volume = 1.0
      if (browserVoice) utter.voice = browserVoice
      utter.onend = () => { setSpeaking(false); resolve() }
      utter.onerror = () => { setSpeaking(false); resolve() }
      setSpeaking(true)
      window.speechSynthesis.speak(utter)
    })
  }, [supported, lang, rate, pitch, browserVoice])

  /**
   * @param {string} text
   * @param {string=} audioB64  서버가 인라인으로 보낸 base64 WAV (있으면 즉시 재생)
   */
  const speak = useCallback(async (text, audioB64) => {
    if (!text && !audioB64) return
    if (audioB64) {
      try { return await speakBase64(audioB64) }
      catch (e) { console.warn('[TTS] inline 재생 실패, fallback', e?.message) }
    }
    try {
      await speakWithGemini(text)
    } catch (e) {
      console.warn('[TTS] Gemini 실패, 브라우저 TTS로 폴백', e?.message)
      await speakWithBrowser(text)
    }
  }, [speakBase64, speakWithGemini, speakWithBrowser])

  const cancel = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
    }
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  return { supported, speaking, speak, cancel }
}
