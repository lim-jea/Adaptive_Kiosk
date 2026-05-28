// 관리자 API 클라이언트 — HttpOnly 쿠키 기반 세션.
// 이전에는 X-Admin-API-Key 를 sessionStorage 에 저장했으나 XSS 시 탈취 위험이 있어 폐기.
// 로그인 후 서버가 발급한 HttpOnly 쿠키가 자동 첨부되므로 자바스크립트는 토큰 값을 보지 못한다.

import axios from 'axios'

const LOGIN_PATH = '/admin/login'

const adminApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/',
  timeout: 30000,
  withCredentials: true,  // 쿠키 자동 첨부
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
})

adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined' && window.location.pathname !== LOGIN_PATH) {
        window.location.assign(LOGIN_PATH)
      }
    }
    return Promise.reject(error)
  }
)

// 로그인 — 자격증명 POST. 성공 시 서버가 HttpOnly 쿠키를 set.
export async function adminLogin({ username, password, apiKey }) {
  const body = apiKey ? { api_key: apiKey } : { username, password }
  const res = await adminApi.post('/api/v1/admin/login', body)
  return res.data
}

// 로그아웃 — 서버 측 토큰 무효화 + 쿠키 폐기.
export async function adminLogout() {
  try {
    await adminApi.post('/api/v1/admin/logout', {})
  } catch { /* ignore */ }
}

// 로그인 상태 확인 — 페이지 새로고침 후 세션 유효성 검사용.
export async function adminCheckSession() {
  try {
    await adminApi.get('/api/v1/admin/me')
    return true
  } catch {
    return false
  }
}

// ── Deprecated (호환성 잔재) ──
// 기존 sessionStorage 기반 키는 더 이상 사용하지 않는다. 빈 값 반환.
export function getStoredAdminKey() { return '' }
export function setStoredAdminKey() { /* no-op */ }
export function clearStoredAdminKey() {
  try { sessionStorage.removeItem('admin_api_key') } catch { /* ignore */ }
}

export default adminApi
