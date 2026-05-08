import axios from 'axios'

const ADMIN_KEY_STORAGE = 'admin_api_key'
const LOGIN_PATH = '/admin/login'

export function getStoredAdminKey() {
  return sessionStorage.getItem(ADMIN_KEY_STORAGE) || ''
}

export function setStoredAdminKey(key) {
  sessionStorage.setItem(ADMIN_KEY_STORAGE, key)
}

export function clearStoredAdminKey() {
  sessionStorage.removeItem(ADMIN_KEY_STORAGE)
}

const adminApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
})

adminApi.interceptors.request.use((config) => {
  const key = getStoredAdminKey()
  if (key) {
    config.headers['X-Admin-API-Key'] = key
  }
  return config
})

adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredAdminKey()
      if (typeof window !== 'undefined' && window.location.pathname !== LOGIN_PATH) {
        window.location.assign(LOGIN_PATH)
      }
    }
    return Promise.reject(error)
  }
)

export default adminApi
