// idle timeout 훅 — 일정 시간 무동작 시 콜백을 호출한다.
// 사용자의 터치/키보드/마우스/스크롤 이벤트 감지로 타이머 리셋.
// 화면별로 다른 timeout 을 적용할 수 있도록 enabled / timeoutMs / warningMs 를 받는다.

import { useEffect, useRef, useState } from 'react'

const RESET_EVENTS = ['mousedown', 'touchstart', 'keydown', 'wheel', 'pointermove']

export function useIdleTimeout({
  enabled = true,
  timeoutMs = 180000,    // 기본 3분
  warningMs = 10000,     // 만료 10초 전 경고
  onTimeout,
  onWarning,
  onResume,
}) {
  const [showWarning, setShowWarning] = useState(false)
  const [remainingSec, setRemainingSec] = useState(Math.round(warningMs / 1000))
  const timeoutRef = useRef(null)
  const warningRef = useRef(null)
  const tickRef = useRef(null)

  // 콜백을 ref 로 보관 — 호출부에서 새 함수 인스턴스를 넘겨도 effect 가 재실행되지 않도록.
  const onTimeoutRef = useRef(onTimeout)
  const onWarningRef = useRef(onWarning)
  const onResumeRef = useRef(onResume)
  useEffect(() => { onTimeoutRef.current = onTimeout }, [onTimeout])
  useEffect(() => { onWarningRef.current = onWarning }, [onWarning])
  useEffect(() => { onResumeRef.current = onResume }, [onResume])

  useEffect(() => {
    if (!enabled) return

    const cleanupTimers = () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      if (warningRef.current) clearTimeout(warningRef.current)
      if (tickRef.current) clearInterval(tickRef.current)
    }

    const startTick = () => {
      let left = Math.round(warningMs / 1000)
      setRemainingSec(left)
      if (tickRef.current) clearInterval(tickRef.current)
      tickRef.current = setInterval(() => {
        left -= 1
        setRemainingSec(left)
        if (left <= 0 && tickRef.current) clearInterval(tickRef.current)
      }, 1000)
    }

    const reset = () => {
      cleanupTimers()
      // functional update 로 최신 showWarning 값을 안전하게 참조 — 사용자가 경고 모달 표시 중 화면을 누르면 모달이 사라지도록.
      setShowWarning((prev) => {
        if (prev) onResumeRef.current?.()
        return false
      })
      warningRef.current = setTimeout(() => {
        setShowWarning(true)
        startTick()
        onWarningRef.current?.()
      }, Math.max(0, timeoutMs - warningMs))
      timeoutRef.current = setTimeout(() => {
        onTimeoutRef.current?.()
      }, timeoutMs)
    }

    reset()
    for (const ev of RESET_EVENTS) {
      window.addEventListener(ev, reset, { passive: true })
    }
    return () => {
      cleanupTimers()
      for (const ev of RESET_EVENTS) {
        window.removeEventListener(ev, reset)
      }
    }
  }, [enabled, timeoutMs, warningMs])

  const extend = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    if (warningRef.current) clearTimeout(warningRef.current)
    if (tickRef.current) clearInterval(tickRef.current)
    setShowWarning(false)
    onResume?.()
    // 다음 사이클은 자동으로 RESET_EVENTS 리스너가 재시작하지 않으므로 dummy 이벤트
    window.dispatchEvent(new Event('mousedown'))
  }

  return { showWarning, remainingSec, extend }
}
