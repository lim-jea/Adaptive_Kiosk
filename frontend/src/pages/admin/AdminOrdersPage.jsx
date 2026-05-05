import { useEffect, useMemo, useState } from 'react'
import adminApi from '../../utils/adminApi'
import useDateRange from '../../hooks/useDateRange'
import DateRangePicker from '../../components/admin/DateRangePicker'
import { formatKst, rangeToQuery } from '../../utils/dateRange'

const ORDER_STATUSES = [
  { value: '', label: '전체 상태' },
  { value: 'pending', label: 'pending' },
  { value: 'completed', label: 'completed' },
  { value: 'cancelled', label: 'cancelled' },
]

const REC_OPTIONS = [
  { value: '', label: '추천 사용 무관' },
  { value: 'true', label: '추천 사용' },
  { value: 'false', label: '추천 미사용' },
]

const PAGE_SIZE = 50

function won(n) { return `${Number(n || 0).toLocaleString()}원` }

function OrderDetailModal({ order, onClose }) {
  if (!order) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg bg-white p-6" onClick={(e) => e.stopPropagation()}>
        <header className="mb-4 flex items-start justify-between">
          <div>
            <h3 className="text-lg font-bold">주문 상세</h3>
            <p className="font-mono text-xs text-slate-500">{order.order_uuid}</p>
          </div>
          <button onClick={onClose} className="rounded-md border px-3 py-1 text-sm">닫기</button>
        </header>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-slate-500">일시</dt><dd>{formatKst(order.created_at)}</dd>
          <dt className="text-slate-500">상태</dt><dd>{order.status}</dd>
          <dt className="text-slate-500">총 금액</dt><dd className="font-semibold">{won(order.total_price)}</dd>
          <dt className="text-slate-500">추천 사용</dt><dd>{order.used_recommendation ? '예' : '아니오'}</dd>
          <dt className="text-slate-500">세션 UUID</dt><dd className="font-mono text-xs">{order.session_uuid || '-'}</dd>
        </dl>
        <h4 className="mt-5 mb-2 text-sm font-bold text-slate-700">주문 항목</h4>
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-3 py-2">메뉴</th>
              <th className="px-3 py-2">수량</th>
              <th className="px-3 py-2">단가</th>
              <th className="px-3 py-2">옵션</th>
              <th className="px-3 py-2">추천</th>
            </tr>
          </thead>
          <tbody>
            {(order.items || []).map((item) => (
              <tr key={item.id} className="border-t align-top">
                <td className="px-3 py-2 font-semibold">{item.menu_name}</td>
                <td className="px-3 py-2">{item.quantity}</td>
                <td className="px-3 py-2">{won(item.unit_price)}</td>
                <td className="px-3 py-2 text-xs">
                  {(item.options || []).length === 0 && <span className="text-slate-400">없음</span>}
                  {(item.options || []).map((opt, i) => (
                    <div key={i}>
                      {opt.option_name}
                      {opt.extra_price ? ` (+${won(opt.extra_price)})` : ''}
                    </div>
                  ))}
                </td>
                <td className="px-3 py-2">{item.from_recommendation ? '✓' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function AdminOrdersPage() {
  const [range, setRange] = useDateRange()
  const [statusFilter, setStatusFilter] = useState('')
  const [recFilter, setRecFilter] = useState('')
  const [skip, setSkip] = useState(0)

  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)

  const params = useMemo(() => {
    const p = { ...rangeToQuery({ from: range.from, to: range.to }), skip, limit: PAGE_SIZE }
    if (statusFilter) p.status = statusFilter
    if (recFilter !== '') p.used_recommendation = recFilter
    return p
  }, [range.from, range.to, statusFilter, recFilter, skip])

  useEffect(() => {
    let mounted = true
    setLoading(true)
    adminApi.get('/api/v1/orders', { params })
      .then((res) => {
        if (!mounted) return
        setOrders(res.data.items || [])
        setTotal(res.data.total || 0)
        setError('')
      })
      .catch(() => mounted && setError('주문 목록을 불러오지 못했습니다.'))
      .finally(() => mounted && setLoading(false))
    return () => { mounted = false }
  }, [params])

  const onRangeChange = (next) => { setRange(next); setSkip(0) }

  return (
    <section>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">주문 조회</h2>
          <p className="mt-1 text-sm text-slate-500">행을 클릭하면 주문 상세(옵션 포함)가 표시됩니다.</p>
        </div>
        <DateRangePicker preset={range.preset} from={range.from} to={range.to} onChange={onRangeChange} />
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setSkip(0) }} className="rounded-md border px-2 py-1">
          {ORDER_STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select value={recFilter} onChange={(e) => { setRecFilter(e.target.value); setSkip(0) }} className="rounded-md border px-2 py-1">
          {REC_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <span className="text-slate-500">총 {total.toLocaleString()}건</span>
      </div>

      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {loading && <p className="text-slate-400">불러오는 중...</p>}

      <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">주문 UUID</th>
              <th className="px-4 py-3">일시</th>
              <th className="px-4 py-3">상태</th>
              <th className="px-4 py-3">금액</th>
              <th className="px-4 py-3">추천</th>
              <th className="px-4 py-3">항목 수</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr
                key={order.order_uuid}
                onClick={() => setSelected(order)}
                className="cursor-pointer border-t hover:bg-amber-50/50"
              >
                <td className="px-4 py-3 font-mono text-xs">{order.order_uuid.slice(0, 8)}...</td>
                <td className="px-4 py-3">{formatKst(order.created_at)}</td>
                <td className="px-4 py-3">{order.status}</td>
                <td className="px-4 py-3 font-semibold">{won(order.total_price)}</td>
                <td className="px-4 py-3">{order.used_recommendation ? '✓' : ''}</td>
                <td className="px-4 py-3">{(order.items || []).length}</td>
              </tr>
            ))}
            {!loading && orders.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400">결과 없음</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <button
          type="button"
          disabled={skip === 0}
          onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
          className="rounded-md border px-3 py-1 disabled:opacity-50"
        >
          이전
        </button>
        <span className="text-slate-500">{skip + 1} – {Math.min(skip + PAGE_SIZE, total)}</span>
        <button
          type="button"
          disabled={skip + PAGE_SIZE >= total}
          onClick={() => setSkip(skip + PAGE_SIZE)}
          className="rounded-md border px-3 py-1 disabled:opacity-50"
        >
          다음
        </button>
      </div>

      <OrderDetailModal order={selected} onClose={() => setSelected(null)} />
    </section>
  )
}
