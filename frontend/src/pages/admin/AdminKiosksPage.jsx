import { useEffect, useState } from 'react'
import adminApi from '../../utils/adminApi'

export default function AdminKiosksPage() {
  const [kiosks, setKiosks] = useState([])
  const [form, setForm] = useState({ name: '', location: '' })
  const [issuedKey, setIssuedKey] = useState('')
  const [error, setError] = useState('')

  const loadKiosks = async () => {
    const res = await adminApi.get('/api/v1/kiosks', { params: { limit: 1000 } })
    setKiosks(res.data.items || [])
  }

  useEffect(() => {
    loadKiosks().catch(() => setError('키오스크 목록을 불러오지 못했습니다.'))
  }, [])

  const createKiosk = async (event) => {
    event.preventDefault()
    setError('')
    setIssuedKey('')
    try {
      const res = await adminApi.post('/api/v1/kiosks', {
        name: form.name.trim(),
        location: form.location.trim() || null,
      })
      setIssuedKey(res.data.api_key)
      setForm({ name: '', location: '' })
      await loadKiosks()
    } catch {
      setError('키오스크 등록에 실패했습니다.')
    }
  }

  const toggleActive = async (kiosk) => {
    setError('')
    try {
      await adminApi.patch(`/api/v1/kiosks/${kiosk.id}`, {
        is_active: !kiosk.is_active,
      })
      await loadKiosks()
    } catch {
      setError('키오스크 상태 변경에 실패했습니다.')
    }
  }

  return (
    <section>
      <div className="mb-6">
        <h2 className="text-2xl font-bold">키오스크 관리</h2>
        <p className="mt-1 text-sm text-slate-500">단말 등록과 활성 상태를 관리합니다.</p>
      </div>
      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {issuedKey && (
        <p className="mb-4 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-800">
          발급된 API Key: <span className="font-mono">{issuedKey}</span>
        </p>
      )}
      <div className="grid grid-cols-[360px_1fr] gap-6">
        <form onSubmit={createKiosk} className="rounded-md border border-slate-200 bg-white p-5">
          <h3 className="text-lg font-bold">키오스크 등록</h3>
          <div className="mt-4 space-y-3">
            <input className="w-full rounded-md border px-3 py-2" placeholder="이름" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input className="w-full rounded-md border px-3 py-2" placeholder="위치" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
          </div>
          <button type="submit" className="mt-4 rounded-md bg-slate-950 px-4 py-2 text-sm font-bold text-white">등록</button>
        </form>
        <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">이름</th>
                <th className="px-4 py-3">위치</th>
                <th className="px-4 py-3">상태</th>
                <th className="px-4 py-3">마지막 접속</th>
                <th className="px-4 py-3">관리</th>
              </tr>
            </thead>
            <tbody>
              {kiosks.map((kiosk) => (
                <tr key={kiosk.id} className="border-t">
                  <td className="px-4 py-3">{kiosk.id}</td>
                  <td className="px-4 py-3 font-semibold">{kiosk.name}</td>
                  <td className="px-4 py-3">{kiosk.location || '-'}</td>
                  <td className="px-4 py-3">{kiosk.is_active ? '활성' : '비활성'}</td>
                  <td className="px-4 py-3">{kiosk.last_seen_at ? new Date(kiosk.last_seen_at).toLocaleString() : '-'}</td>
                  <td className="px-4 py-3">
                    <button type="button" onClick={() => toggleActive(kiosk)} className="rounded-md border px-3 py-1 font-semibold">
                      {kiosk.is_active ? '비활성화' : '활성화'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
