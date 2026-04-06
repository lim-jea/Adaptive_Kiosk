// API 유틸리티 — axios 인스턴스 및 인터셉터
// baseURL: VITE_API_URL (.env)
// 키오스크 인증: VITE_KIOSK_API_KEY 를 X-API-Key 헤더로 자동 첨부

import axios from 'axios'

const KIOSK_API_KEY = import.meta.env.VITE_KIOSK_API_KEY || ''

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
})

// 요청 인터셉터 — 모든 요청에 X-API-Key 자동 주입
api.interceptors.request.use(
  (config) => {
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
  (response) => response,
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.error?.message
        || error.response?.data?.detail
        || error.message
    console.error(`[API 응답 오류] ${status}: ${message}`, error.config?.url)
    return Promise.reject(error)
  }
)

export default api
