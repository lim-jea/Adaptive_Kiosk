import { PRESETS, addDays, presetToRange, toKstDateString } from '../../utils/dateRange'

export default function DateRangePicker({ preset, from, to, onChange }) {
  const handlePreset = (key) => {
    if (key === 'custom') {
      onChange({ preset: 'custom', from, to })
      return
    }
    const range = presetToRange(key)
    onChange({ preset: key, from: range.from, to: range.to })
  }

  const setFrom = (value) => {
    if (!value) return
    onChange({ preset: 'custom', from: value, to: to && to <= value ? addDays(value, 1) : to })
  }
  const setTo = (value) => {
    if (!value) return
    onChange({ preset: 'custom', from: from && from >= value ? addDays(value, -1) : from, to: value })
  }

  // `to`는 exclusive (다음 날 자정) → 사용자에게 보여줄 때는 `to-1일`이 자연.
  const visibleTo = to ? addDays(to, -1) : ''
  const todayKst = toKstDateString()
  const maxKst = todayKst

  return (
    <div className="flex flex-wrap items-end gap-2">
      <div className="flex gap-1">
        {PRESETS.map((p) => (
          <button
            type="button"
            key={p.key}
            onClick={() => handlePreset(p.key)}
            className={`rounded-md border px-3 py-1.5 text-xs font-semibold ${
              preset === p.key ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-slate-300 text-slate-600'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-1 text-xs text-slate-500">
        <input
          type="date"
          value={from || ''}
          max={visibleTo || maxKst}
          onChange={(e) => setFrom(e.target.value)}
          className="rounded-md border border-slate-300 px-2 py-1 text-slate-900"
        />
        <span>—</span>
        <input
          type="date"
          value={visibleTo || ''}
          min={from || ''}
          max={maxKst}
          onChange={(e) => setTo(addDays(e.target.value, 1))}
          className="rounded-md border border-slate-300 px-2 py-1 text-slate-900"
        />
      </div>
    </div>
  )
}
