import { useCallback, useMemo } from 'react'
import api from '../utils/api'
import { logClientTiming } from '../utils/api'

let sharedBuffer = []
let sharedSeq = 1
let flushInFlight = null

function pushEvent(event) {
  sharedBuffer.push({
    seq: sharedSeq++,
    occurred_at: new Date().toISOString(),
    source: 'ui',
    payload_json: null,
    ...event,
  })
}

async function flushBuffered(sessionUuid) {
  if (!sessionUuid || sharedBuffer.length === 0) return 0
  if (flushInFlight) return flushInFlight

  const events = [...sharedBuffer]
  sharedBuffer = []
  const startedAt = performance.now()

  flushInFlight = api
    .post('/api/v1/logs/batch', {
      session_uuid: sessionUuid,
      events,
    })
    .then(() => {
      logClientTiming('logger.flush', performance.now() - startedAt, {
        event_count: events.length,
      })
      return events.length
    })
    .catch((err) => {
      logClientTiming('logger.flush.error', performance.now() - startedAt, {
        event_count: events.length,
      })
      sharedBuffer = [...events, ...sharedBuffer]
      throw err
    })
    .finally(() => {
      flushInFlight = null
    })

  return flushInFlight
}

export function useLogger(sessionUuid) {
  const log = useCallback(
    (
      eventType,
      screenName,
      {
        actionName,
        targetType = null,
        targetId = null,
        targetLabel = null,
        durationMs = null,
        source = 'ui',
        payload = null,
      } = {}
    ) => {
      pushEvent({
        event_type: eventType,
        screen_name: screenName,
        action_name: actionName || eventType,
        target_type: targetType,
        target_id: targetId == null ? null : String(targetId),
        target_label: targetLabel,
        duration_ms: durationMs,
        source,
        payload_json: payload,
      })

      if (sessionUuid && sharedBuffer.length >= 20) {
        flushBuffered(sessionUuid).catch((err) => {
          console.warn('activity log flush failed:', err?.message || err)
        })
      }
    },
    [sessionUuid]
  )

  const flush = useCallback(
    async (overrideSessionUuid = null) => {
      const targetSessionUuid = overrideSessionUuid || sessionUuid
      if (!targetSessionUuid) return 0
      try {
        return await flushBuffered(targetSessionUuid)
      } catch (err) {
        console.warn('activity log flush failed:', err?.message || err)
        return 0
      }
    },
    [sessionUuid]
  )

  const logScreenEnter = useCallback(
    (screenName, payload = null) => {
      log('screen', screenName, {
        actionName: 'enter',
        payload,
      })
    },
    [log]
  )

  const logScreenExit = useCallback(
    (screenName, durationMs, payload = null) => {
      log('screen', screenName, {
        actionName: 'exit',
        durationMs,
        payload,
      })
    },
    [log]
  )

  return useMemo(
    () => ({
      log,
      flush,
      logScreenEnter,
      logScreenExit,
    }),
    [log, flush, logScreenEnter, logScreenExit]
  )
}
