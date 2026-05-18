import { useEffect, useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import adminApi from '../../utils/adminApi'
import useDateRange from '../../hooks/useDateRange'
import DateRangePicker from '../../components/admin/DateRangePicker'
import { formatKst, formatKstDate, rangeToQuery } from '../../utils/dateRange'

const COLORS = ['#0f172a', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#8b5cf6']

function percent(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`
}

function number(value) {
  return Number(value || 0).toLocaleString()
}

function seconds(value) {
  if (value == null) return '-'
  const total = Math.round(Number(value) || 0)
  if (total < 60) return `${total}초`
  const min = Math.floor(total / 60)
  const sec = total % 60
  return sec ? `${min}분 ${sec}초` : `${min}분`
}

function elapsed(value) {
  if (value == null) return '-'
  return seconds(Number(value) / 1000)
}

function StatCard({ item, onClick }) {
  const value = item.unit === '%' ? `${item.value}%` : item.unit === 'sec' ? seconds(item.value) : number(item.value)
  const clickable = typeof onClick === 'function'
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      className={`rounded-md border border-slate-200 bg-white p-4 text-left ${
        clickable ? 'transition hover:border-amber-300 hover:bg-amber-50/40' : ''
      }`}
    >
      <p className="text-sm font-semibold text-slate-500">{item.label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-950">{value}</p>
      {item.detail && <p className="mt-1 text-xs text-slate-500">{item.detail}</p>}
      {clickable && <p className="mt-2 text-xs font-semibold text-amber-700">분포 보기</p>}
    </button>
  )
}

function Panel({ title, children }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-bold text-slate-700">{title}</h3>
      {children}
    </section>
  )
}

function Empty({ label = '데이터가 없습니다.' }) {
  return <div className="flex h-56 items-center justify-center text-sm text-slate-400">{label}</div>
}

function EventPayload({ payload }) {
  if (!payload || Object.keys(payload).length === 0) return null
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs font-semibold text-slate-500">원본 데이터 보기</summary>
      <pre className="mt-2 max-h-44 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  )
}

function SessionTimelineModal({ session, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState(null)

  useEffect(() => {
    if (!session?.session_uuid) return
    let mounted = true
    setLoading(true)
    setError('')
    setDetail(null)
    adminApi.get(`/api/v1/analytics/usability/sessions/${session.session_uuid}`)
      .then((res) => { if (mounted) setDetail(res.data) })
      .catch(() => { if (mounted) setError('세션 로그를 불러오지 못했습니다.') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [session?.session_uuid])

  if (!session) {
    return (
      <div className="mt-4 rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
        세션을 선택하면 이 영역에 시간순 로그 흐름이 표시됩니다.
      </div>
    )
  }
  const summary = detail?.session || session
  const events = detail?.events || []
  const importantActions = new Set([
    'session_start',
    'age_group_select',
    'face_recognition_click',
    'face_analysis_start',
    'face_analysis_complete',
    'face_analysis_error',
    'enter',
    'menu_click',
    'recommendation_click',
    'option_confirm',
    'menu_detail_close',
    'cart_add',
    'cart_remove',
    'go_to_payment',
    'payment_start',
    'order_submit_success',
    'order_submit_error',
    'order_created',
    'session_complete',
    'voice_action_failed',
  ])
  const visibleEvents = showAll
    ? events
    : events.filter((event) => importantActions.has(event.action_name) || event.event_type === 'order')

  return (
    <div className="mt-4 overflow-hidden rounded-md border border-slate-200 bg-white">
      <header className="flex items-start justify-between gap-4 border-b bg-slate-50 px-5 py-4">
          <div>
            <h3 className="text-lg font-bold">세션 로그 타임라인</h3>
            <p className="mt-1 break-all font-mono text-xs text-slate-500">{summary.session_uuid}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1 text-sm">닫기</button>
      </header>

      <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="rounded-md border border-slate-200 bg-slate-50 p-4">
            <h4 className="text-sm font-bold text-slate-900">세션 요약</h4>
            <div className="mt-3 space-y-2 text-sm">
              <Info label="시작 시각" value={formatKst(summary.started_at)} />
              <Info label="연령대 / 성별" value={`${summary.age_group || '-'} / ${summary.gender || '-'}`} />
              <Info label="주문 상태" value={summary.completed ? '주문 완료' : '미완료'} />
              <Info label="전체 주문 시간" value={seconds(summary.total_seconds)} />
              <Info label="첫 메뉴 선택" value={seconds(summary.first_menu_select_seconds)} />
              <Info label="음성 사용" value={summary.voice_used ? '사용' : '미사용'} />
              <Info label="마지막 행동" value={`${summary.last_screen_name || '-'} / ${summary.last_action_name || '-'}`} />
              <Info label="로그 수" value={`${number(summary.event_count)}건`} />
            </div>
            {detail?.notes?.length > 0 && (
              <div className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-950">
                {detail.notes.map((note, index) => <p key={index}>{note}</p>)}
              </div>
            )}
          </aside>

          <section className="flex flex-col overflow-hidden rounded-md border border-slate-200 bg-white">
            <div className="flex flex-none flex-wrap items-center justify-between gap-2 border-b bg-slate-50 px-4 py-3">
              <div>
                <h4 className="text-sm font-bold text-slate-900">로그 흐름</h4>
                <p className="mt-1 text-xs text-slate-500">
                  {showAll ? `전체 로그 ${events.length}건 표시` : `핵심 흐름 ${visibleEvents.length}건 표시 / 전체 ${events.length}건`}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAll((value) => !value)}
                className="rounded-md border bg-white px-3 py-1.5 text-xs font-semibold text-slate-700"
              >
                {showAll ? '핵심 흐름만 보기' : '전체 로그 보기'}
              </button>
            </div>

            <div className="min-h-0 flex-1 p-3">
              {loading && <p className="text-sm text-slate-500">세션 로그를 불러오는 중...</p>}
              {error && <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
              {!loading && !error && visibleEvents.length === 0 && <Empty label="이 세션에는 표시할 활동 로그가 없습니다." />}

              {!loading && !error && visibleEvents.length > 0 && (
                <div className="h-[460px] overflow-y-auto overscroll-contain rounded-sm bg-white pr-2">
                  <ol className="relative space-y-3 border-l border-slate-200 pl-5">
                    {visibleEvents.map((event, index) => (
                      <li key={`${event.occurred_at}-${index}`} className="relative">
                        <span className="absolute -left-[29px] top-1 h-3 w-3 rounded-full border-2 border-white bg-amber-500" />
                        <button
                          type="button"
                          onClick={() => setSelectedEvent(selectedEvent === event ? null : event)}
                          className="w-full rounded-md border border-slate-200 bg-white p-3 text-left transition hover:border-amber-300 hover:bg-amber-50/30"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div>
                              <p className="text-sm font-bold text-slate-900">{event.action_label}</p>
                              <p className="mt-1 text-sm text-slate-600">{event.summary}</p>
                            </div>
                            <div className="text-right text-xs text-slate-500">
                              <p>{formatKst(event.occurred_at)}</p>
                              <p>시작 후 {elapsed(event.elapsed_ms)}</p>
                            </div>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                            <Badge label="화면" value={event.screen_label || event.screen_name || '-'} />
                            <Badge label="종류" value={event.event_type} />
                            <Badge label="입력" value={event.source} />
                            {event.target_label && <Badge label="대상" value={event.target_label} />}
                            {event.duration_ms != null && <Badge label="체류" value={seconds(event.duration_ms / 1000)} />}
                          </div>
                        </button>
                        {selectedEvent === event && (
                          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50/40 p-3 text-sm">
                            <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 md:grid-cols-4">
                              <Info label="발생 시각" value={formatKst(event.occurred_at)} />
                              <Info label="경과 시간" value={elapsed(event.elapsed_ms)} />
                              <Info label="화면" value={event.screen_label || event.screen_name || '-'} />
                              <Info label="입력 출처" value={event.source || '-'} />
                              <Info label="대상 타입" value={event.target_type || '-'} />
                              <Info label="대상 ID" value={event.target_id || '-'} />
                              <Info label="대상 이름" value={event.target_label || '-'} />
                              <Info label="체류 시간" value={event.duration_ms != null ? seconds(event.duration_ms / 1000) : '-'} />
                            </div>
                            <EventPayload payload={event.payload_json} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </section>
      </div>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-bold text-slate-900">{value}</p>
    </div>
  )
}

function Badge({ label, value }) {
  return (
    <span className="rounded-full border border-slate-200 px-2 py-1">
      {label}: {value}
    </span>
  )
}

function DistributionModal({ metric, data, onClose }) {
  if (!metric) return null
  const rows = metric === 'order'
    ? data.duration_distribution || []
    : data.menu_select_distribution || []
  const title = metric === 'order' ? '주문 완료 시간 분포' : '첫 메뉴 선택 시간 분포'
  const description = metric === 'order'
    ? '세션 시작부터 주문 생성까지 걸린 시간입니다. 평균보다 중앙값이 낮다면 일부 긴 세션이 평균을 끌어올렸을 가능성이 큽니다.'
    : '메뉴 화면 진입부터 첫 메뉴 클릭 또는 추천 메뉴 클릭까지 걸린 시간입니다. 메뉴를 찾는 데 얼마나 걸렸는지 확인할 수 있습니다.'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-3xl rounded-lg bg-white p-6 shadow-xl" onClick={(event) => event.stopPropagation()}>
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold">{title}</h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md border px-3 py-1 text-sm">닫기</button>
        </header>

        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" name="세션 수" fill="#f59e0b" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function AdminUsabilityPage() {
  const [range, setRange] = useDateRange()
  const [sessionSearch, setSessionSearch] = useState('')
  const [completionFilter, setCompletionFilter] = useState('')
  const [voiceFilter, setVoiceFilter] = useState('')
  const [selectedSession, setSelectedSession] = useState(null)
  const [distributionMetric, setDistributionMetric] = useState(null)
  const params = useMemo(() => rangeToQuery({ from: range.from, to: range.to }), [range])
  const queryKey = useMemo(() => JSON.stringify(params), [params])

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError('')
    adminApi.get('/api/v1/analytics/usability', { params })
      .then((res) => { if (mounted) setData(res.data) })
      .catch(() => { if (mounted) setError('사용성 분석 데이터를 불러오지 못했습니다.') })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [queryKey])

  const ageRows = data?.by_age_group || []
  const menuFriction = data?.menu_friction || []
  const abandonRows = (data?.abandon_steps || []).map((row) => ({
    ...row,
    label: `${row.screen_name || '-'} / ${row.action_name || '-'}`,
  }))
  const voiceCompare = data ? [
    { group: '음성 사용', completion: data.voice.completion_rate, avgSeconds: data.voice.avg_total_seconds },
    { group: '터치만 사용', completion: data.touch_only.completion_rate, avgSeconds: data.touch_only.avg_total_seconds },
  ] : []
  const sessions = useMemo(() => {
    const q = sessionSearch.trim().toLowerCase()
    return (data?.sessions || []).filter((row) => {
      if (q && !row.session_uuid.toLowerCase().includes(q)) return false
      if (completionFilter === 'completed' && !row.completed) return false
      if (completionFilter === 'incomplete' && row.completed) return false
      if (voiceFilter === 'voice' && !row.voice_used) return false
      if (voiceFilter === 'touch' && row.voice_used) return false
      return true
    })
  }, [data, sessionSearch, completionFilter, voiceFilter])

  return (
    <section>
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">사용성 분석</h2>
          <p className="mt-1 text-sm text-slate-500">
            기간: {formatKstDate(params.start_date)} ~ {formatKstDate(params.end_date)} (KST)
          </p>
          <p className="mt-1 text-xs text-slate-400">
            특정 이용 기록은 아래 세션 목록에서 UUID로 검색하고, 행을 클릭하면 시간순 로그 타임라인을 볼 수 있습니다.
          </p>
        </div>
        <DateRangePicker preset={range.preset} from={range.from} to={range.to} onChange={setRange} />
      </header>

      {loading && <p className="text-slate-500">분석 데이터를 불러오는 중...</p>}
      {error && <p className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {(data.summary || []).map((item) => (
              <StatCard
                key={item.key}
                item={item}
                onClick={
                  item.key === 'avg_total_seconds'
                    ? () => setDistributionMetric('order')
                    : item.key === 'avg_menu_select_seconds'
                      ? () => setDistributionMetric('menu')
                      : undefined
                }
              />
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            {(data.insights || []).map((item, idx) => (
              <div
                key={idx}
                className={`rounded-md border p-4 ${
                  item.level === 'good'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
                    : item.level === 'warning'
                      ? 'border-amber-200 bg-amber-50 text-amber-950'
                      : 'border-blue-200 bg-blue-50 text-blue-950'
                }`}
              >
                <p className="text-sm font-bold">{item.title}</p>
                <p className="mt-1 text-sm leading-6">{item.message}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel title="주문 흐름 퍼널">
              {(data.funnel || []).length === 0 ? <Empty /> : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={data.funnel}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" fontSize={11} />
                    <YAxis />
                    <Tooltip formatter={(value, name) => name === 'rate' ? percent(value) : number(value)} />
                    <Legend />
                    <Bar dataKey="count" name="세션 수" fill="#0f172a" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Panel>

            <Panel title="주문 시간과 첫 메뉴 선택 시간 분포">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={(data.duration_distribution || []).map((row, index) => ({
                  label: row.label,
                  order: row.count,
                  menu: data.menu_select_distribution?.[index]?.count || 0,
                }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="order" name="주문 완료 시간" fill="#0f172a" />
                  <Bar dataKey="menu" name="첫 메뉴 선택 시간" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel title="연령대별 완료율과 소요 시간">
              {ageRows.length === 0 ? <Empty /> : (
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={ageRows.map((row) => ({
                    age: row.age_group || '미분류',
                    completion: row.completion_rate,
                    orderSeconds: row.median_total_seconds,
                    menuSeconds: row.avg_menu_select_seconds,
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="age" />
                    <YAxis yAxisId="rate" tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                    <YAxis yAxisId="seconds" orientation="right" />
                    <Tooltip formatter={(value, name) => name === 'completion' ? percent(value) : seconds(value)} />
                    <Legend />
                    <Line yAxisId="rate" type="monotone" dataKey="completion" name="주문 완료율" stroke="#10b981" strokeWidth={2} />
                    <Line yAxisId="seconds" type="monotone" dataKey="orderSeconds" name="주문 시간 중앙값" stroke="#0f172a" />
                    <Line yAxisId="seconds" type="monotone" dataKey="menuSeconds" name="첫 메뉴 선택 평균" stroke="#f59e0b" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Panel>

            <Panel title="음성 사용 효과 비교">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={voiceCompare}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="group" />
                  <YAxis yAxisId="rate" tickFormatter={(value) => `${Math.round(value * 100)}%`} />
                  <YAxis yAxisId="seconds" orientation="right" />
                  <Tooltip formatter={(value, name) => name === 'completion' ? percent(value) : name === 'avgSeconds' ? seconds(value) : number(value)} />
                  <Legend />
                  <Bar yAxisId="rate" dataKey="completion" name="주문 완료율" fill="#10b981" />
                  <Bar yAxisId="seconds" dataKey="avgSeconds" name="평균 주문 시간" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-2 text-xs text-slate-500">
                음성 동작 실패율: {percent(data.voice.action_failure_rate)} ({data.voice.action_failures}건 실패 / {data.voice.action_successes + data.voice.action_failures}건)
              </p>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel title="메뉴 상세 이탈 신호">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">메뉴</th>
                    <th>열람</th>
                    <th>담기</th>
                    <th>닫힘</th>
                    <th>이탈률</th>
                    <th>평균 열람</th>
                  </tr>
                </thead>
                <tbody>
                  {menuFriction.length === 0 && <tr><td colSpan={6} className="px-3 py-4 text-center text-slate-400">아직 메뉴 상세 닫힘 로그가 없습니다.</td></tr>}
                  {menuFriction.map((row) => (
                    <tr key={`${row.menu_id}-${row.menu_name}`} className="border-t">
                      <td className="px-3 py-2">{row.menu_name}</td>
                      <td className="text-center">{number(row.opens)}</td>
                      <td className="text-center">{number(row.cart_adds)}</td>
                      <td className="text-center">{number(row.abandons)}</td>
                      <td className="text-right">{percent(row.abandon_rate)}</td>
                      <td className="text-right">{seconds(row.avg_open_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Panel title="미완료 세션의 마지막 행동">
              {abandonRows.length === 0 ? <Empty label="미완료 세션이 없거나 로그가 없습니다." /> : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={abandonRows} layout="vertical" margin={{ left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" width={140} dataKey="label" fontSize={11} />
                    <Tooltip formatter={(value, name) => name === 'rate' ? percent(value) : number(value)} />
                    <Bar dataKey="count" name="세션 수">
                      {abandonRows.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Panel>
          </div>

          <Panel title="세션별 분석 목록">
            <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
              <input
                value={sessionSearch}
                onChange={(event) => setSessionSearch(event.target.value)}
                placeholder="세션 UUID 검색"
                className="w-64 rounded-md border border-slate-300 px-3 py-1.5"
              />
              <select value={completionFilter} onChange={(event) => setCompletionFilter(event.target.value)} className="rounded-md border px-2 py-1.5">
                <option value="">완료 여부 전체</option>
                <option value="completed">주문 완료</option>
                <option value="incomplete">미완료</option>
              </select>
              <select value={voiceFilter} onChange={(event) => setVoiceFilter(event.target.value)} className="rounded-md border px-2 py-1.5">
                <option value="">음성 사용 전체</option>
                <option value="voice">음성 사용</option>
                <option value="touch">터치만 사용</option>
              </select>
              {(sessionSearch || completionFilter || voiceFilter) && (
                <button
                  type="button"
                  onClick={() => {
                    setSessionSearch('')
                    setCompletionFilter('')
                    setVoiceFilter('')
                  }}
                  className="rounded-md border px-3 py-1.5 font-semibold text-slate-600"
                >
                  필터 초기화
                </button>
              )}
              <span className="text-slate-500">표시 {sessions.length.toLocaleString()}건</span>
            </div>
            <p className="mb-3 text-xs text-slate-500">
              행을 클릭하면 세션의 실제 로그가 시간순으로 표시됩니다. 어떤 화면을 거쳤고, 언제 어떤 선택을 했는지 확인할 수 있습니다.
            </p>
            <div className="overflow-hidden rounded-md border border-slate-200">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-2">세션 UUID</th>
                    <th className="px-3 py-2">시작 시각</th>
                    <th className="px-3 py-2">연령대</th>
                    <th className="px-3 py-2">완료</th>
                    <th className="px-3 py-2">주문 시간</th>
                    <th className="px-3 py-2">첫 메뉴</th>
                    <th className="px-3 py-2">음성</th>
                    <th className="px-3 py-2">마지막 행동</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.length === 0 && <tr><td colSpan={8} className="px-3 py-4 text-center text-slate-400">조건에 맞는 세션이 없습니다.</td></tr>}
                  {sessions.map((row) => (
                    <tr
                      key={row.session_uuid}
                      onClick={() => setSelectedSession(row)}
                      className="cursor-pointer border-t hover:bg-amber-50/50"
                    >
                      <td className="px-3 py-2 font-mono text-xs" title={row.session_uuid}>{row.session_uuid.slice(0, 10)}...</td>
                      <td className="px-3 py-2">{formatKst(row.started_at)}</td>
                      <td className="px-3 py-2">{row.age_group || '-'}</td>
                      <td className="px-3 py-2">{row.completed ? '완료' : '미완료'}</td>
                      <td className="px-3 py-2">{seconds(row.total_seconds)}</td>
                      <td className="px-3 py-2">{seconds(row.first_menu_select_seconds)}</td>
                      <td className="px-3 py-2">{row.voice_used ? '사용' : '-'}</td>
                      <td className="px-3 py-2">{row.last_screen_name || '-'} / {row.last_action_name || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <SessionTimelineModal session={selectedSession} onClose={() => setSelectedSession(null)} />
          <DistributionModal metric={distributionMetric} data={data} onClose={() => setDistributionMetric(null)} />
        </div>
      )}
    </section>
  )
}
