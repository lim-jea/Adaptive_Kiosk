// 연령대 직접 선택 페이지 — 카메라 실패 시 fallback
// 기존 LandingPage의 수동 선택 UI를 분리

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

const AGE_GROUPS = [
  { label: '어린이', emoji: '🧒', range: '0 ~ 12세',  ageGroup: '어린이', ageEst: 6  },
  { label: '청년',   emoji: '😊', range: '13 ~ 30세', ageGroup: '청년',   ageEst: 20 },
  { label: '중년',   emoji: '🙂', range: '31 ~ 60세', ageGroup: '중년',   ageEst: 45 },
  { label: '노년',   emoji: '👴', range: '61세 이후',  ageGroup: '노년',   ageEst: 65 },
]

export default function SelectAgePage() {
  const navigate = useNavigate()
  const { dispatch, ACTIONS } = useSession()
  const logger = useLogger()

  const [loading, setLoading] = useState(false)
  const [loadingGroup, setLoadingGroup] = useState(null)
  const [error, setError] = useState(null)

  const handleAgeGroupSelect = async (group) => {
    if (loading) return
    setLoading(true)
    setLoadingGroup(group.ageGroup)
    setError(null)

    try {
      logger.log('click', 'select-age', {
        actionName: 'age_group_select',
        targetType: 'button',
        targetLabel: group.ageGroup,
      })

      // 세션이 없으면 새로 생성
      let sessionUuid = sessionStorage.getItem('session_uuid')
      if (!sessionUuid) {
        const sessionRes = await api.post('/api/v1/sessions')
        sessionUuid = sessionRes.data.session_uuid
        dispatch({ type: ACTIONS.SET_SESSION, payload: { sessionUuid } })
        sessionStorage.setItem('session_uuid', sessionUuid)
        logger.log('session', 'select-age', {
          actionName: 'session_start',
          source: 'system',
          payload: { sessionUuid },
        })
        logger.flush(sessionUuid).catch(() => {})
      }

      dispatch({
        type: ACTIONS.SET_VISION,
        payload: {
          ageGroup: group.ageGroup,
          gender: 'unknown',
          ageEst: group.ageEst,
          isSimpleMode: group.ageGroup === '어린이',
        },
      })

      navigate('/order-type')
    } catch (err) {
      const status = err?.response?.status
      setError(
        status === 401 || status === 403
          ? '키오스크 인증 정보가 올바르지 않습니다.'
          : '시작할 수 없습니다. 잠시 후 다시 시도해주세요.',
      )
    } finally {
      setLoading(false)
      setLoadingGroup(null)
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(160deg, #1a0a00 0%, #3b1a08 50%, #1a0a00 100%)' }}
    >
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-10">

        {/* 로고 */}
        <div className="text-center mb-8">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center shadow-2xl mb-3 mx-auto"
            style={{ background: 'linear-gradient(135deg, #f59e0b 0%, #b45309 100%)' }}
          >
            <span className="text-3xl">☕</span>
          </div>
          <h1 className="text-2xl font-black text-white tracking-widest">BREW AI</h1>
          <p className="text-amber-400 text-xs font-medium tracking-widest mt-1">CAFÉ & ROASTERY</p>
        </div>

        <p className="text-amber-400/80 text-base font-medium text-center mb-2">
          카메라를 사용할 수 없어요
        </p>
        <p className="text-amber-600/60 text-sm text-center mb-8">
          연령대를 직접 선택해 주세요
        </p>

        {/* 에러 */}
        {error && (
          <div className="mb-4 px-4 py-3 bg-red-900/50 border border-red-700 text-red-300 rounded-xl text-sm text-center w-full max-w-sm">
            {error}
          </div>
        )}

        {/* 연령대 선택 */}
        <div className="w-full max-w-sm">
          <div className="grid grid-cols-2 gap-3">
            {AGE_GROUPS.map((group) => (
              <button
                key={group.ageGroup}
                onClick={() => handleAgeGroupSelect(group)}
                disabled={loading}
                className={`
                  flex flex-col items-center justify-center
                  py-6 px-4
                  rounded-2xl border transition-all duration-200
                  ${loadingGroup === group.ageGroup
                    ? 'border-amber-400 bg-amber-500/20 scale-95'
                    : 'border-amber-800/50 bg-white/5 hover:bg-white/10 hover:border-amber-600/60 active:scale-95'}
                  disabled:opacity-60 disabled:cursor-not-allowed
                `}
              >
                <span className="text-4xl mb-2">{group.emoji}</span>
                <span className="text-lg font-bold text-white">{group.label}</span>
                <span className="text-xs text-amber-500/60 mt-1 text-center leading-tight">{group.range}</span>
              </button>
            ))}
          </div>
        </div>

      </div>

      <div className="px-6 pb-6 text-center">
        <p className="text-xs text-amber-900/50">© BREW AI CAFÉ · 개인정보를 저장하지 않습니다</p>
      </div>
    </div>
  )
}