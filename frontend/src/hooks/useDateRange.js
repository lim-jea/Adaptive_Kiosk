import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DEFAULT_PRESET, presetToRange } from '../utils/dateRange'

// URL ?preset=&from=&to= 와 동기화되는 기간 상태.
export default function useDateRange(defaultPreset = DEFAULT_PRESET) {
  const [params, setParams] = useSearchParams()
  const initial = useCallback(() => {
    const preset = params.get('preset') || defaultPreset
    const from = params.get('from')
    const to = params.get('to')
    if (preset === 'custom' && from && to) return { preset, from, to }
    const range = presetToRange(preset)
    return { preset, ...range }
  }, [params, defaultPreset])

  const [range, setRange] = useState(initial)

  useEffect(() => {
    const next = new URLSearchParams(params)
    next.set('preset', range.preset)
    next.set('from', range.from)
    next.set('to', range.to)
    setParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range.preset, range.from, range.to])

  return [range, setRange]
}
