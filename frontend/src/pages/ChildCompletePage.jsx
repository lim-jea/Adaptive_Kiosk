import { useEffect, useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { formatOrderDisplayNo } from '../utils/orderDisplay'
import { splitVAT } from '../utils/price'

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
  { id: 'q1',  title: '키오스크 이용이 전반적으로 편리했나요?',                  labels: RATING5 },
  { id: 'q2',  title: '화면 글씨 크기가 적절했나요?',                            labels: RATING5 },
  { id: 'q3',  title: '원하는 메뉴를 쉽게 찾을 수 있었나요?',                    labels: RATING5 },
  { id: 'q6',  title: '주문을 완료하기까지의 과정이 전체적으로 쉬웠나요?',        labels: RATING5 },
  { id: 'q7',  title: '다른 키오스크와 비교하면 어떠셨나요?',                     labels: RATING5_COMPARE, hasNoExperience: true },
  { id: 'q9',  title: '얼굴 인식 속도가 빠르다고 느끼셨나요?',                    labels: RATING5 },
  { id: 'q10', title: '인식된 나이대가 실제와 비슷했나요?',                       labels: RATING5_ACCURACY },
  { id: 'q12', title: '카메라로 얼굴을 촬영하는 방식에 거부감은 없으셨나요?',     labels: RATING5_PRIVACY },
  { id: 'q13', title: '추천된 메뉴가 본인 취향에 맞았나요?',                      labels: RATING5 },
  { id: 'q14', title: '추천 메뉴가 다양했나요?',                                 labels: RATING5 },
  { id: 'q17', title: '추천이 본인의 선택에 어떻게 작용했나요?',                  labels: RATING5_INFLUENCE },
]

