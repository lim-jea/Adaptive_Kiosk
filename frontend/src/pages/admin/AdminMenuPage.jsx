import { useEffect, useState } from 'react'
import adminApi from '../../utils/adminApi'

const emptyForm = {
  name: '',
  category: '',
  price: 0,
  icon_emoji: '',
  calories: '',
  serving_temperature: '',
  is_caffeinated: false,
  description: '',
  image_url: '',
}

function normalizeForm(form) {
  return {
    name: form.name.trim(),
    category: form.category.trim(),
    price: Number(form.price) || 0,
    icon_emoji: form.icon_emoji || null,
    calories: form.calories === '' ? null : Number(form.calories),
    serving_temperature: form.serving_temperature || null,
    is_caffeinated: Boolean(form.is_caffeinated),
    description: form.description || null,
    image_url: form.image_url || null,
  }
}

export default function AdminMenuPage() {
  const [menus, setMenus] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editing, setEditing] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadMenus = async () => {
    const res = await adminApi.get('/api/v1/menus', {
      params: { limit: 1000, include_unavailable: true, sort_by: 'category' },
    })
    setMenus(res.data.items || [])
  }

  useEffect(() => {
    loadMenus().catch(() => setError('메뉴 목록을 불러오지 못했습니다.'))
  }, [])

  const startEdit = (menu) => {
    setEditing(menu)
    setForm({
      name: menu.name || '',
      category: menu.category || '',
      price: menu.price || 0,
      icon_emoji: menu.icon_emoji || '',
      calories: menu.calories ?? '',
      serving_temperature: menu.serving_temperature || '',
      is_caffeinated: menu.is_caffeinated || false,
      description: menu.description || '',
      image_url: menu.image_url || '',
    })
  }

  const resetForm = () => {
    setEditing(null)
    setForm(emptyForm)
  }

  const submit = async (event) => {
    event.preventDefault()
    setMessage('')
    setError('')
    try {
      const payload = normalizeForm(form)
      if (editing) {
        await adminApi.patch(`/api/v1/menus/${editing.id}`, payload)
        setMessage('메뉴를 수정했습니다.')
      } else {
        await adminApi.post('/api/v1/menus', payload)
        setMessage('메뉴를 추가했습니다.')
      }
      resetForm()
      await loadMenus()
    } catch {
      setError('메뉴 저장에 실패했습니다. 이름 중복이나 입력값을 확인하세요.')
    }
  }

  const toggleAvailability = async (menu) => {
    setError('')
    try {
      await adminApi.patch(`/api/v1/menus/${menu.id}/availability`, {
        is_available: !menu.is_available,
      })
      await loadMenus()
    } catch {
      setError('판매 상태 변경에 실패했습니다.')
    }
  }

  return (
    <section>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold">메뉴 관리</h2>
          <p className="mt-1 text-sm text-slate-500">기존 메뉴 구조를 그대로 사용해 메뉴를 추가하고 판매 상태를 바꿉니다.</p>
        </div>
      </div>

      {(message || error) && (
        <p className={`mb-4 rounded-md px-4 py-3 text-sm ${error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
          {error || message}
        </p>
      )}

      <div className="grid grid-cols-[360px_1fr] gap-6">
        <form onSubmit={submit} className="rounded-md border border-slate-200 bg-white p-5">
          <h3 className="text-lg font-bold">{editing ? '메뉴 수정' : '메뉴 추가'}</h3>
          <div className="mt-4 space-y-3">
            <input className="w-full rounded-md border px-3 py-2" placeholder="메뉴명" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input className="w-full rounded-md border px-3 py-2" placeholder="카테고리" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} required />
            <input className="w-full rounded-md border px-3 py-2" type="number" placeholder="가격" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required />
            <input className="w-full rounded-md border px-3 py-2" placeholder="아이콘" value={form.icon_emoji} onChange={(e) => setForm({ ...form, icon_emoji: e.target.value })} />
            <input className="w-full rounded-md border px-3 py-2" type="number" placeholder="칼로리" value={form.calories} onChange={(e) => setForm({ ...form, calories: e.target.value })} />
            <select className="w-full rounded-md border px-3 py-2" value={form.serving_temperature} onChange={(e) => setForm({ ...form, serving_temperature: e.target.value })}>
              <option value="">온도 선택 없음</option>
              <option value="hot">hot</option>
              <option value="ice">ice</option>
            </select>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_caffeinated} onChange={(e) => setForm({ ...form, is_caffeinated: e.target.checked })} />
              카페인 포함
            </label>
            <textarea className="w-full rounded-md border px-3 py-2" placeholder="설명" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <input className="w-full rounded-md border px-3 py-2" placeholder="이미지 URL" value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} />
          </div>
          <div className="mt-4 flex gap-2">
            <button type="submit" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-bold text-white">{editing ? '수정' : '추가'}</button>
            {editing && <button type="button" onClick={resetForm} className="rounded-md border px-4 py-2 text-sm font-bold">취소</button>}
          </div>
        </form>

        <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-3">메뉴</th>
                <th className="px-4 py-3">카테고리</th>
                <th className="px-4 py-3">가격</th>
                <th className="px-4 py-3">상태</th>
                <th className="px-4 py-3">관리</th>
              </tr>
            </thead>
            <tbody>
              {menus.map((menu) => (
                <tr key={menu.id} className="border-t">
                  <td className="px-4 py-3 font-semibold">{menu.icon_emoji} {menu.name}</td>
                  <td className="px-4 py-3">{menu.category}</td>
                  <td className="px-4 py-3">{menu.price.toLocaleString()}원</td>
                  <td className="px-4 py-3">{menu.is_available ? '판매중' : '숨김'}</td>
                  <td className="space-x-2 px-4 py-3">
                    <button type="button" onClick={() => startEdit(menu)} className="rounded-md border px-3 py-1 font-semibold">수정</button>
                    <button type="button" onClick={() => toggleAvailability(menu)} className="rounded-md border px-3 py-1 font-semibold">
                      {menu.is_available ? '숨김' : '판매'}
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
