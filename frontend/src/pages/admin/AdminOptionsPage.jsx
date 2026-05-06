import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import adminApi from '../../utils/adminApi'

// 전역 옵션 카탈로그 뷰. 옵션 그룹·아이템이 어떤 메뉴에서 사용되는지 보여준다.
// 옵션 자체의 정의는 메뉴별 row의 집계로 도출되므로, 직접 편집은 메뉴 수정 화면에서.
export default function AdminOptionsPage() {
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [includeUnavailable, setIncludeUnavailable] = useState(true)
  const [search, setSearch] = useState('')
  const [openGroup, setOpenGroup] = useState(null)

  const load = (flag) => {
    setLoading(true)
    setError('')
    adminApi.get('/api/v1/option-catalog', { params: { include_unavailable: flag } })
      .then((res) => setCatalog(res.data || []))
      .catch(() => setError('옵션 카탈로그를 불러오지 못했습니다.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(includeUnavailable) }, [includeUnavailable])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return catalog
    return catalog
      .map((g) => ({
        ...g,
        items: g.items.filter((it) => `${g.group_name} ${it.option_name}`.toLowerCase().includes(q)),
      }))
      .filter((g) => g.group_name.toLowerCase().includes(q) || g.items.length > 0)
  }, [catalog, search])

  return (
    <section>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">옵션 카탈로그</h2>
          <p className="mt-1 text-sm text-slate-500">
            전역 옵션 일람 + 사용 메뉴. 추가/수정/삭제는 각 메뉴의 "수정" 화면에서 진행합니다.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="그룹/옵션명 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <label className="flex items-center gap-1 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={includeUnavailable}
              onChange={(e) => setIncludeUnavailable(e.target.checked)}
            />
            숨김 옵션 포함
          </label>
          <Link to="/admin/menus" className="rounded-md border px-3 py-1.5 text-sm font-semibold">
            메뉴에서 편집 →
          </Link>
        </div>
      </header>

      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {loading && <p className="text-slate-400">불러오는 중...</p>}

      {!loading && filtered.length === 0 && (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-slate-400">
          표시할 옵션이 없습니다.
        </p>
      )}

      <div className="space-y-3">
        {filtered.map((group) => {
          const isOpen = openGroup === group.group_name
          return (
            <div key={group.group_name} className="rounded-md border border-slate-200 bg-white">
              <button
                type="button"
                onClick={() => setOpenGroup(isOpen ? null : group.group_name)}
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <div className="flex items-center gap-3">
                  <span className="text-base font-bold">{group.group_name}</span>
                  <span className="text-xs text-slate-500">
                    옵션 {group.items.length}개 · 사용 메뉴 {group.used_in_menus.length}개
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Tag>min {group.representative_min_select}</Tag>
                  <Tag>max {group.representative_max_select}</Tag>
                  <Tag>{group.representative_is_required ? '필수' : '선택'}</Tag>
                  <span className="text-slate-400">{isOpen ? '▲' : '▼'}</span>
                </div>
              </button>
              {isOpen && (
                <div className="border-t border-slate-100 px-4 py-3">
                  <div className="mb-3 text-xs text-slate-500">
                    이 그룹을 사용하는 메뉴:&nbsp;
                    {group.used_in_menus.map((m) => (
                      <span key={m.id} className="mr-2 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5">
                        {m.name}
                      </span>
                    ))}
                  </div>
                  <table className="w-full text-sm">
                    <thead className="text-slate-500">
                      <tr>
                        <th className="text-left">옵션명</th>
                        <th>평균 추가가격</th>
                        <th className="text-left">사용 메뉴</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.items.map((it) => (
                        <tr key={it.option_name} className="border-t">
                          <td className="py-1.5 font-semibold">{it.option_name}</td>
                          <td className="text-center">{it.avg_extra_price.toLocaleString()}원</td>
                          <td className="py-1.5">
                            {it.used_in_menus.map((m) => (
                              <span key={m.id} className="mr-1 inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-xs">
                                {m.name}
                              </span>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function Tag({ children }) {
  return <span className="rounded-full border border-slate-200 px-2 py-0.5">{children}</span>
}