const SECTIONS = [
  { label: '전반적 사용 경험', ids: ['q1', 'q2', 'q3', 'q6', 'q7'] },
  { label: '얼굴 인식',        ids: ['q9', 'q10', 'q12'] },
  { label: '추천',             ids: ['q13', 'q14', 'q17'] },
]

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
              ? 'bg-sky-500 text-white border-sky-500 shadow-md'
              : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'}`}
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
              ? 'bg-sky-500 text-white border-sky-500'
              : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export default function ChildCompletePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { paymentMethod, totalPrice, totalCount, orderUuid } = location.state || {}
  const vat = splitVAT(totalPrice)

  const [orderNum] = useState(() => formatOrderDisplayNo(orderUuid) || String(Math.floor(Math.random() * 9000 + 1000)))
  const [surveyOpen, setSurveyOpen] = useState(false)
  const [surveyDone, setSurveyDone] = useState(false)
  const [surveySubmitting, setSurveySubmitting] = useState(false)

  const [respAge, setRespAge] = useState('')
  const [respGender, setRespGender] = useState(null)
  const [answers, setAnswers] = useState({})
  const [q7NoExperience, setQ7NoExperience] = useState(false)
  const [g1Choices, setG1Choices] = useState([])
  const [easyMode, setEasyMode] = useState(undefined)

  const startedAtRef = useRef(Date.now())
  const sessionUuidRef = useRef(state.sessionUuid)

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('child_complete', { payment_method: paymentMethod, total_price: totalPrice })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('child_complete', Date.now() - enteredAt)
    }
  }, [logger, state.sessionUuid, paymentMethod, totalPrice])

  useEffect(() => {
    const endSession = async () => {
      if (!state.sessionUuid) return
      try {
        logger.log('session', 'child_complete', { actionName: 'session_complete', source: 'system' })
        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, { status: 'ended', end_reason: 'completed' })
        await logger.flush()
      } catch (err) {
        console.warn('세션 종료 실패:', err.message)
      }
    }
    endSession()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoHome = async () => {
    logger.log('navigation', 'child_complete', { actionName: 'go_home', targetType: 'button', targetLabel: 'home' })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
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
    <div className="min-h-screen flex flex-col items-center px-5 py-10" style={{ background: '#ECFEFF' }}>

      <div className="text-7xl mb-5">🎉</div>
      <h1 className="text-4xl font-black text-gray-800 mb-3">주문 완료!</h1>
      <p className="text-lg text-gray-500 mb-8">{paymentMethod}으로 결제되었어요</p>

      {/* 주문번호 */}
      <div className="bg-white rounded-[32px] shadow-md border-4 border-sky-200 px-10 py-8 w-full max-w-sm text-center mb-6">
        <p className="text-xl font-bold text-gray-400 mb-2">주문번호</p>
        <p className="text-7xl font-black text-sky-500">#{orderNum}</p>
        <p className="text-base text-gray-400 mt-3">번호가 나오면 음료를 받아가세요</p>
      </div>

      {/* 주문 내역 */}
      <div className="bg-white rounded-3xl border-2 border-sky-100 shadow-sm w-full max-w-sm px-6 py-5 mb-6">
        <p className="text-lg font-black text-gray-500 mb-3">주문 내역</p>
        <div className="divide-y">
          {(state.cart || []).map((item) => {
            const optionLabel = (item.optionLabels || []).join(' · ')
            return (
              <div key={item.cartItemId} className="py-3 flex justify-between gap-3">
                <div>
                  <p className="text-xl font-black text-gray-800">
                    {item.displayName}
                    <span className="text-sky-500 ml-2">×{item.quantity}</span>
                  </p>
                  {optionLabel && <p className="text-sm text-gray-400 mt-1">{optionLabel}</p>}
                </div>
                <p className="text-lg font-bold text-gray-700">
                  {(item.unitPrice * item.quantity).toLocaleString()}원
                </p>
              </div>
            )
          })}
        </div>
        <div className="border-t pt-3 mt-2 space-y-1">
          <div className="flex justify-between text-xs text-gray-400">
            <span>공급가액</span>
            <span>{vat.net.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between text-xs text-gray-400">
            <span>부가세 (10%)</span>
            <span>{vat.tax.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center pt-1">
            <span className="text-lg font-bold text-gray-600">총 {totalCount}개</span>
            <span className="text-2xl font-black text-sky-600">{totalPrice?.toLocaleString()}원</span>
          </div>
        </div>
      </div>

      {/* 의견 들려주기 토글 */}
      <div className="rounded-3xl border-2 border-emerald-500 shadow-lg w-full max-w-sm mb-6 overflow-hidden bg-emerald-500">
        <button
          onClick={() => !surveyDone && setSurveyOpen((o) => !o)}
          className="w-full flex items-center justify-between px-6 py-5 text-white"
        >
          <div className="text-left">
            <p className="font-black text-white text-2xl">
              {surveyDone ? '의견 제출 완료! 감사해요 😊' : '의견 남기기'}
            </p>
            {!surveyDone && (
              <p className="text-base font-semibold text-emerald-50 mt-1">2~3분 · 더 좋은 키오스크를 만드는 데 써요</p>
            )}
          </div>
          {!surveyDone && (
            <span
              className="text-white text-2xl font-black transition-transform duration-200"
              style={{ transform: surveyOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              ▾
            </span>
          )}
        </button>

        {surveyOpen && !surveyDone && (
          <div className="px-5 pb-6 border-t border-emerald-100 space-y-5 pt-4 bg-white">

            <div>
              <p className="text-sm font-bold text-gray-800 mb-2">만 나이</p>
              <input
                type="number"
                min="1"
                max="120"
                value={respAge}
                onChange={(e) => setRespAge(e.target.value)}
                placeholder="예: 12"
                className="w-full border-2 border-sky-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-sky-400"
              />
            </div>

            <div>
              <p className="text-sm font-bold text-gray-800 mb-2">성별</p>
              <SingleChoice value={respGender} onChange={setRespGender} options={GENDER_OPTIONS} />
            </div>

            {SECTIONS.map((section) => (
              <div key={section.label}>
                <p className="text-xs font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
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
                          <RatingRow value={answers[id]?.value} onChange={setAnswer(id, q.labels)} labels={q.labels} />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}

            <div>
              <p className="text-xs font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
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
                        ? 'bg-sky-500 text-white border-sky-500'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
                간편 모드
              </p>
              <p className="text-sm font-semibold text-gray-700 mb-2">
                큰 글씨와 음성 안내가 강화된 "간편 모드"를 안내받으면 사용해보고 싶으신가요?
              </p>
              <SingleChoice value={easyMode} onChange={setEasyMode} options={EASY_MODE_OPTIONS} />
            </div>

            <button
              onClick={handleSurveySubmit}
              disabled={surveySubmitting}
              className="w-full py-3 bg-sky-500 hover:bg-sky-600 disabled:opacity-60 text-white font-bold rounded-2xl transition-colors"
            >
              {surveySubmitting ? '제출 중...' : '의견 제출하기'}
            </button>
          </div>
        )}
      </div>

      {/* 홈 버튼 */}
      <button
        onClick={handleGoHome}
        className="w-full max-w-sm py-6 bg-sky-500 hover:bg-sky-600 text-white font-black text-2xl rounded-3xl shadow-lg active:scale-95 transition-all"
      >
        처음으로 돌아가기
      </button>

    </div>
  )
}
