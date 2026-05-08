import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import adminApi from '../../utils/adminApi'

const SERVING_TEMPERATURE_OPTIONS = [
  { value: '', label: '온도 선택 없음' },
  { value: 'hot', label: 'hot (따뜻)' },
  { value: 'cold', label: 'cold (차가움)' },
  { value: 'both', label: 'both (선택 가능)' },
]

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

const emptyOptionItem = () => ({ name: '', extra_price: 0, is_default: false, is_available: true, option_order: 0 })
const emptyGroup = () => ({
  name: '', group_order: 0, is_required: true, min_select: 1, max_select: 1, items: [emptyOptionItem()],
})

function buildCreatePayload(form, optionGroups) {
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
    option_groups: optionGroups?.length ? optionGroups : null,
  }
}

function buildUpdatePayload(form, original, optionGroups, optionGroupsTouched) {
  const candidate = {
    name: form.name.trim(),
    category: form.category.trim(),
    price: Number(form.price),
    icon_emoji: form.icon_emoji,
    calories: form.calories === '' ? undefined : Number(form.calories),
    serving_temperature: form.serving_temperature,
    is_caffeinated: Boolean(form.is_caffeinated),
    description: form.description,
    image_url: form.image_url,
  }
  const result = {}
  for (const [key, value] of Object.entries(candidate)) {
    if (value === undefined) continue
    if (value === '' && original?.[key] == null) continue
    if (value === original?.[key]) continue
    result[key] = value === '' ? null : value
  }
  if (optionGroupsTouched) result.option_groups = optionGroups
  return result
}

