import { useEffect, useState } from 'react'
import api from '../utils/api'

function buildCompactReasoning(rec, mode) {
  if (!rec?.reasoning) {
    return mode === 'CF'
      ? '함께 고르기 좋은 메뉴예요.'
      : '많이 선택한 메뉴예요.'
  }

  const breakdown = rec.cf_breakdown || {}
  if (mode === 'CF') {
    if (Number(breakdown.cart_support_count) > 0) {
      return '장바구니 메뉴와 잘 어울려요.'
    }
    return '현재 조건에서 잘 맞는 메뉴예요.'
  }
  return '현재 조건에서 많이 선택된 메뉴예요.'
}

function recommendationLevel(score) {
  const value = Number(score) || 0
  if (value >= 0.65) return '매우추천'
  if (value >= 0.35) return '추천'
  return '보통'
}

function cartSupportLevel(count) {
  if (count >= 2) return '매우추천'
  if (count >= 1) return '추천'
  return '보통'
}

function buildScoreSummary(rec, mode, hasCartItems) {
  const breakdown = rec?.cf_breakdown || {}
  if (mode === 'CF') {
    return [
      { label: '추천도', value: recommendationLevel(rec?.final_score || rec?.score) },
      { label: '어울림', value: cartSupportLevel(Number(breakdown.cart_support_count)) },
      { label: '장바구니', value: hasCartItems ? '반영' : '미반영' },
    ]
  }

  return [
    { label: '추천도', value: recommendationLevel(rec?.final_score || rec?.score) },
    { label: '어울림', value: cartSupportLevel(Number(breakdown.cart_support_count)) },
    { label: '장바구니', value: hasCartItems ? '반영' : '미반영' },
  ]
}

