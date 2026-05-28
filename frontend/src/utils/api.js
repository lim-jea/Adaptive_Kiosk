// API 유틸리티 — axios 인스턴스 및 인터셉터
// baseURL: VITE_API_URL (.env)
// 키오스크 인증:
//   - 세션 생성 직전까지: VITE_KIOSK_API_KEY 를 X-API-Key 헤더로 자동 첨부
//   - 세션 생성 후: 응답의 access_token 을 X-Session-Token 으로 사용 (API key 클라이언트 노출 회피)

import axios from 'axios'

const KIOSK_API_KEY = import.meta.env.VITE_KIOSK_API_KEY || ''
export const DEBUG_TIMING = import.meta.env.VITE_DEBUG_TIMING === 'true' || import.meta.env.DEV

const SESSION_TOKEN_KEY = 'session_access_token'
const SESSION_TOKEN_EXP_KEY = 'session_access_token_expires_at'

export function setSessionToken(token, expiresInSec) {
  if (!token) return
  try {
    const expiresAt = Date.now() + (Number(expiresInSec || 0) * 1000)
    sessionStorage.setItem(SESSION_TOKEN_KEY, token)
    sessionStorage.setItem(SESSION_TOKEN_EXP_KEY, String(expiresAt))
  } catch { /* ignore storage errors */ }
}

export function clearSessionToken() {
  try {
    sessionStorage.removeItem(SESSION_TOKEN_KEY)
    sessionStorage.removeItem(SESSION_TOKEN_EXP_KEY)
  } catch { /* ignore */ }
}

function getSessionToken() {
  try {
    const token = sessionStorage.getItem(SESSION_TOKEN_KEY)
    if (!token) return null
    const expAt = Number(sessionStorage.getItem(SESSION_TOKEN_EXP_KEY) || 0)
    if (expAt && expAt < Date.now()) {
      clearSessionToken()
      return null
    }
    return token
  } catch {
    return null
  }
}

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

function getStoredSessionUuid() {
  try { return sessionStorage.getItem('session_uuid') || '' } catch { return '' }
}

// 요청 인터셉터 — 세션 토큰 + X-Session-UUID 동시 전송
// 토큰이 있으면: X-Session-Token + X-Session-UUID (백엔드 rate limit/세션 매칭 검증용)
// 토큰이 없으면: X-API-Key (세션 생성 시점만)
api.interceptors.request.use(
  (config) => {
    config.metadata = {
      startedAt: performance.now(),
    }
    const sessionToken = getSessionToken()
    if (sessionToken) {
      config.headers['X-Session-Token'] = sessionToken
      const sessionUuid = getStoredSessionUuid()
      if (sessionUuid) {
        config.headers['X-Session-UUID'] = sessionUuid
      }
    } else if (KIOSK_API_KEY) {
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
    // 세션 토큰이 만료/무효이면 폐기하고 홈으로 복귀 — 새 세션을 생성하도록 유도.
    // 그대로 두면 API key 폴백 요청도 백엔드의 엄격한 토큰 검증으로 다시 401 → 무한 루프 위험.
    if (status === 401 && error.config?.headers?.['X-Session-Token']) {
      clearSessionToken()
      try {
        sessionStorage.removeItem('session_uuid')
        sessionStorage.removeItem('kiosk_profile')
        sessionStorage.removeItem('order_type')
        sessionStorage.removeItem('face_consent_at')
      } catch { /* ignore */ }
      if (typeof window !== 'undefined'
          && window.location.pathname !== '/'
          && !window.location.pathname.startsWith('/admin')) {
        window.location.assign('/')
      }
    }
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
