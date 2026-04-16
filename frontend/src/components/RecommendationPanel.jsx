// 추천 음료 패널 — Mode A (상황 기반) 추천 표시
// 사용자의 성별, 나이대, 현재 시간을 기반으로 추천된 음료 표시

import { useEffect, useState } from 'react'
import api from '../utils/api'

export default function RecommendationPanel({ gender, ageGroup, onSelectMenu }) {
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!gender || !ageGroup) {
      setLoading(false)
      return
    }

    const fetchRecommendations = async () => {
      try {
        setLoading(true)
        setError(null)

        console.log('🔍 RecommendationPanel - 원본 입력:', { gender, ageGroup })

        // gender 형식 변환 (male/female/unknown → M/F)
        const genderCode = 
          gender === 'male' || gender === 'M' ? 'M' : 
          gender === 'female' || gender === 'F' ? 'F' : 'M'

        // ageGroup 형식 변환 (한글 → API 형식)
        const ageGroupMap = {
          '어린이': '10~19',
          'child': '10~19',
          '청년': '20~29',
          'young': '20~29',
          '중장년': '30~39',
          'adult': '30~39',
          '중년': '40~49',
          'middle': '40~49',
          '노년': '50+',
          'senior': '50+',
          // 이미 올바른 형식이면 그대로 사용
          '10~19': '10~19',
          '20~29': '20~29',
          '30~39': '30~39',
          '40~49': '40~49',
          '50+': '50+',
        }
        const ageGroupCode = ageGroupMap[ageGroup] || '20~29' // 기본값

        console.log('✨ RecommendationPanel - 변환된 파라미터:', { genderCode, ageGroupCode })

        // Mode A 추천 API 호출
        const response = await api.get('/api/v1/recommendations/situation', {
          params: {
            gender: genderCode,
            age_group: ageGroupCode,
            top_n: 3,  // 3개로 제한
          },
        })

        console.log('✅ 추천 API 응답:', response.data)

        if (response.data.recommendations && response.data.recommendations.length > 0) {
          setRecommendations(response.data.recommendations)
        } else {
          setRecommendations([])
        }
      } catch (err) {
        console.error('❌ 추천 로드 실패:', err)
        console.error('에러 상세:', err.response?.data)
        
        let errorMsg = '추천을 불러올 수 없습니다'
        if (err.response?.status === 404) {
          errorMsg = `API 주소를 찾을 수 없습니다.\n상태: ${err.response.status}\n확인: 백엔드 서버가 실행 중인가요?`
        } else if (err.response?.status === 500) {
          errorMsg = `서버 오류입니다.\n상태: ${err.response.status}\n오류: ${err.response?.data?.detail || 'Unknown error'}`
        } else if (err.message === 'Network Error') {
          errorMsg = `네트워크 연결을 확인하세요.\n(localhost:5000에 연결할 수 없음)`
        } else if (err.response?.data?.detail) {
          errorMsg = err.response.data.detail
        }
        
        setError(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    fetchRecommendations()
  }, [gender, ageGroup])

  if (!gender || !ageGroup) {
    return null
  }

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border-2 border-amber-200">
        <div className="text-center py-8">
          <div className="inline-block animate-spin">⏳</div>
          <p className="text-amber-700 mt-2 font-medium">추천 음료 준비 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-2xl p-6 border-2 border-red-200">
        <div className="text-center">
          <p className="text-red-700 font-bold mb-2">⚠️ 추천을 불러올 수 없습니다</p>
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
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border-2 border-amber-200">
        <p className="text-amber-700 text-center font-medium">제안할 추천이 없습니다</p>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border-2 border-amber-200 shadow-md">
      {/* 헤더 */}
      <div className="mb-4 flex items-center gap-2">
        <span className="text-2xl">✨</span>
        <h2 className="text-xl font-bold text-amber-900">AI 추천 음료</h2>
        <span className="text-sm bg-amber-500 text-white px-3 py-1 rounded-full ml-auto font-semibold">
          {recommendations.length}개
        </span>
      </div>

      {/* 추천 음료 목록 */}
      <div className="grid grid-cols-3 gap-2">
        {recommendations.map((rec, idx) => (
          <button
            key={rec.menu_id}
            onClick={() => onSelectMenu && onSelectMenu(rec.menu_name)}
            className="
              group relative
              bg-white rounded-lg p-3 
              border-2 border-amber-200 
              hover:border-amber-500 
              active:scale-95
              transition-all duration-200
              cursor-pointer
              text-left
            "
          >
            {/* 순위 배지 */}
            <div className="absolute top-1 left-1 bg-amber-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">
              {idx + 1}
            </div>

            {/* 메뉴명 — 2줄 제한 */}
            <h3 className="text-sm font-bold text-amber-900 pr-6 line-clamp-2 mb-2">
              {rec.menu_name}
            </h3>

            {/* 통계 정보 — 컴팩트 */}
            <div className="space-y-1 text-xs text-amber-700">
              <div className="flex items-center justify-between">
                <span className="opacity-75">인기도</span>
                <span className="font-semibold">{(rec.popularity * 100).toFixed(0)}%</span>
              </div>

              <div className="flex items-center justify-between">
                <span className="opacity-75">트렌드</span>
                <span className="font-semibold px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">
                  {rec.trend_weight.toFixed(2)}x
                </span>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-amber-100">
                <span className="opacity-75 text-xs">점수</span>
                <span className="text-xs font-bold text-amber-600">
                  {rec.final_score.toFixed(3)}
                </span>
              </div>
            </div>

            {/* 호버 효과 */}
            <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-amber-400 to-orange-400 opacity-0 group-hover:opacity-5 transition-opacity pointer-events-none" />
          </button>
        ))}
      </div>

      {/* 설명 */}
      <p className="text-xs text-amber-600 mt-3 text-center">
        💡 AI 추천 (성별·나이·시간 기반). 클릭하면 선택!
      </p>
    </div>
  )
}
