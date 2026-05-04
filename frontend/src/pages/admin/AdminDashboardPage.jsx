import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import adminApi from '../../utils/adminApi'
import { formatBucket, formatKstDate, pickBucket, rangeToQuery } from '../../utils/dateRange'
import useDateRange from '../../hooks/useDateRange'
import DateRangePicker from '../../components/admin/DateRangePicker'

const PIE_COLORS = ['#f59e0b', '#fb7185', '#34d399', '#60a5fa', '#a78bfa', '#f472b6', '#fbbf24', '#22d3ee']

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-950">{value}</p>
      {sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}
    </div>
  )
}

function percent(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`
}

function won(n) {
  return `${Number(n || 0).toLocaleString()}원`
}

function durationLabel(seconds) {
  const s = Math.round(Number(seconds) || 0)
  if (s < 60) return `${s}초`
  const m = Math.floor(s / 60)
  const rest = s % 60
  return rest === 0 ? `${m}분` : `${m}분 ${rest}초`
}

function EmptyChart({ height = 220, label = '데이터 없음' }) {
  return (
    <div className="flex items-center justify-center text-sm text-slate-400" style={{ height }}>
      {label}
    </div>
  )
}

export default function AdminDashboardPage() {
  const [range, setRange] = useDateRange()
  const bucket = useMemo(() => pickBucket(range), [range])
  const query = useMemo(() => rangeToQuery({ from: range.from, to: range.to }), [range])

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      const fallbacks = {
        orders: { total_orders: 0, total_revenue: 0, avg_order_price: 0, recommendation_used_count: 0, recommendation_used_rate: 0 },
        sessions: { total_sessions: 0, simple_mode_sessions: 0, simple_mode_rate: 0, help_triggered_count: 0 },
        recommendations: { total_shown: 0, total_clicked: 0, click_through_rate: 0, led_to_order_count: 0, order_conversion_rate: 0 },
        ordersTs: [],
        hourOfDay: [],
        topMenus: [],
        byCategory: [],
        recFunnel: { shown: 0, clicked: 0, led_to_order: 0, ctr: 0, cvr: 0 },
        demographics: [],
        sessionFunnel: { sessions: 0, sessions_with_cart: 0, sessions_with_order: 0, cart_conversion: 0, order_conversion: 0 },
        sessionDuration: { sample: 0, avg_seconds: 0, by_age_group: [] },
      }
      const requests = {
        orders: ['/api/v1/analytics/orders', query],
        sessions: ['/api/v1/analytics/sessions', query],
        recommendations: ['/api/v1/analytics/recommendations', query],
        ordersTs: ['/api/v1/analytics/orders/timeseries', { ...query, bucket }],
        hourOfDay: ['/api/v1/analytics/orders/by-hour-of-day', query],
        topMenus: ['/api/v1/analytics/menus/top', { ...query, limit: 10 }],
        byCategory: ['/api/v1/analytics/menus/by-category', query],
        recFunnel: ['/api/v1/analytics/recommendations/funnel', query],
        demographics: ['/api/v1/analytics/sessions/demographics', query],
        sessionFunnel: ['/api/v1/analytics/sessions/funnel', query],
        sessionDuration: ['/api/v1/analytics/sessions/duration', query],
      }
      const entries = Object.entries(requests)
      const settled = await Promise.allSettled(
        entries.map(([, [url, params]]) => adminApi.get(url, { params })),
      )
      if (!mounted) return
      const next = {}
      const failed = []
      entries.forEach(([key], i) => {
        const r = settled[i]
        if (r.status === 'fulfilled') next[key] = r.value.data
        else { next[key] = fallbacks[key]; failed.push(key) }
      })
      setData(next)
      if (failed.length > 0) {
        setError(`일부 통계를 불러오지 못했습니다: ${failed.join(', ')}`)
      }
      setLoading(false)
    }
    load()
    return () => { mounted = false }
  }, [bucket, range.from, range.to])

  return (
    <section>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">대시보드</h2>
          <p className="mt-1 text-sm text-slate-500">
            기간: {formatKstDate(query.start_date)} ~ {formatKstDate(query.end_date)} (KST 기준)
          </p>
        </div>
        <DateRangePicker preset={range.preset} from={range.from} to={range.to} onChange={setRange} />
      </header>

      {loading && <p className="text-slate-500">통계를 불러오는 중...</p>}
      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      {data && (
        <div className="space-y-6">
          {/* KPI */}
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="총 주문" value={data.orders.total_orders.toLocaleString()} />
            <StatCard label="총 매출" value={won(data.orders.total_revenue)} />
            <StatCard label="평균 주문 금액" value={won(Math.round(data.orders.avg_order_price))} />
            <StatCard label="총 세션" value={data.sessions.total_sessions.toLocaleString()} />
            <StatCard label="간편모드 사용률" value={percent(data.sessions.simple_mode_rate)} />
            <StatCard label="도움 요청" value={data.sessions.help_triggered_count.toLocaleString()} />
            <StatCard label="추천 노출" value={data.recommendations.total_shown.toLocaleString()} />
            <StatCard label="추천 클릭률" value={percent(data.recommendations.click_through_rate)} />
            <StatCard label="추천 주문 전환율" value={percent(data.recommendations.order_conversion_rate)} />
            <StatCard
              label="평균 세션 체류시간"
              value={durationLabel(data.sessionDuration?.avg_seconds)}
              sub={`표본 ${(data.sessionDuration?.sample || 0).toLocaleString()}건`}
            />
          </div>

          {/* Time series */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">주문/매출 추이 ({bucket === 'hour' ? '시간' : '일'} 단위)</h3>
              {data.ordersTs.length === 0 ? (
                <EmptyChart height={260} />
              ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={data.ordersTs}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" tickFormatter={(v) => formatBucket(v, bucket)} fontSize={11} />
                  <YAxis yAxisId="orders" />
                  <YAxis yAxisId="revenue" orientation="right" />
                  <Tooltip labelFormatter={(v) => formatBucket(v, bucket)} formatter={(v, n) => n === 'revenue' ? won(v) : v} />
                  <Legend />
                  <Line yAxisId="orders" type="monotone" dataKey="orders" stroke="#0f172a" name="주문 수" />
                  <Line yAxisId="revenue" type="monotone" dataKey="revenue" stroke="#f59e0b" name="매출(원)" />
                </LineChart>
              </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">시간대별 평균 수요 (0~23시)</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.hourOfDay}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="hour" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="orders" fill="#f59e0b" name="주문" />
                  <Bar dataKey="sessions" fill="#94a3b8" name="세션" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Menu breakdown */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">메뉴 TOP 10</h3>
              {data.topMenus.length === 0 ? (
                <EmptyChart height={300} />
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={data.topMenus} layout="vertical" margin={{ left: 70 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={120} />
                    <Tooltip formatter={(v, n) => n === 'revenue' ? won(v) : v} />
                    <Bar dataKey="quantity" fill="#0f172a" name="수량" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">카테고리별 매출 비중</h3>
              {data.byCategory.length === 0 ? (
                <EmptyChart height={300} />
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={data.byCategory} dataKey="revenue" nameKey="category" outerRadius={110} label>
                      {data.byCategory.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => won(v)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Funnels */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">세션 전환 깔때기</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={[
                    { stage: '세션', value: data.sessionFunnel.sessions },
                    { stage: '카트 형성', value: data.sessionFunnel.sessions_with_cart },
                    { stage: '주문 완료', value: data.sessionFunnel.sessions_with_order },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="stage" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#0f172a" />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-2 text-xs text-slate-500">
                카트 전환 {percent(data.sessionFunnel.cart_conversion)} · 주문 전환 {percent(data.sessionFunnel.order_conversion)}
              </p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <h3 className="mb-2 text-sm font-bold text-slate-700">추천 깔때기</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={[
                    { stage: '노출', value: data.recFunnel.shown },
                    { stage: '클릭', value: data.recFunnel.clicked },
                    { stage: '주문 전환', value: data.recFunnel.led_to_order },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="stage" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-2 text-xs text-slate-500">
                CTR {percent(data.recFunnel.ctr)} · CVR {percent(data.recFunnel.cvr)}
              </p>
            </div>
          </div>

          {/* Demographics */}
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <h3 className="mb-2 text-sm font-bold text-slate-700">연령대×성별 (세션 기반)</h3>
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2">연령대</th>
                  <th className="px-3 py-2">성별</th>
                  <th className="px-3 py-2">세션</th>
                  <th className="px-3 py-2">주문</th>
                  <th className="px-3 py-2">매출</th>
                </tr>
              </thead>
              <tbody>
                {data.demographics.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-4 text-center text-slate-400">데이터 없음</td></tr>
                )}
                {data.demographics.map((d, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-2">{d.age_group || '-'}</td>
                    <td className="px-3 py-2">{d.gender || '-'}</td>
                    <td className="px-3 py-2">{d.sessions.toLocaleString()}</td>
                    <td className="px-3 py-2">{d.orders.toLocaleString()}</td>
                    <td className="px-3 py-2">{won(d.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
