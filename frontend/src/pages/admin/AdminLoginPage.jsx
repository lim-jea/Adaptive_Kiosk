import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import adminApi, { setStoredAdminKey } from '../../utils/adminApi'

export default function AdminLoginPage() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      setStoredAdminKey(apiKey.trim())
      await adminApi.get('/api/v1/analytics/orders')
      navigate('/admin', { replace: true })
    } catch {
      sessionStorage.removeItem('admin_api_key')
      setError('관리자 API 키가 올바르지 않습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-10 text-white">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-md flex-col justify-center">
        <p className="text-sm font-semibold uppercase tracking-widest text-amber-300">BREW AI</p>
        <h1 className="mt-3 text-3xl font-bold">관리자 로그인</h1>
        <form onSubmit={submit} className="mt-8 space-y-4">
          <label className="block">
            <span className="text-sm font-semibold text-slate-300">관리자 API 키</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-4 py-3 text-white outline-none focus:border-amber-400"
              placeholder="관리자 API 키를 입력하세요"
              autoFocus
            />
          </label>
          {error && <p className="rounded-md bg-red-950 px-4 py-3 text-sm text-red-200">{error}</p>}
          <button
            type="submit"
            disabled={loading || !apiKey.trim()}
            className="w-full rounded-md bg-amber-400 px-4 py-3 font-bold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? '확인 중...' : '로그인'}
          </button>
        </form>
      </div>
    </div>
  )
}
