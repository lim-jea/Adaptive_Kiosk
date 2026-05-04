import { useEffect, useState } from 'react'
import adminApi from '../../utils/adminApi'

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.get('/api/v1/orders', { params: { limit: 100 } })
      .then((res) => setOrders(res.data.items || []))
      .catch(() => setError('주문 목록을 불러오지 못했습니다.'))
  }, [])

  return (
    <section>
      <div className="mb-6">
        <h2 className="text-2xl font-bold">주문 조회</h2>
        <p className="mt-1 text-sm text-slate-500">최근 주문과 주문 항목을 확인합니다.</p>
      </div>
      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">주문 UUID</th>
              <th className="px-4 py-3">일시</th>
              <th className="px-4 py-3">금액</th>
              <th className="px-4 py-3">추천 사용</th>
              <th className="px-4 py-3">항목</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.order_uuid} className="border-t align-top">
                <td className="px-4 py-3 font-mono text-xs">{order.order_uuid}</td>
                <td className="px-4 py-3">{new Date(order.created_at).toLocaleString()}</td>
                <td className="px-4 py-3 font-semibold">{order.total_price.toLocaleString()}원</td>
                <td className="px-4 py-3">{order.used_recommendation ? '사용' : '미사용'}</td>
                <td className="px-4 py-3">
                  {(order.items || []).map((item) => (
                    <div key={item.id}>{item.menu_name} x {item.quantity}</div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
