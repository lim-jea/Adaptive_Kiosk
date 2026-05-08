import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend,
} from 'recharts'
import adminApi from '../../utils/adminApi'
import useDateRange from '../../hooks/useDateRange'
import DateRangePicker from '../../components/admin/DateRangePicker'
import { formatKstDate, rangeToQuery } from '../../utils/dateRange'

const tabs = [
  { to: '/admin/analytics', label: '매출/메뉴', end: true },
  { to: '/admin/analytics/users', label: '사용자' },
  { to: '/admin/analytics/recommendations', label: '추천' },
]

function won(n) { return `${Number(n || 0).toLocaleString()}원` }
function percent(v) { return `${((Number(v) || 0) * 100).toFixed(1)}%` }

export default function AdminAnalyticsLayout() {
  const [range, setRange] = useDateRange()
  const params = useMemo(() => rangeToQuery({ from: range.from, to: range.to }), [range])
  const location = useLocation()

  return (
    <section>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">분석</h2>
          <p className="mt-1 text-sm text-slate-500">기간: {formatKstDate(params.start_date)} ~ {formatKstDate(params.end_date)} (KST)</p>
        </div>
        <DateRangePicker preset={range.preset} from={range.from} to={range.to} onChange={setRange} />
      </header>
      <nav className="mb-5 flex gap-2">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) => `rounded-md border px-3 py-1.5 text-sm font-semibold ${isActive ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-slate-200 text-slate-500'}`}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={{ params, location }} />
    </section>
  )
}

function useAnalyticsData(endpoints, params) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let mounted = true
    Promise.all(endpoints.map((url) => adminApi.get(url, { params })))
      .then((results) => mounted && setData(results.map((r) => r.data)))
      .catch(() => mounted && setError('데이터를 불러오지 못했습니다.'))
    return () => { mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(params), endpoints.join(',')])
  return { data, error }
}

export function AnalyticsRevenueTab() {
  const { params } = useOutletContext()
  const { data, error } = useAnalyticsData([
    '/api/v1/analytics/menus/top',
    '/api/v1/analytics/menus/by-category',
    '/api/v1/analytics/menus/options',
  ], { ...params, limit: 10 })
  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <p className="text-slate-400">불러오는 중...</p>
  const [topMenus, categories, optionUsage] = data
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="메뉴 TOP 10 (수량)">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={topMenus} layout="vertical" margin={{ left: 70 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="name" width={120} />
              <Tooltip formatter={(v, n) => n === 'revenue' ? won(v) : v} />
              <Bar dataKey="quantity" fill="#0f172a" name="수량" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="카테고리별 매출 비중">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-2 text-left">카테고리</th><th>수량</th><th>매출</th><th>비중</th></tr></thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.category} className="border-t">
                  <td className="px-3 py-1.5">{c.category}</td>
                  <td className="text-center">{c.quantity.toLocaleString()}</td>
                  <td className="text-right">{won(c.revenue)}</td>
                  <td className="text-right">{percent(c.share)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
      <Panel title="옵션 선택 분포 (전체 메뉴)">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-2 text-left">그룹</th><th className="text-left">옵션</th><th>선택 수</th><th>그룹 내 비중</th></tr></thead>
          <tbody>
            {optionUsage.length === 0 && <tr><td colSpan={4} className="px-3 py-3 text-center text-slate-400">데이터 없음</td></tr>}
            {optionUsage.map((o, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-1.5">{o.group_name}</td>
                <td>{o.option_name}</td>
                <td className="text-center">{o.count.toLocaleString()}</td>
                <td className="text-right">{percent(o.share)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  )
}

export function AnalyticsUsersTab() {
  const { params } = useOutletContext()
  const { data, error } = useAnalyticsData([
    '/api/v1/analytics/sessions/demographics',
    '/api/v1/analytics/sessions/funnel',
  ], params)
  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <p className="text-slate-400">불러오는 중...</p>
  const [demographics, funnel] = data
  return (
    <div className="space-y-4">
      <Panel title={`세션 전환 (전환률 ${percent(funnel.order_conversion)})`}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={[
            { stage: '세션', value: funnel.sessions },
            { stage: '카트', value: funnel.sessions_with_cart },
            { stage: '주문', value: funnel.sessions_with_order },
          ]}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="stage" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#0f172a" />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="연령×성별 (세션 기반)">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500"><tr><th className="px-3 py-2 text-left">연령대</th><th>성별</th><th>세션</th><th>주문</th><th>매출</th></tr></thead>
          <tbody>
            {demographics.length === 0 && <tr><td colSpan={5} className="px-3 py-3 text-center text-slate-400">데이터 없음</td></tr>}
            {demographics.map((d, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-1.5">{d.age_group || '-'}</td>
                <td className="text-center">{d.gender || '-'}</td>
                <td className="text-center">{d.sessions}</td>
                <td className="text-center">{d.orders}</td>
                <td className="text-right">{won(d.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  )
}

export function AnalyticsRecommendationsTab() {
  const { params } = useOutletContext()
  const { data, error } = useAnalyticsData([
    '/api/v1/analytics/recommendations/funnel',
    '/api/v1/analytics/recommendations/by-category',
    '/api/v1/analytics/recommendations/by-type',
  ], params)
  if (error) return <p className="text-red-600">{error}</p>
  if (!data) return <p className="text-slate-400">불러오는 중...</p>
  const [funnel, byCategory, byType] = data
  return (
    <div className="space-y-4">
      <Panel title={`추천 깔때기 (CTR ${percent(funnel.ctr)} · CVR ${percent(funnel.cvr)})`}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={[
            { stage: '노출', value: funnel.shown },
            { stage: '클릭', value: funnel.clicked },
            { stage: '주문', value: funnel.led_to_order },
          ]}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="stage" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="선호 카테고리별 성과">
          <BreakdownTable rows={byCategory} />
        </Panel>
        <Panel title="추천 타입별 성과">
          <BreakdownTable rows={byType} />
        </Panel>
      </div>
    </div>
  )
}

function BreakdownTable({ rows }) {
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-50 text-slate-500">
        <tr><th className="px-3 py-2 text-left">키</th><th>노출</th><th>클릭</th><th>주문</th><th>CTR</th><th>CVR</th></tr>
      </thead>
      <tbody>
        {rows.length === 0 && <tr><td colSpan={6} className="px-3 py-3 text-center text-slate-400">데이터 없음</td></tr>}
        {rows.map((r, i) => (
          <tr key={i} className="border-t">
            <td className="px-3 py-1.5">{r.key}</td>
            <td className="text-center">{r.shown}</td>
            <td className="text-center">{r.clicked}</td>
            <td className="text-center">{r.led_to_order}</td>
            <td className="text-right">{percent(r.ctr)}</td>
            <td className="text-right">{percent(r.cvr)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Panel({ title, children }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <h3 className="mb-2 text-sm font-bold text-slate-700">{title}</h3>
      {children}
    </div>
  )
}