export default function RecommendationPanel({
  gender,
  age,
  ageGroup,
  menus = [],
  cartItems = [],
  onSelectMenu,
  vertical = false,
  allowUnderage = false,
}) {
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState('CF')

  // 미성년(20세 미만) 여부 — 백엔드 normalize_age_group 이 "10~19" / "어린이" 거부.
  // 프론트에서 미리 차단해 호출 자체를 안 하고, 컴포넌트도 화면에서 숨긴다.
  const parsedAgeForGuard = Number(age)
  const isUnderage = !allowUnderage && (
    (Number.isFinite(parsedAgeForGuard) && parsedAgeForGuard < 20) ||
    ageGroup === '어린이' ||
    ageGroup === '10~19' ||
    ageGroup === 'child'
  )

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
            어린이: '10~19',
            child: '10~19',
            청년: '20~29',
            young: '20~29',
            중장년: '30~39',
            adult: '30~39',
            중년: '40~49',
            middle: '40~49',
            노년: '50+',
            senior: '50+',
            '10~19': '10~19',
            '20~29': '20~29',
            '30~39': '30~39',
            '40~49': '40~49',
            '50+': '50+',
          }
          const ageGroupCode = ageGroupMap[ageGroup] || '20~29'

          response = await api.get('/api/v1/recommendations/situation', {
            params: {
              gender: genderCode,
              age_group: ageGroupCode,
              top_n: 3,
            },
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
        console.error('에러 상세:', err.response?.data)

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

  if (!gender || (!age && !ageGroup)) {
    return null
  }

  // 미성년 — 추천 영역 자체를 화면에서 제거
  if (isUnderage) {
    return null
  }

  if (loading) {
    return (
      <div className={`bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border-2 border-amber-200 ${vertical ? 'p-4' : 'p-6'}`}>
        <div className={`text-center ${vertical ? 'py-4' : 'py-8'}`}>
          <div className="inline-block animate-spin">⏳</div>
          <p className="text-amber-700 mt-2 font-semibold text-sm">추천 음료 준비 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`bg-red-50 rounded-2xl border-2 border-red-200 ${vertical ? 'p-4' : 'p-6'}`}>
        <div className="text-center">
          <p className="text-red-700 font-bold mb-2 text-sm">⚠️ 추천을 불러올 수 없습니다</p>
          <p className="text-red-600 text-xs whitespace-pre-wrap mb-3">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-xs bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          >
            새로고침
          </button>
        </div>
      </div>
    )
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className={`bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border-2 border-amber-200 ${vertical ? 'p-4' : 'p-6'}`}>
        <p className="text-amber-700 text-center font-semibold text-sm">제안할 추천이 없습니다</p>
      </div>
    )
  }

  return (
    <div className={`bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border-2 border-amber-200 shadow-md ${vertical ? 'p-4' : 'p-6'}`}>
      <div className={`flex items-center gap-2 ${vertical ? 'mb-3' : 'mb-4'}`}>
        <span className={vertical ? 'text-lg' : 'text-2xl'}>✨</span>
        <h2 className={`font-bold text-amber-900 ${vertical ? 'text-base' : 'text-xl'}`}>
          {vertical ? 'AI 추천' : 'AI 추천 음료'}
        </h2>
      </div>

      {vertical ? (
        <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
          {recommendations.map((rec, idx) => {
            const menuId = rec.menu_id || rec.id
            const menuName = rec.menu_name || rec.name
            const compactReason = buildCompactReasoning(rec, mode)
            const scoreSummary = buildScoreSummary(rec, mode, cartItems.length > 0)

            return (
              <button
                key={menuId}
                onClick={() => onSelectMenu && onSelectMenu(menuName, { menuId, fromRecommendation: true })}
                className="group relative min-w-[220px] bg-white rounded-xl p-3 border-2 border-amber-200 hover:border-amber-500 active:scale-95 transition-all duration-200 text-left w-[78vw] max-w-[260px] lg:w-full lg:max-w-none lg:min-w-0"
              >
                <div className="flex items-start gap-2 mb-2">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-amber-500 text-white flex items-center justify-center text-xs font-bold mt-0.5">
                    {idx + 1}
                  </span>
                  <h3 className="text-sm font-bold text-amber-900 line-clamp-2 flex-1 leading-tight">
                    {menuName}
                  </h3>
                </div>
                <p className="text-xs text-amber-700 mb-2 line-clamp-2 leading-relaxed">
                  {compactReason}
                </p>
                <div className="grid grid-cols-3 gap-1 mb-2">
                  {scoreSummary.map((item) => (
                    <div key={item.label} className="rounded bg-amber-50 border border-amber-100 px-1 py-1 text-center">
                      <div className="text-[10px] text-amber-600">{item.label}</div>
                      <div className="text-[11px] font-bold text-amber-900">{item.value}</div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-semibold">
                  추천 메뉴
                  </span>
                </div>
                <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-amber-400 to-orange-400 opacity-0 group-hover:opacity-5 transition-opacity pointer-events-none" />
              </button>
            )
          })}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {recommendations.map((rec, idx) => {
            const menuId = rec.menu_id || rec.id
            const menuName = rec.menu_name || rec.name
            const finalScore = rec.final_score || rec.score || 0
            const breakdown = rec.cf_breakdown || {}
            const compactReason = buildCompactReasoning(rec, mode)
            const scoreSummary = buildScoreSummary(rec, mode, cartItems.length > 0)

            return (
              <button
                key={menuId}
                onClick={() => onSelectMenu && onSelectMenu(menuName, { menuId, fromRecommendation: true })}
                className="group relative bg-white rounded-xl p-3 border-2 border-amber-200 hover:border-amber-500 active:scale-95 transition-all duration-200 cursor-pointer text-left"
              >
                <div className="absolute top-2 right-2 bg-amber-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shadow-sm">
                  {idx + 1}
                </div>
                <h3 className="text-base font-bold text-amber-900 pr-8 line-clamp-2 mb-3">
                  {menuName}
                </h3>
                <p className="text-sm font-medium leading-5 text-amber-800 min-h-[40px]">
                  {compactReason}
                </p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {scoreSummary.map((item) => (
                    <div key={item.label} className="rounded-lg bg-amber-50 border border-amber-100 px-2 py-2 text-center">
                      <div className="text-[11px] text-amber-700 font-medium">{item.label}</div>
                      <div className="text-xs font-bold text-amber-900 mt-1">{item.value}</div>
                    </div>
                  ))}
                </div>
                {mode === 'CF' && Number(breakdown.cart_support_count) > 0 && (
                  <p className="mt-2 text-[11px] text-amber-700">
                    장바구니 메뉴와 잘 어울려요
                  </p>
                )}
                <div className="mt-3 flex items-center justify-between text-xs text-amber-700">
                  <span className="px-2 py-1 rounded-full bg-amber-100 font-semibold">
                    추천 메뉴
                  </span>
                </div>
                <div className="mt-3 pt-2 border-t border-amber-100 flex items-center justify-between text-sm text-amber-700">
                  <span className="font-medium">추천도</span>
                  <span className="font-bold text-amber-600">{recommendationLevel(finalScore)}</span>
                </div>
                <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-amber-400 to-orange-400 opacity-0 group-hover:opacity-5 transition-opacity pointer-events-none" />
              </button>
            )
          })}
        </div>
      )}

      <p className={`text-amber-700 text-center font-medium ${vertical ? 'text-xs mt-2' : 'text-sm mt-3'}`}>
        고르기 쉬운 추천 메뉴를 먼저 보여드립니다.
      </p>
    </div>
  )
}
