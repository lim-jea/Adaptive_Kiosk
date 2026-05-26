// 결제 완료 페이지 — 주차·영수증·직원호출 + 의견 토글 설문
import { useEffect, useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'

// ── 설문 상수 ──────────────────────────────────────────────────────────────
const RATING5 = [
  { value: 1, label: '불만족' },
  { value: 2, label: '비선호' },
  { value: 3, label: '보통' },
  { value: 4, label: '선호' },
  { value: 5, label: '만족' },
]
const RATING5_COMPARE = [
  { value: 1, label: '훨씬 어려움' },
  { value: 2, label: '약간 어려움' },
  { value: 3, label: '비슷' },
  { value: 4, label: '약간 편함' },
  { value: 5, label: '훨씬 편함' },
]
const RATING5_ACCURACY = [
  { value: 1, label: '전혀 다름' },
  { value: 2, label: '다름' },
  { value: 3, label: '비슷' },
  { value: 4, label: '정확' },
  { value: 5, label: '매우 정확' },
]
const RATING5_PRIVACY = [
  { value: 1, label: '매우 거부감' },
  { value: 2, label: '약간 거부감' },
  { value: 3, label: '보통' },
  { value: 4, label: '거의 없음' },
  { value: 5, label: '전혀 없음' },
]
const RATING5_INFLUENCE = [
  { value: 1, label: '매우 방해' },
  { value: 2, label: '방해' },
  { value: 3, label: '영향 없음' },
  { value: 4, label: '도움' },
  { value: 5, label: '매우 도움' },
]
const GENDER_OPTIONS = [
  { value: 'M', label: '남' },
  { value: 'F', label: '여' },
  { value: 'no_answer', label: '응답 안 함' },
]
const STUCK_OPTIONS = [
  '얼굴 인식', '메뉴 찾기', '옵션 선택', '카트 확인',
  '음성 주문', '결제', '추천 메뉴 이해', '도움말 호출',
  '없음', '기타',
]
const EASY_MODE_OPTIONS = [
  { value: 1, label: '사용' },
  { value: 0, label: '안 함' },
  { value: null, label: '모르겠음' },
]

const RATING_QUESTIONS = [
  { id: 'q1',  title: '키오스크 이용이 전반적으로 편리했나요?',                    labels: RATING5 },
  { id: 'q2',  title: '화면 글씨 크기가 적절했나요?',                              labels: RATING5 },
  { id: 'q3',  title: '원하는 메뉴를 쉽게 찾을 수 있었나요?',                      labels: RATING5 },
  { id: 'q6',  title: '주문을 완료하기까지의 과정이 전체적으로 쉬웠나요?',          labels: RATING5 },
  { id: 'q7',  title: '다른 키오스크와 비교하면 어떠셨나요?',                       labels: RATING5_COMPARE, hasNoExperience: true },
  { id: 'q9',  title: '얼굴 인식 속도가 빠르다고 느끼셨나요?',                      labels: RATING5 },
  { id: 'q10', title: '인식된 나이대가 실제와 비슷했나요?',                         labels: RATING5_ACCURACY },
  { id: 'q12', title: '카메라로 얼굴을 촬영하는 방식에 거부감은 없으셨나요?',       labels: RATING5_PRIVACY },
  { id: 'q13', title: '추천된 메뉴가 본인 취향에 맞았나요?',                        labels: RATING5 },
  { id: 'q14', title: '추천 메뉴가 다양했나요?',                                   labels: RATING5 },
  { id: 'q17', title: '추천이 본인의 선택에 어떻게 작용했나요?',                    labels: RATING5_INFLUENCE },
]

const SECTIONS = [
  { label: '전반적 사용 경험', ids: ['q1', 'q2', 'q3', 'q6', 'q7'] },
  { label: '얼굴 인식',        ids: ['q9', 'q10', 'q12'] },
  { label: '추천',             ids: ['q13', 'q14', 'q17'] },
]

// ── 설문 서브컴포넌트 ──────────────────────────────────────────────────────
function RatingRow({ value, onChange, labels }) {
  return (
    <div className="grid grid-cols-5 gap-1.5">
      {labels.map(({ value: v, label }) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`py-2.5 rounded-xl text-xs font-semibold transition-all border-2
            ${value === v
              ? 'bg-amber-500 text-white border-amber-500 shadow-md'
              : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
        >
          <div className="text-sm font-black">{v}</div>
          <div className="text-[10px] mt-0.5 leading-tight">{label}</div>
        </button>
      ))}
    </div>
  )
}

function SingleChoice({ value, onChange, options }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all border-2
            ${value === opt.value
              ? 'bg-amber-500 text-white border-amber-500'
              : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ── main ───────────────────────────────────────────────────────────────────
export default function CompletionPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { paymentMethod, totalPrice, discountAmount = 0, discountLabel } = location.state || {}

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('completion', { payment_method: paymentMethod, total_price: totalPrice })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('completion', Date.now() - enteredAt)
    }
  }, [logger, paymentMethod, state.sessionUuid, totalPrice])

  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return
      try {
        logger.log('session', 'completion', { actionName: 'session_complete', source: 'system' })
        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, { status: 'ended', end_reason: 'completed' })
        await logger.flush()
      } catch (err) {
        console.warn('세션 종료 실패 (무시):', err.message)
      }
    }
    endSession()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [orderNum] = useState(() => Math.floor(Math.random() * 900 + 100))
  const [countdown, setCountdown] = useState(30)
  const [parkingDone, setParkingDone] = useState(false)
  const [parkingToast, setParkingToast] = useState(false)
  const [staffCalled, setStaffCalled] = useState(false)

  // 의견 토글
  const [surveyOpen, setSurveyOpen] = useState(false)
  const [surveyDone, setSurveyDone] = useState(false)
  const [surveySubmitting, setSurveySubmitting] = useState(false)

  // 설문 응답 상태
  const [respAge, setRespAge] = useState('')
  const [respGender, setRespGender] = useState(null)
  const [answers, setAnswers] = useState({})
  const [q7NoExperience, setQ7NoExperience] = useState(false)
  const [g1Choices, setG1Choices] = useState([])
  const [easyMode, setEasyMode] = useState(undefined)

  const startedAtRef = useRef(Date.now())
  const sessionUuidRef = useRef(state.sessionUuid)

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timer); handleGoHome(); return 0 }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoHome = async () => {
    logger.log('navigation', 'completion', { actionName: 'go_home', targetType: 'button', targetLabel: 'home' })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleParking = () => {
    if (parkingDone) return
    logger.log('click', 'completion', { actionName: 'parking_register', targetType: 'button', targetLabel: 'parking_register' })
    setParkingDone(true)
    setParkingToast(true)
    setTimeout(() => setParkingToast(false), 3000)
  }

  const handleStaffCall = () => {
    if (staffCalled) return
    logger.log('click', 'completion', { actionName: 'call_staff', targetType: 'button', targetLabel: 'call_staff' })
    setStaffCalled(true)
    setTimeout(() => setStaffCalled(false), 5000)
  }

  const setAnswer = (id, labels) => (v) => {
    const found = labels.find((opt) => opt.value === v)
    setAnswers((prev) => ({ ...prev, [id]: { value: v, label: found?.label || null } }))
  }

  const getEasyModeAnswer = () => {
    if (easyMode === undefined) return undefined
    const found = EASY_MODE_OPTIONS.find((opt) => opt.value === easyMode)
    return { value: easyMode, label: found?.label || null }
  }

  const toggleG1 = (opt) => {
    setG1Choices((prev) =>
      prev.includes(opt) ? prev.filter((x) => x !== opt) : [...prev, opt]
    )
  }

  const handleSurveySubmit = async () => {
    setSurveySubmitting(true)
    try {
      await api.post('/api/v1/survey/responses', {
        session_uuid: sessionUuidRef.current,
        status: 'completed',
        resp_age: respAge === '' ? null : Number(respAge),
        resp_gender: respGender,
        resp_kiosk_freq: null,
        answers: { ...answers, q22: getEasyModeAnswer() },
        multi_choices: { g1: g1Choices },
        free_texts: {},
        q7_no_experience: q7NoExperience,
        survey_snapshot: null,
        duration_ms: Date.now() - startedAtRef.current,
      })
    } catch (err) {
      console.warn('[survey] submit failed (ignored):', err.message)
    }
    setSurveyDone(true)
    setSurveySubmitting(false)
  }

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col">

      {/* 상단 성공 배너 */}
      <div className="bg-amber-500 px-4 pt-12 pb-8 text-center text-white">
        <div className="text-5xl mb-3">✅</div>
        <h1 className="text-2xl font-black mb-1">결제 완료!</h1>
        <p className="text-amber-100 text-sm">
          {paymentMethod}으로 {totalPrice?.toLocaleString()}원 결제되었어요
        </p>
        {discountAmount > 0 && (
          <p className="text-amber-200 text-xs mt-1">
            {discountLabel} 적용 · {discountAmount.toLocaleString()}원 할인
          </p>
        )}
        <div className="mt-3 inline-block bg-white/20 rounded-full px-4 py-1.5">
          <span className="text-sm font-bold">주문번호 #{orderNum}</span>
        </div>
      </div>

      <div className="flex-1 px-4 py-5 space-y-4">

        {/* 3개 버튼 한 줄 */}
        <div className="grid grid-cols-3 gap-3">
          {/* 주차 등록 */}
          <button
            onClick={handleParking}
            disabled={parkingDone}
            className={`bg-white rounded-2xl border shadow-sm py-4 flex flex-col items-center gap-1.5 transition-colors
              ${parkingDone
                ? 'border-green-200 bg-green-50 text-green-600'
                : 'border-gray-100 text-gray-500 hover:bg-gray-50'}`}
          >
            <span className="text-xl">{parkingDone ? '✅' : '🚗'}</span>
            <span className="text-xs font-semibold">{parkingDone ? '등록 완료' : '주차 등록'}</span>
          </button>

          {/* 영수증 */}
          <button className="bg-white rounded-2xl border border-gray-100 shadow-sm py-4 flex flex-col items-center gap-1.5 text-gray-500 hover:bg-gray-50 transition-colors">
            <span className="text-xl">🧾</span>
            <span className="text-xs font-semibold">영수증</span>
          </button>

          {/* 직원 호출 */}
          <button
            onClick={handleStaffCall}
            disabled={staffCalled}
            className={`bg-white rounded-2xl border shadow-sm py-4 flex flex-col items-center gap-1.5 transition-colors
              ${staffCalled
                ? 'border-amber-200 bg-amber-50 text-amber-600'
                : 'border-gray-100 text-gray-500 hover:bg-gray-50'}`}
          >
            <span className="text-xl">{staffCalled ? '📣' : '🔔'}</span>
            <span className="text-xs font-semibold">{staffCalled ? '호출 중...' : '직원 호출'}</span>
          </button>
        </div>

        {/* 의견 들려주기 토글 */}
        <div className="rounded-2xl shadow-lg border-2 border-emerald-500 overflow-hidden bg-emerald-500">
          <button
            onClick={() => !surveyDone && setSurveyOpen((o) => !o)}
            className="w-full flex items-center justify-between px-6 py-5 text-white"
          >
            <div className="flex items-center gap-4">
              <span className="text-3xl">📝</span>
              <div className="text-left">
                <p className="font-black text-xl">
                  {surveyDone ? '의견 제출 완료! 감사합니다 😊' : '의견 들려주기'}
                </p>
                {!surveyDone && (
                  <p className="text-sm font-semibold text-emerald-50 mt-1">2~3분 · 서비스 개선에 직접 반영됩니다</p>
                )}
              </div>
            </div>
            {!surveyDone && (
              <span className="text-white text-2xl font-black transition-transform duration-200"
                style={{ transform: surveyOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>
                ▾
              </span>
            )}
          </button>

          {/* 설문 본문 */}
          {surveyOpen && !surveyDone && (
            <div className="px-4 pb-5 border-t border-emerald-100 space-y-5 pt-4 bg-white">

              {/* 만 나이 */}
              <div>
                <p className="text-sm font-bold text-gray-800 mb-2">만 나이</p>
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={respAge}
                  onChange={(e) => setRespAge(e.target.value)}
                  placeholder="예: 35"
                  className="w-full border-2 border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-amber-400"
                />
              </div>

              {/* 성별 */}
              <div>
                <p className="text-sm font-bold text-gray-800 mb-2">성별</p>
                <SingleChoice value={respGender} onChange={setRespGender} options={GENDER_OPTIONS} />
              </div>

              {/* 섹션별 rating 문항 */}
              {SECTIONS.map((section) => (
                <div key={section.label}>
                  <p className="text-xs font-black text-amber-600 uppercase tracking-wider mb-3 pb-1 border-b border-amber-100">
                    {section.label}
                  </p>
                  <div className="space-y-4">
                    {section.ids.map((id) => {
                      const q = RATING_QUESTIONS.find((r) => r.id === id)
                      if (!q) return null
                      return (
                        <div key={id}>
                          <p className="text-sm font-semibold text-gray-700 mb-2">{q.title}</p>
                          {q.hasNoExperience && (
                            <label className="flex items-center gap-2 mb-2 text-xs text-gray-500 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={q7NoExperience}
                                onChange={(e) => setQ7NoExperience(e.target.checked)}
                                className="rounded"
                              />
                              비교 경험 없음
                            </label>
                          )}
                          {(!q.hasNoExperience || !q7NoExperience) && (
                            <RatingRow
                              value={answers[id]?.value}
                              onChange={setAnswer(id, q.labels)}
                              labels={q.labels}
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}

              {/* G-1 막힌 단계 */}
              <div>
                <p className="text-xs font-black text-amber-600 uppercase tracking-wider mb-3 pb-1 border-b border-amber-100">
                  막힌 단계
                </p>
                <p className="text-sm font-semibold text-gray-700 mb-2">
                  주문 중 어려움을 겪었거나 막힌 단계가 있다면 골라 주세요
                </p>
                <p className="text-xs text-gray-400 mb-2">여러 개 선택 가능</p>
                <div className="flex flex-wrap gap-2">
                  {STUCK_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => toggleG1(opt)}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold transition-all border-2
                        ${g1Choices.includes(opt)
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              {/* H-1 간편 모드 */}
              <div>
                <p className="text-xs font-black text-amber-600 uppercase tracking-wider mb-3 pb-1 border-b border-amber-100">
                  간편 모드
                </p>
                <p className="text-sm font-semibold text-gray-700 mb-2">
                  큰 글씨와 음성 안내가 강화된 "간편 모드"를 안내받으면 사용해보고 싶으신가요?
                </p>
                <SingleChoice value={easyMode} onChange={setEasyMode} options={EASY_MODE_OPTIONS} />
              </div>

              {/* 제출 */}
              <button
                onClick={handleSurveySubmit}
                disabled={surveySubmitting}
                className="w-full py-3 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-60 text-white font-bold rounded-2xl transition-colors"
              >
                {surveySubmitting ? '제출 중...' : '의견 제출하기'}
              </button>
            </div>
          )}
        </div>

      </div>

      {/* 하단 홈 버튼 + 카운트다운 */}
      <div className="px-4 pb-8 pt-2 space-y-2">
        <button
          onClick={handleGoHome}
          className="w-full py-3 bg-white border-2 border-gray-200 hover:bg-gray-50 text-gray-600 font-semibold rounded-2xl transition-colors"
        >
          처음으로
        </button>
        <p className="text-center text-xs text-gray-400 mt-2">
          {countdown}초 후 자동으로 처음 화면으로 이동합니다
        </p>
      </div>

      {/* 주차 완료 토스트 */}
      {parkingToast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 bg-green-600 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-2 z-50 animate-bounce">
          <span>🚗</span>
          <span className="font-bold text-sm">주차 등록 완료! 1시간 무료</span>
        </div>
      )}
    </div>
  )
}
