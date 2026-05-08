// TTS 훅 — 1순위 인라인 audio_b64, 2순위 백엔드 Edge-TTS 합성 (POST /voice/tts),
// 3순위 브라우저 speechSynthesis 폴백.
// 단순 안내 멘트도 음성 주문 응답과 동일한 Edge-TTS 음색으로 통일하기 위해 백엔드 합성을 자동 호출한다.

import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../utils/api'

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

  // 매직 넘버로 오디오 포맷 자동 감지 (WAV / MP3 모두 지원).
  // backend 가 Edge-TTS 사용 시 mp3, Gemini TTS / 옛 캐시는 wav 가 올 수 있다.
  const detectAudioMime = (u8) => {
    if (!u8 || u8.length < 4) return null
    // WAV: 'RIFF'....'WAVE'
    if (
      u8.length >= 12 &&
      u8[0] === 0x52 && u8[1] === 0x49 && u8[2] === 0x46 && u8[3] === 0x46 &&
      u8[8] === 0x57 && u8[9] === 0x41 && u8[10] === 0x56 && u8[11] === 0x45
    ) return 'audio/wav'
    // MP3 (ID3 v2): 'ID3'
    if (u8[0] === 0x49 && u8[1] === 0x44 && u8[2] === 0x33) return 'audio/mpeg'
    // MP3 (frame sync): 0xFF 0xEx / 0xFx — 상위 11비트 1
    if (u8[0] === 0xFF && (u8[1] & 0xE0) === 0xE0) return 'audio/mpeg'
    return null
  }

  // Uint8Array (WAV/MP3) → Audio 재생 (성공 여부 boolean 반환)
  const playBytes = useCallback((bytes) => {
    try {
      const mime = detectAudioMime(bytes)
      if (!mime) return Promise.resolve(false)
      const blob = new Blob([bytes], { type: mime })
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

  // base64 → bytes → 재생
  const playBase64 = useCallback((b64) => {
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
      return playBytes(bytes)
    } catch {
      return Promise.resolve(false)
    }
  }, [playBytes])

  // 백엔드 /voice/tts 호출 — Edge-TTS 합성 결과(mp3)를 받아 재생.
  // 404(Edge 비활성) 또는 네트워크 오류 시 false 반환 → 호출처가 브라우저 TTS 로 폴백.
  const synthesizeViaBackend = useCallback(async (text) => {
    if (!text) return false
    try {
      const res = await api.post(
        '/api/v1/voice/tts',
        { text },
        { responseType: 'arraybuffer' }
      )
      if (res.status === 200 && res.data) {
        const bytes = new Uint8Array(res.data)
        return await playBytes(bytes)
      }
    } catch {
      // 404(TTS_UNAVAILABLE) / 네트워크 오류 — 호출처에서 브라우저 TTS 폴백
    }
    return false
  }, [playBytes])

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
   * @param {string=} audioB64 - 서버가 인라인으로 보낸 base64 (있으면 즉시 재생)
   *
   * 우선순위: ① audioB64(인자) → ② 백엔드 /voice/tts(Edge-TTS) → ③ 브라우저 speechSynthesis
   */
  const speak = useCallback(async (text, audioB64) => {
    if (!text && !audioB64) return
    if (audioB64) {
      const ok = await playBase64(audioB64)
      if (ok) return
    }
    if (text) {
      const ok = await synthesizeViaBackend(text)
      if (ok) return
    }
    await speakBrowser(text)
  }, [playBase64, synthesizeViaBackend, speakBrowser])

  const cancel = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = '' }
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  return { supported, speaking, speak, cancel }
}