function FormRow({ label, children, hint }) {
  return (
    <label className="block text-sm">
      <span className="font-semibold text-slate-700">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}

function OptionGroupsEditor({ groups, onChange, catalog }) {
  const setGroup = (i, patch) => {
    const next = groups.slice()
    next[i] = { ...next[i], ...patch }
    onChange(next)
  }
  const setItem = (gi, ii, patch) => {
    const next = groups.slice()
    const items = next[gi].items.slice()
    items[ii] = { ...items[ii], ...patch }
    next[gi] = { ...next[gi], items }
    onChange(next)
  }

  // 카탈로그에서 그룹 통째로 가져오기.
  const importGroup = (groupName) => {
    const cat = (catalog || []).find((g) => g.group_name === groupName)
    if (!cat) return
    if (groups.some((g) => g.name === cat.group_name)) {
      window.alert('이미 같은 이름의 그룹이 있습니다.')
      return
    }
    onChange([
      ...groups,
      {
        name: cat.group_name,
        group_order: groups.length,
        is_required: cat.representative_is_required,
        min_select: cat.representative_min_select,
        max_select: cat.representative_max_select,
        items: cat.items.map((it, idx) => ({
          name: it.option_name,
          extra_price: it.avg_extra_price,
          is_default: false,
          is_available: true,
          option_order: idx,
        })),
      },
    ])
  }

  // 카탈로그에서 특정 그룹의 옵션을 현재 그룹에 한 줄 추가.
  const importItem = (gi, optionName) => {
    const groupName = groups[gi]?.name
    const cat = (catalog || []).find((g) => g.group_name === groupName)
    const item = cat?.items.find((it) => it.option_name === optionName)
    if (!item) return
    if (groups[gi].items.some((x) => x.name === item.option_name)) return
    setGroup(gi, {
      items: [
        ...groups[gi].items,
        {
          name: item.option_name,
          extra_price: item.avg_extra_price,
          is_default: false,
          is_available: true,
          option_order: groups[gi].items.length,
        },
      ],
    })
  }

  const groupNameOptions = (catalog || []).map((g) => g.group_name)

  return (
    <div className="space-y-3">
      <datalist id="catalog-group-names">
        {groupNameOptions.map((n) => <option key={n} value={n} />)}
      </datalist>

      {(catalog || []).length > 0 && (
        <div className="rounded-md border border-dashed border-amber-300 bg-amber-50 p-2 text-xs">
          <span className="mr-2 font-semibold text-amber-900">카탈로그에서 그룹 가져오기:</span>
          <select
            defaultValue=""
            onChange={(e) => { if (e.target.value) { importGroup(e.target.value); e.target.value = '' } }}
            className="rounded border px-1 py-0.5"
          >
            <option value="">선택...</option>
            {catalog.map((g) => (
              <option key={g.group_name} value={g.group_name}>
                {g.group_name} ({g.items.length}개 옵션 · {g.used_in_menus.length}개 메뉴)
              </option>
            ))}
          </select>
        </div>
      )}

      {groups.map((g, gi) => {
        const matchedCat = (catalog || []).find((c) => c.group_name === g.name)
        const itemListId = `catalog-items-${gi}`
        return (
          <div key={gi} className="rounded-md border border-slate-200 p-3">
            <div className="flex items-center gap-2">
              <input
                list="catalog-group-names"
                className="flex-1 rounded-md border px-2 py-1 text-sm"
                placeholder="그룹 이름 (예: 사이즈, 샷 추가)"
                value={g.name}
                onChange={(e) => setGroup(gi, { name: e.target.value })}
              />
              <button
                type="button"
                onClick={() => onChange(groups.filter((_, i) => i !== gi))}
                className="rounded-md border px-2 py-1 text-xs text-red-600"
              >
                그룹 삭제
              </button>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
              <label>필수
                <input type="checkbox" className="ml-2" checked={g.is_required} onChange={(e) => setGroup(gi, { is_required: e.target.checked })} />
              </label>
              <label>최소 선택
                <input type="number" className="ml-2 w-14 rounded border px-1" min={0} value={g.min_select} onChange={(e) => setGroup(gi, { min_select: Number(e.target.value) || 0 })} />
              </label>
              <label>최대 선택
                <input type="number" className="ml-2 w-14 rounded border px-1" min={1} value={g.max_select} onChange={(e) => setGroup(gi, { max_select: Number(e.target.value) || 1 })} />
              </label>
            </div>

            {matchedCat && (
              <datalist id={itemListId}>
                {matchedCat.items.map((it) => <option key={it.option_name} value={it.option_name} />)}
              </datalist>
            )}

            <table className="mt-2 w-full text-xs">
              <thead className="text-slate-500">
                <tr>
                  <th className="text-left">옵션명</th>
                  <th>추가가격</th>
                  <th>기본</th>
                  <th>판매</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {g.items.map((it, ii) => (
                  <tr key={ii} className="border-t">
                    <td>
                      <input
                        list={matchedCat ? itemListId : undefined}
                        className="w-full rounded border px-1 py-0.5"
                        value={it.name}
                        onChange={(e) => setItem(gi, ii, { name: e.target.value })}
                      />
                    </td>
                    <td><input type="number" className="w-20 rounded border px-1" value={it.extra_price} onChange={(e) => setItem(gi, ii, { extra_price: Number(e.target.value) || 0 })} /></td>
                    <td className="text-center"><input type="checkbox" checked={it.is_default} onChange={(e) => setItem(gi, ii, { is_default: e.target.checked })} /></td>
                    <td className="text-center"><input type="checkbox" checked={it.is_available} onChange={(e) => setItem(gi, ii, { is_available: e.target.checked })} /></td>
                    <td><button type="button" onClick={() => setGroup(gi, { items: g.items.filter((_, k) => k !== ii) })} className="text-red-600">삭제</button></td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setGroup(gi, { items: [...g.items, emptyOptionItem()] })}
                className="rounded-md border px-2 py-1 text-xs"
              >+ 옵션 추가</button>
              {matchedCat && matchedCat.items.length > 0 && (
                <select
                  defaultValue=""
                  onChange={(e) => { if (e.target.value) { importItem(gi, e.target.value); e.target.value = '' } }}
                  className="rounded border px-1 py-0.5 text-xs"
                >
                  <option value="">카탈로그에서 옵션 가져오기...</option>
                  {matchedCat.items.map((it) => (
                    <option key={it.option_name} value={it.option_name}>
                      {it.option_name} (+{it.avg_extra_price.toLocaleString()}원)
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        )
      })}
      <button
        type="button"
        onClick={() => onChange([...groups, emptyGroup()])}
        className="rounded-md border border-dashed px-3 py-2 text-xs text-slate-600"
      >+ 빈 옵션 그룹 추가</button>
    </div>
  )
}

export default function AdminMenuPage() {
  const [menus, setMenus] = useState([])
  const [catalog, setCatalog] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editing, setEditing] = useState(null)
  const [optionGroups, setOptionGroups] = useState([])
  const [optionGroupsTouched, setOptionGroupsTouched] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadMenus = async () => {
    const res = await adminApi.get('/api/v1/menus', {
      params: { limit: 1000, include_unavailable: true, sort_by: 'category' },
    })
    setMenus(res.data.items || [])
  }

  const loadCatalog = async () => {
    const res = await adminApi.get('/api/v1/option-catalog', { params: { include_unavailable: true } })
    setCatalog(res.data || [])
  }

  useEffect(() => {
    loadMenus().catch(() => setError('메뉴 목록을 불러오지 못했습니다.'))
    loadCatalog().catch(() => {/* 카탈로그는 보조 기능 — 실패해도 페이지 동작 */})
  }, [])

  const startEdit = async (menu) => {
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
    setOptionGroupsTouched(false)
    try {
      const res = await adminApi.get(
        `/api/v1/menus/${encodeURIComponent(menu.name)}`,
        { params: { include_unavailable_options: true } },
      )
      const groups = (res.data.option_groups || []).map((g) => ({
        name: g.name,
        group_order: 0,
        is_required: g.is_required,
        min_select: g.min_select,
        max_select: g.max_select,
        items: (g.items || []).map((it, idx) => ({
          name: it.name,
          extra_price: it.extra_price,
          is_default: it.is_default,
          is_available: it.is_available,
          option_order: idx,
        })),
      }))
      setOptionGroups(groups)
    } catch {
      setOptionGroups([])
    }
  }

  const resetForm = () => {
    setEditing(null)
    setForm(emptyForm)
    setOptionGroups([])
    setOptionGroupsTouched(false)
  }

  const onOptionGroupsChange = (next) => {
    setOptionGroups(next)
    setOptionGroupsTouched(true)
  }

  const submit = async (event) => {
    event.preventDefault()
    setMessage('')
    setError('')
    try {
      if (editing) {
        const payload = buildUpdatePayload(form, editing, optionGroups, optionGroupsTouched)
        if (Object.keys(payload).length === 0) {
          setMessage('변경된 내용이 없습니다.')
          return
        }
        await adminApi.patch(`/api/v1/menus/${editing.id}`, payload)
        setMessage('메뉴를 수정했습니다.')
      } else {
        await adminApi.post('/api/v1/menus', buildCreatePayload(form, optionGroups))
        setMessage('메뉴를 추가했습니다.')
      }
      resetForm()
      await loadMenus()
      loadCatalog().catch(() => {})
    } catch {
      setError('메뉴 저장에 실패했습니다. 이름 중복이나 입력값을 확인하세요.')
    }
  }

  const toggleAvailability = async (menu) => {
    setError('')
    try {
      await adminApi.patch(`/api/v1/menus/${menu.id}`, { is_available: !menu.is_available })
      await loadMenus()
    } catch {
      setError('판매 상태 변경에 실패했습니다.')
    }
  }

  const remove = async (menu) => {
    if (!window.confirm(`"${menu.name}" 메뉴를 숨김 처리할까요? (소프트 삭제)`)) return
    setError('')
    try {
      await adminApi.delete(`/api/v1/menus/${menu.id}`)
      await loadMenus()
    } catch {
      setError('삭제에 실패했습니다.')
    }
  }

  return (
    <section>
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold">메뉴 관리</h2>
          <p className="mt-1 text-sm text-slate-500">메뉴와 옵션을 한 화면에서 관리합니다. 옵션 그룹은 통째로 교체됩니다.</p>
        </div>
        <Link to="/admin/options" className="rounded-md border px-3 py-1.5 text-sm font-semibold">옵션 카탈로그 →</Link>
      </header>

      {(message || error) && (
        <p className={`mb-4 rounded-md px-4 py-3 text-sm ${error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
          {error || message}
        </p>
      )}

      <div className="grid grid-cols-[420px_1fr] gap-6">
        <form onSubmit={submit} className="rounded-md border border-slate-200 bg-white p-5">
          <h3 className="text-lg font-bold">{editing ? `메뉴 수정: ${editing.name}` : '메뉴 추가'}</h3>

          <div className="mt-4 space-y-3">
            <FormRow label="메뉴명">
              <input className="w-full rounded-md border px-3 py-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </FormRow>
            <FormRow label="카테고리" hint="예: 커피, 티, 스무디">
              <input className="w-full rounded-md border px-3 py-2" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} required />
            </FormRow>
            <div className="grid grid-cols-2 gap-3">
              <FormRow label="가격 (원)">
                <input type="number" min={0} className="w-full rounded-md border px-3 py-2" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required />
              </FormRow>
              <FormRow label="칼로리 (kcal)" hint="비워두면 미입력">
                <input type="number" min={0} className="w-full rounded-md border px-3 py-2" value={form.calories} onChange={(e) => setForm({ ...form, calories: e.target.value })} />
              </FormRow>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <FormRow label="아이콘 이모지">
                <input className="w-full rounded-md border px-3 py-2" placeholder="☕" value={form.icon_emoji} onChange={(e) => setForm({ ...form, icon_emoji: e.target.value })} />
              </FormRow>
              <FormRow label="제공 온도">
                <select className="w-full rounded-md border px-3 py-2" value={form.serving_temperature} onChange={(e) => setForm({ ...form, serving_temperature: e.target.value })}>
                  {SERVING_TEMPERATURE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </FormRow>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_caffeinated} onChange={(e) => setForm({ ...form, is_caffeinated: e.target.checked })} />
              <span className="font-semibold">카페인 포함</span>
            </label>
            <FormRow label="설명" hint="고객용 짧은 설명 (255자)">
              <textarea className="w-full rounded-md border px-3 py-2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </FormRow>
            <FormRow label="이미지 URL">
              <input className="w-full rounded-md border px-3 py-2" value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} />
            </FormRow>
          </div>

          <div className="mt-5">
            <h4 className="mb-2 text-sm font-bold text-slate-700">옵션 그룹 (선택)</h4>
            <p className="mb-2 text-xs text-slate-500">변경 후 저장하면 이 메뉴의 옵션이 통째로 교체됩니다. 미수정 시 보존.</p>
            <OptionGroupsEditor groups={optionGroups} onChange={onOptionGroupsChange} catalog={catalog} />
          </div>

          <div className="mt-5 flex gap-2">
            <button type="submit" className="rounded-md bg-slate-950 px-4 py-2 text-sm font-bold text-white">{editing ? '수정 저장' : '추가'}</button>
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
                  <td className="space-x-1 px-4 py-3">
                    <button type="button" onClick={() => startEdit(menu)} className="rounded-md border px-2 py-1 font-semibold">수정</button>
                    <button type="button" onClick={() => toggleAvailability(menu)} className="rounded-md border px-2 py-1 font-semibold">
                      {menu.is_available ? '숨김' : '판매'}
                    </button>
                    <button type="button" onClick={() => remove(menu)} className="rounded-md border border-red-200 px-2 py-1 font-semibold text-red-600">삭제</button>
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
