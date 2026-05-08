import { useEffect, useState } from 'react'
import api from '../utils/api'

function formatPercent(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '0.0%'
  return `${(num * 100).toFixed(1)}%`
}

function buildCompactReasoning(rec, mode) {
  if (!rec?.reasoning) {
    return mode === 'CF'
      ? '장바구니와의 연관도와 현재 프로필을 함께 반영했어요.'
      : '현재 조건에서 많이 선택된 메뉴예요.'
  }

  const breakdown = rec.cf_breakdown || {}
  if (mode === 'CF') {
    if (Number(breakdown.cart_support_count) > 0) {
      return `장바구니 ${breakdown.cart_support_count}개 메뉴 근거를 반영했어요.`
    }
    return '현재 프로필과 전체 선호도를 함께 반영했어요.'
  }

  const percentMatch = rec.reasoning.match(/약 ([0-9.]+)%/)
  if (percentMatch) {
    return `현재 조건에서 선택 비중 ${percentMatch[1]}%`
  }
  return '현재 조건에서 많이 선택된 메뉴예요.'
}

function buildScoreSummary(rec, mode) {
  const breakdown = rec?.cf_breakdown || {}
  if (mode === 'CF') {
    return [
      { label: '기본', value: formatPercent(breakdown.base_score) },
      { label: '장바구니', value: formatPercent(breakdown.cart_cf_score) },
      { label: '최종', value: Number(rec?.final_score || 0).toFixed(3) },
    ]
  }

  return [
    { label: '선택 비중', value: formatPercent(rec?.popularity) },
    { label: '트렌드', value: `${Number(rec?.trend_weight || rec?.trend_score || 1).toFixed(2)}x` },
    { label: '최종', value: Number(rec?.final_score || rec?.score || 0).toFixed(3) },
  ]
}

