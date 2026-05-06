// API 유틸리티 — axios 인스턴스 및 인터셉터
// baseURL: VITE_API_URL (.env)
// 키오스크 인증: VITE_KIOSK_API_KEY 를 X-API-Key 헤더로 자동 첨부

import axios from 'axios'

const KIOSK_API_KEY = import.meta.env.VITE_KIOSK_API_KEY || ''
export const DEBUG_TIMING = import.meta.env.VITE_DEBUG_TIMING === 'true' || import.meta.env.DEV

export function logClientTiming(label, durationMs, details = {}) {
  if (!DEBUG_TIMING) return
  const suffix = Object.keys(details).length > 0 ? ` ${JSON.stringify(details)}` : ''
  console.info(`[timing] ${label}: ${durationMs.toFixed(1)}ms${suffix}`)
}

const api = axios.create({
  // VITE_API_URL="" 이면 같은 오리진(상대경로), 미설정이면 로컬 백엔드
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:5000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
})

// 요청 인터셉터 — 모든 요청에 X-API-Key 자동 주입
api.interceptors.request.use(
  (config) => {
    config.metadata = {
      startedAt: performance.now(),
    }
    if (KIOSK_API_KEY) {
      config.headers['X-API-Key'] = KIOSK_API_KEY
    }
    return config
  },
  (error) => {
    console.error('[API 요청 오류]', error)
    return Promise.reject(error)
  }
)

// 응답 인터셉터 — 에러 로깅
api.interceptors.response.use(
  (response) => {
    const startedAt = response.config?.metadata?.startedAt
    if (DEBUG_TIMING && typeof startedAt === 'number') {
      const clientMs = performance.now() - startedAt
      const serverMs = Number(response.headers?.['x-process-time-ms'])
      console.info(
        `[api timing] ${String(response.config?.method || 'GET').toUpperCase()} ${response.config?.url} `
        + `-> ${response.status} | client=${clientMs.toFixed(1)}ms`
        + `${Number.isFinite(serverMs) ? ` | server=${serverMs.toFixed(1)}ms` : ''}`
      )
    }
    return response
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.error?.message
        || error.response?.data?.detail
        || error.message
    const startedAt = error.config?.metadata?.startedAt
    if (DEBUG_TIMING && typeof startedAt === 'number') {
      const clientMs = performance.now() - startedAt
      const serverMs = Number(error.response?.headers?.['x-process-time-ms'])
      console.info(
        `[api timing] ${String(error.config?.method || 'GET').toUpperCase()} ${error.config?.url} `
        + `-> ${status || 'ERR'} | client=${clientMs.toFixed(1)}ms`
        + `${Number.isFinite(serverMs) ? ` | server=${serverMs.toFixed(1)}ms` : ''}`
      )
    }
    console.error(`[API 응답 오류] ${status}: ${message}`, error.config?.url)
    return Promise.reject(error)
  }
)

export default api
