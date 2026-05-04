import { useEffect, useState } from 'react'
import adminApi from '../../utils/adminApi'

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

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [orders, sessions, recommendations] = await Promise.all([
          adminApi.get('/api/v1/analytics/orders'),
          adminApi.get('/api/v1/analytics/sessions'),
          adminApi.get('/api/v1/analytics/recommendations'),
        ])
        if (mounted) {
          setStats({
            orders: orders.data,
            sessions: sessions.data,
            recommendations: recommendations.data,
          })
        }
      } catch {
        if (mounted) setError('통계를 불러오지 못했습니다.')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [])

  if (loading) return <p className="text-slate-500">통계를 불러오는 중...</p>

  return (
    <section>
      <div className="mb-6">
        <h2 className="text-2xl font-bold">대시보드</h2>
        <p className="mt-1 text-sm text-slate-500">주문, 세션, 추천 성과를 한눈에 확인합니다.</p>
      </div>
      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="총 주문" value={stats.orders.total_orders.toLocaleString()} />
          <StatCard label="총 매출" value={`${stats.orders.total_revenue.toLocaleString()}원`} />
          <StatCard label="평균 주문 금액" value={`${Math.round(stats.orders.avg_order_price).toLocaleString()}원`} />
          <StatCard label="총 세션" value={stats.sessions.total_sessions.toLocaleString()} />
          <StatCard label="간편모드 사용률" value={percent(stats.sessions.simple_mode_rate)} />
          <StatCard label="도움 요청" value={stats.sessions.help_triggered_count.toLocaleString()} />
          <StatCard label="추천 노출" value={stats.recommendations.total_shown.toLocaleString()} />
          <StatCard label="추천 클릭률" value={percent(stats.recommendations.click_through_rate)} />
          <StatCard label="추천 주문 전환율" value={percent(stats.recommendations.order_conversion_rate)} />
        </div>
      )}
    </section>
  )
}
