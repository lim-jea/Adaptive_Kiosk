// KST 기준 날짜 유틸. DB는 UTC로 저장된다는 가정으로 동작.
// 모든 표시는 Asia/Seoul, 모든 쿼리 파라미터는 ISO8601 (UTC `Z`)로 변환해서 송신.

const KST_OFFSET_MS = 9 * 60 * 60 * 1000

export const PRESETS = [
  { key: 'today', label: '오늘' },
  { key: '7d', label: '최근 7일' },
  { key: '30d', label: '최근 30일' },
  { key: 'thisMonth', label: '이번 달' },
  { key: 'custom', label: '사용자 지정' },
]

export const DEFAULT_PRESET = '7d'

// "YYYY-MM-DD" (KST) → KST 자정의 UTC Date
function kstDateStringToUtcDate(s, hourMin = '00:00:00') {
  // s는 KST 자정의 wall-clock. UTC로는 9시간 빠름.
  const utcMs = Date.parse(`${s}T${hourMin}+09:00`)
  return new Date(utcMs)
}

// JS Date → "YYYY-MM-DD" (KST)
export function toKstDateString(date = new Date()) {
  const shifted = new Date(date.getTime() + KST_OFFSET_MS)
  return shifted.toISOString().slice(0, 10)
}

// 프리셋에서 KST 날짜 문자열 from/to 계산. to는 "exclusive" 다음 날 00:00.
export function presetToRange(preset, today = new Date()) {
  const todayKst = toKstDateString(today)
  const d = new Date(`${todayKst}T00:00:00+09:00`)
  switch (preset) {
    case 'today':
      return { from: todayKst, to: addDays(todayKst, 1) }
    case '7d':
      return { from: addDays(todayKst, -6), to: addDays(todayKst, 1) }
    case '30d':
      return { from: addDays(todayKst, -29), to: addDays(todayKst, 1) }
    case 'thisMonth': {
      const yyyyMm = todayKst.slice(0, 7)
      return { from: `${yyyyMm}-01`, to: addDays(todayKst, 1) }
    }
    default:
      return { from: addDays(todayKst, -6), to: addDays(todayKst, 1) }
  }
}

export function addDays(kstDateStr, n) {
  const [y, m, d] = kstDateStr.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  dt.setUTCDate(dt.getUTCDate() + n)
  return dt.toISOString().slice(0, 10)
}

// 7일 이하면 hour, 그 이상은 day.
export function pickBucket({ from, to }) {
  const ms = Date.parse(`${to}T00:00:00+09:00`) - Date.parse(`${from}T00:00:00+09:00`)
  const days = Math.round(ms / (24 * 60 * 60 * 1000))
  return days <= 7 ? 'hour' : 'day'
}

// API에 보낼 파라미터 (UTC ISO 문자열).
export function rangeToQuery({ from, to, kioskId } = {}) {
  const params = {}
  if (from) params.start_date = kstDateStringToUtcDate(from).toISOString()
  if (to) params.end_date = kstDateStringToUtcDate(to).toISOString()
  if (kioskId) params.kiosk_id = kioskId
  return params
}

const KST_FORMATTER = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit',
})
const KST_DATE_FORMATTER = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  year: 'numeric', month: '2-digit', day: '2-digit',
})
const KST_HOUR_FORMATTER = new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul',
  month: '2-digit', day: '2-digit', hour: '2-digit',
})

export function formatKst(value) {
  if (!value) return ''
  return KST_FORMATTER.format(new Date(value))
}

export function formatKstDate(value) {
  if (!value) return ''
  return KST_DATE_FORMATTER.format(new Date(value))
}

export function formatBucket(value, bucket) {
  if (!value) return ''
  if (bucket === 'hour') return KST_HOUR_FORMATTER.format(new Date(value))
  return KST_DATE_FORMATTER.format(new Date(value))
}
