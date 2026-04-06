// 인터랙션 로그 버퍼링 커스텀 훅
// 이벤트를 메모리에 쌓아두었다가 세션 종료 시 일괄 전송

import { useRef, useCallback } from 'react'
import api from '../utils/api'

/**
 * 인터랙션 로그 수집 훅
 * @returns {Object} log, flush, logScreenEnter, logScreenExit
 */
export function useLogger() {
  // 이벤트 버퍼 (메모리)
  const bufferRef = useRef([])

  // 시퀀스 카운터 (세션 내 이벤트 순서)
  const seqRef = useRef(1)

  /**
   * 이벤트를 버퍼에 추가
   * @param {string} eventType - click / hover / screen_enter / screen_exit / scroll
   * @param {string} screenName - 발생한 화면 이름
   * @param {string|null} elementId - 클릭된 요소 ID
   * @param {object|null} extra - 부가 데이터
   * @param {string|null} elementType - 요소 유형
   * @param {number|null} durationMs - 체류 시간 (ms)
   */
  const log = useCallback((
    eventType,
    screenName,
    elementId = null,
    extra = null,
    elementType = null,
    durationMs = null,
  ) => {
    bufferRef.current.push({
      event_type: eventType,
      screen_name: screenName,
      element_id: elementId,
      element_type: elementType,
      duration_ms: durationMs,
      seq: seqRef.current++,
      extra,
      created_at: new Date().toISOString(),
    })
  }, [])

  /**
   * 화면 진입 이벤트 자동 기록
   * @param {string} screenName
   */
  const logScreenEnter = useCallback((screenName) => {
    log('screen_enter', screenName)
  }, [log])

  /**
   * 화면 이탈 이벤트 자동 기록
   * @param {string} screenName
   * @param {number} durationMs - 화면 체류 시간 (ms)
   */
  const logScreenExit = useCallback((screenName, durationMs) => {
    log('screen_exit', screenName, null, null, null, durationMs)
  }, [log])

  /**
   * 버퍼에 쌓인 이벤트를 서버로 전송 후 초기화
   * 세션 종료 시 (주문 완료 또는 뒤로가기) 호출
   * @param {string} sessionId
   */
  const flush = useCallback(async (sessionId) => {
    if (!sessionId || bufferRef.current.length === 0) return

    const events = [...bufferRef.current]
    bufferRef.current = []  // 전송 전에 버퍼 초기화 (중복 전송 방지)

    try {
      await api.post('/api/v1/logs/batch', {
        session_id: sessionId,
        events,
      })
    } catch (err) {
      // 로그 전송 실패는 무시 (UX 방해 금지)
      console.warn('로그 전송 실패 (무시됨):', err.message)
      // 실패한 이벤트는 버리지 않고 복원
      bufferRef.current = [...events, ...bufferRef.current]
    }
  }, [])

  return {
    log,
    flush,
    logScreenEnter,
    logScreenExit,
  }
}