export default function RecommendationPanel({
  gender,
  age,
  ageGroup,
  menus = [],
  cartItems = [],
  onSelectMenu,
}) {
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('CF')

  const parsedAgeForGuard = Number(age)
  const isUnderage =
    (Number.isFinite(parsedAgeForGuard) && parsedAgeForGuard < 20) ||
    ageGroup === '어린이' ||
    ageGroup === '10~19' ||
    ageGroup === 'child'

  useEffect(() => {
    if (isUnderage) {
      setRecommendations([])
      setLoading(false)
      setError(null)
      return
    }
    if (!gender || (!age && !ageGroup)) {
      setLoading(false)
      return
    }

    const fetchRecommendations = async () => {
      try {
        setLoading(true)
        setError(null)

        const genderCode =
          gender === 'male' || gender === 'M'
            ? 'M'
            : gender === 'female' || gender === 'F'
              ? 'F'
              : 'M'

        const menuNameToId = new Map(
          menus
            .filter((menu) => menu?.id && menu?.name)
            .map((menu) => [menu.name, menu.id])
        )

        const parsedAge = Number(age)
        const cartMenuIds = [...new Set(
          cartItems
            .map((item) => item.menu_id || item.menuId || item.id || menuNameToId.get(item.menuName))
            .filter(Boolean)
        )]

        let response
        let recommendationMode = 'CF'

        if (Number.isFinite(parsedAge) && parsedAge >= 15 && parsedAge <= 100) {
          try {
            response = await api.post('/api/v1/recommendations/suggest', {
              gender: genderCode,
              age: Math.round(parsedAge),
              cart_items: cartMenuIds,
              top_n: 3,
              include_trend: true,
            })
            recommendationMode = 'CF'
          } catch (cfError) {
            console.warn('CF 추천 실패, Mode A로 폴백:', cfError.message)
            recommendationMode = 'Mode A'
            response = await api.get('/api/v1/recommendations/situation', {
              params: {
                gender: genderCode,
                age: Math.round(parsedAge),
                top_n: 3,
              },
            })
          }
        } else if (ageGroup) {
          const ageGroupMap = {
            어린이: '10~19', child: '10~19',
            청년: '20~29',   young: '20~29',
            중장년: '30~39', adult: '30~39',
            중년: '40~49',   middle: '40~49',
            노년: '50+',     senior: '50+',
            '10~19': '10~19', '20~29': '20~29',
            '30~39': '30~39', '40~49': '40~49', '50+': '50+',
          }
          const ageGroupCode = ageGroupMap[ageGroup] || '20~29'
          response = await api.get('/api/v1/recommendations/situation', {
            params: { gender: genderCode, age_group: ageGroupCode, top_n: 3 },
          })
          recommendationMode = 'Mode A'
        } else {
          setRecommendations([])
          setMode('Mode A')
          return
        }

        setMode(recommendationMode)
        setRecommendations(response.data.recommendations || [])
      } catch (err) {
        console.error('추천 로드 실패:', err)
        let errorMsg = '추천을 불러올 수 없습니다'
        if (err.response?.status === 404) {
          errorMsg = `API 주소를 찾을 수 없습니다.\n상태: ${err.response.status}`
        } else if (err.response?.status === 422) {
          errorMsg = '입력값이 올바르지 않습니다.\n상태: 422 Unprocessable Entity'
        } else if (err.response?.status === 500) {
          errorMsg = `서버 오류입니다.\n상태: ${err.response.status}\n오류: ${err.response?.data?.detail || 'Unknown error'}`
        } else if (err.message === 'Network Error') {
          errorMsg = '네트워크 연결을 확인하세요.\n(localhost:8000에 연결할 수 없음)'
        } else if (err.response?.data?.detail) {
          errorMsg = err.response.data.detail
        }
        setError(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    fetchRecommendations()
  }, [gender, age, ageGroup, menus, cartItems])

  if (!gender || (!age && !ageGroup)) return null
  if (isUnderage) return null

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-4 sm:p-6 border-2 border-amber-200">
        <div className="text-center py-8">
          <div className="inline-block animate-spin">⏳</div>
          <p className="text-amber-700 mt-2 font-semibold">추천 음료 준비 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-2xl p-4 sm:p-6 border-2 border-red-200">
        <div className="text-center">
          <p className="text-red-700 font-bold mb-2">⚠️ 추천을 불러올 수 없습니다</p>
          <p className="text-red-600 text-sm whitespace-pre-wrap mb-3">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-sm bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          >
            새로고침
          </button>
        </div>
      </div>
    )
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-4 sm:p-6 border-2 border-amber-200">
        <p className="text-amber-700 text-center font-semibold">제안할 추천이 없습니다</p>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-4 sm:p-6 border-2 border-amber-200 shadow-md">
      {/* 헤더 */}
      <div className="mb-4 flex items-center gap-2">
        <span className="text-xl sm:text-2xl">✨</span>
        <h2 className="text-base sm:text-xl font-bold text-amber-900">AI 추천 음료</h2>
        <span className="text-xs bg-blue-500 text-white px-2 py-0.5 rounded font-semibold ml-auto">
          {mode}
        </span>
      </div>

      {/*
        모바일: flex + overflow-x-auto + snap-x → 가로 스크롤, 카드 단위로 snap
        sm 이상: grid grid-cols-3 → 기존 3열 레이아웃
      */}
      <div className="
        flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory
        sm:grid sm:grid-cols-3 sm:overflow-x-visible sm:pb-0
      ">
        {recommendations.map((rec, idx) => {
          const menuId = rec.menu_id || rec.id
          const menuName = rec.menu_name || rec.name
          const finalScore = rec.final_score || rec.score || 0
          const trendWeight = rec.trend_weight || rec.trend_score || 1.0
          const breakdown = rec.cf_breakdown || {}
          const compactReason = buildCompactReasoning(rec, mode)
          const scoreSummary = buildScoreSummary(rec, mode)

          return (
            <button
              key={menuId}
              onClick={() =>
                onSelectMenu && onSelectMenu(menuName, { menuId, fromRecommendation: true })
              }
              className="
                group relative
                flex-shrink-0 w-[75vw] snap-start
                sm:w-auto sm:flex-shrink
                bg-white rounded-xl p-3
                border-2 border-amber-200
                hover:border-amber-500
                active:scale-95
                transition-all duration-200
                cursor-pointer text-left
              "
            >
              <div className="absolute top-2 right-2 bg-amber-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow-sm">
                {idx + 1}
              </div>

              <h3 className="text-sm sm:text-base font-bold text-amber-900 pr-8 line-clamp-2 mb-2 sm:mb-3">
                {menuName}
              </h3>

              <p className="text-xs sm:text-sm font-medium leading-5 text-amber-800 min-h-[32px] sm:min-h-[40px]">
                {compactReason}
              </p>

              <div className="mt-2 sm:mt-3 grid grid-cols-3 gap-1 sm:gap-2">
                {scoreSummary.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-lg bg-amber-50 border border-amber-100 px-1 sm:px-2 py-1.5 sm:py-2 text-center"
                  >
                    <div className="text-[10px] sm:text-[11px] text-amber-700 font-medium truncate">{item.label}</div>
                    <div className="text-[10px] sm:text-xs font-bold text-amber-900 mt-0.5 sm:mt-1">{item.value}</div>
                  </div>
                ))}
              </div>

              {mode === 'CF' && Number(breakdown.cart_support_count) > 0 && (
                <p className="mt-1.5 sm:mt-2 text-[10px] sm:text-[11px] text-amber-700">
                  장바구니 {breakdown.cart_support_count}개 메뉴 근거 반영
                </p>
              )}

              <div className="mt-2 sm:mt-3 flex items-center justify-between text-xs text-amber-700 flex-wrap gap-1">
                <span className="px-2 py-0.5 sm:py-1 rounded-full bg-amber-100 font-semibold text-[10px] sm:text-xs">
                  {mode === 'CF' ? '장바구니 반영' : '상황 기반'}
                </span>
                {Number(trendWeight) > 1.0 && (
                  <span className="px-2 py-0.5 sm:py-1 rounded-full bg-yellow-100 text-yellow-800 font-semibold text-[10px] sm:text-xs">
                    트렌드 {Number(trendWeight).toFixed(2)}x
                  </span>
                )}
              </div>

              <div className="mt-2 sm:mt-3 pt-2 border-t border-amber-100 flex items-center justify-between text-xs text-amber-700">
                <span className="font-medium text-[10px] sm:text-sm">
                  {mode === 'CF' ? '종합 점수' : '추천 점수'}
                </span>
                <span className="font-bold text-amber-600 text-[10px] sm:text-sm">
                  {Number(finalScore).toFixed(3)}
                </span>
              </div>

              <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-amber-400 to-orange-400 opacity-0 group-hover:opacity-5 transition-opacity pointer-events-none" />
            </button>
          )
        })}
      </div>

      {/* 모바일에서 스크롤 힌트 도트 */}
      <div className="flex justify-center gap-1.5 mt-3 sm:hidden">
        {recommendations.map((_, idx) => (
          <div
            key={idx}
            className="w-1.5 h-1.5 rounded-full bg-amber-300"
          />
        ))}
      </div>

      <p className="text-xs sm:text-sm text-amber-700 mt-3 text-center font-medium">
        {mode === 'CF' ? '장바구니와 잘 어울리는 메뉴를 함께 추천합니다.' : '현재 조건에서 많이 고른 메뉴를 추천합니다.'}
      </p>
    </div>
  )
}