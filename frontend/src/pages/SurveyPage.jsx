// 설문 페이지 — 결제 완료 또는 키오스크 세션 종료 후 노출.
// 한 페이지 세로 스크롤 형태. 우측 상단 "건너뛰기" / 하단 "제출하기".
// 답변 입력 시 디바운스 자동 저장 (status='partial'), 떠날 때 best-effort 동기 저장.
// 분기: q18(음성 사용)=1 일 때만 q19-q21, e4 노출.

import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { getSessionToken } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

// 5단계 만족 라벨 (사용자 합의)
const RATING5 = [
  { value: 1, label: '불만족' },
  { value: 2, label: '비선호' },
  { value: 3, label: '보통' },
  { value: 4, label: '선호' },
  { value: 5, label: '만족' },
]

// 카메라 거부감 (q12) 만 별도 라벨
const RATING5_PRIVACY = [
  { value: 1, label: '매우 거부감' },
  { value: 2, label: '약간 거부감' },
  { value: 3, label: '보통' },
  { value: 4, label: '거의 없음' },
  { value: 5, label: '전혀 없음' },
]

// q7 다른 키오스크 비교 — 5단계 비교 라벨
const RATING5_COMPARE = [
  { value: 1, label: '훨씬 어려움' },
  { value: 2, label: '약간 어려움' },
  { value: 3, label: '비슷' },
  { value: 4, label: '약간 편함' },
  { value: 5, label: '훨씬 편함' },
]

// q10 나이 인식 정확성 — 5단계 정확성 라벨
const RATING5_ACCURACY = [
  { value: 1, label: '전혀 다름' },
  { value: 2, label: '다름' },
  { value: 3, label: '비슷' },
  { value: 4, label: '정확' },
  { value: 5, label: '매우 정확' },
]

// q17 추천 영향 — 5단계 영향 라벨
const RATING5_INFLUENCE = [
  { value: 1, label: '매우 방해' },
  { value: 2, label: '방해' },
  { value: 3, label: '영향 없음' },
  { value: 4, label: '도움' },
  { value: 5, label: '매우 도움' },
]

// 객관식 5단계 항목 (대부분 RATING5, 일부는 의미에 맞는 5단계 라벨)
const RATING_QUESTIONS = [
  { id: 'q1', section: 'B', title: '키오스크 이용이 전반적으로 편리했나요?', labels: RATING5 },
  { id: 'q2', section: 'B', title: '화면 글씨 크기가 적절했나요?', labels: RATING5 },
  { id: 'q3', section: 'B', title: '원하는 메뉴를 쉽게 찾을 수 있었나요?', labels: RATING5 },
  { id: 'q4', section: 'B', title: '옵션을 고르는 과정이 편했나요?', labels: RATING5 },
  { id: 'q5', section: 'B', title: '결제 과정이 편리했나요?', labels: RATING5 },
  { id: 'q6', section: 'B', title: '주문을 완료하기까지의 과정이 전체적으로 쉬웠나요?', labels: RATING5 },
  { id: 'q7', section: 'B', title: '본 키오스크를 이전에 써본 다른 키오스크와 비교하면 어떠셨나요?', labels: RATING5_COMPARE, hasNoExperience: true },
  { id: 'q8', section: 'B', title: '전반적인 만족도', labels: RATING5, freeTextKey: 'b8_reason', freeTextHint: '이 점수를 주신 가장 큰 이유 (선택)' },
  { id: 'q9', section: 'C', title: '얼굴 인식 속도가 빠르다고 느끼셨나요?', labels: RATING5 },
  { id: 'q10', section: 'C', title: '인식된 나이대가 실제와 비슷했나요?', labels: RATING5_ACCURACY },
  { id: 'q12', section: 'C', title: '카메라로 얼굴을 촬영하는 방식에 거부감은 없으셨나요?', labels: RATING5_PRIVACY },
  { id: 'q13', section: 'D', title: '추천된 메뉴가 본인 취향에 맞았나요?', labels: RATING5, freeTextKey: 'd1_reason', freeTextHint: '그렇게 느끼신 이유 (선택)' },
  { id: 'q14', section: 'D', title: '추천 메뉴가 다양했나요?', labels: RATING5 },
  { id: 'q15', section: 'D', title: '추천된 메뉴가 왜 추천되었는지 이해할 수 있었나요?', labels: RATING5 },
  { id: 'q16', section: 'D', title: '추천을 무시하고 다른 메뉴를 고르는 게 쉬웠나요?', labels: RATING5 },
  { id: 'q17', section: 'D', title: '추천이 본인의 선택에 어떻게 작용했나요?', labels: RATING5_INFLUENCE },
]

// 음성 분기 5단계 (q18=1일 때만)
const VOICE_RATING_QUESTIONS = [
  { id: 'q19', section: 'E', title: '음성 인식이 본인의 말을 잘 알아들었나요?', labels: RATING5 },
  { id: 'q20', section: 'E', title: '음성 응답 속도가 적절했나요?', labels: RATING5 },
  { id: 'q21', section: 'E', title: '음성 주문이 전반적으로 편리했나요?', labels: RATING5 },
]

// 단일 선택 항목 (분류형 — 5단계 척도가 부자연스러운 항목만).
// titlePrefix 는 본문에서 보일 라벨 (예: "Q11", "H-1"). 본문은 SingleQuestionCard 로 자동 렌더링.
const SINGLE_QUESTIONS = {
  q11: {
    titlePrefix: 'Q11',
    title: '인식된 성별이 정확했나요?',
    options: [
      { value: 1, label: '정확' },
      { value: 0, label: '다름' },
    ],
  },
  q18: {
    titlePrefix: 'Q18',
    title: '음성 주문을 사용해 보셨나요?',
    options: [
      { value: 1, label: '예' },
      { value: 0, label: '아니오' },
    ],
  },
  q22: {
    titlePrefix: 'H-1',
    title: '큰 글씨와 음성 안내가 강화된 "간편 모드"를 안내받으면 사용해보고 싶으신가요?',
    options: [
      { value: 1, label: '사용' },
      { value: 0, label: '안 함' },
      { value: null, label: '모르겠음' },
    ],
  },
}

const MULTI_OPTIONS_DESIGN = [
  '버튼 크기', '버튼 색상', '글씨 가독성', '아이콘·이모지',
  '카테고리 분류', '메뉴 설명', '메뉴 사진', '화면 배치',
  '추천 카드 디자인', '기타',
]
const MULTI_OPTIONS_STUCK = [
  '얼굴 인식', '메뉴 찾기', '옵션 선택', '카트 확인',
  '음성 주문', '결제', '추천 메뉴 이해', '도움말 호출',
  '없음', '기타',
]

const GENDER_OPTIONS = [
  { value: 'M', label: '남' },
  { value: 'F', label: '여' },
  { value: 'no_answer', label: '응답하지 않음' },
]
const FREQ_OPTIONS = [
  { value: 'rare', label: '거의 없음' },
  { value: 'sometimes', label: '가끔' },
  { value: 'often', label: '자주' },
]

// ── helpers ──────────────────────────────────────────────────────────────
function SectionTitle({ id, children }) {
  return (
    <h2 id={id} className="text-xl font-black text-amber-700 mt-8 mb-3 pb-2 border-b-2 border-amber-200">
      {children}
    </h2>
  )
}

function QuestionCard({ title, hint, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 px-4 py-4 mb-3">
      <p className="text-base font-bold text-gray-800 mb-3">{title}</p>
      {hint && <p className="text-xs text-gray-400 mb-3 -mt-2">{hint}</p>}
      {children}
    </div>
  )
}

function RatingRow({ value, onChange, labels }) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {labels.map(({ value: v, label }) => {
        const active = value === v
        return (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className={`py-3 rounded-xl text-sm font-semibold transition-all border-2
              ${active
                ? 'bg-amber-500 text-white border-amber-500 shadow-md'
                : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
          >
            <div className="text-base font-black">{v}</div>
            <div className="text-[11px] mt-0.5 leading-tight">{label}</div>
          </button>
        )
      })}
    </div>
  )
}

function SingleChoice({ value, onChange, options }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt, i) => {
        const active = value === opt.value
        return (
          <button
            key={i}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition-all border-2
              ${active
                ? 'bg-amber-500 text-white border-amber-500'
                : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

function MultiChoice({ values, onToggle, options }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = (values || []).includes(opt)
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onToggle(opt)}
            className={`px-3 py-2 rounded-xl text-sm font-semibold transition-all border-2
              ${active
                ? 'bg-amber-500 text-white border-amber-500'
                : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
          >
            {opt}
          </button>
        )
      })}
    </div>
  )
}

function NpsRow({ value, onChange }) {
  return (
    <div className="grid grid-cols-11 gap-1">
      {Array.from({ length: 11 }).map((_, i) => {
        const active = value === i
        return (
          <button
            key={i}
            type="button"
            onClick={() => onChange(i)}
            className={`py-2 rounded-lg text-sm font-bold transition-all border-2
              ${active
                ? 'bg-amber-500 text-white border-amber-500'
                : 'bg-white text-gray-600 border-gray-200 hover:border-amber-300'}`}
          >
            {i}
          </button>
        )
      })}
    </div>
  )
}

function FreeText({ value, onChange, placeholder }) {
  return (
    <textarea
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={3}
      className="w-full px-3 py-2 rounded-xl border-2 border-gray-200 focus:border-amber-400 outline-none text-sm resize-none"
    />
  )
}

// ── main page ─────────────────────────────────────────────────────────────
export default function SurveyPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()

  const [respAge, setRespAge] = useState('')
  const [respGender, setRespGender] = useState(null)
  const [respKioskFreq, setRespKioskFreq] = useState(null)

  const [answers, setAnswers] = useState({})  // { q1: {value, label}, ... }
  const [multiChoices, setMultiChoices] = useState({ f1: [], f2: [], g1: [] })
  const [freeTexts, setFreeTexts] = useState({})
  const [q7NoExperience, setQ7NoExperience] = useState(false)

  const startedAtRef = useRef(Date.now())
  const isFinalizedRef = useRef(false)
  const sessionUuidRef = useRef(state.sessionUuid)
  useEffect(() => { sessionUuidRef.current = state.sessionUuid }, [state.sessionUuid])

  // 진입 시 페이지 최상단으로 — 직전 페이지(CompletionPage) 의 스크롤 위치가 이어지지 않도록.
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [])

  const usedVoice = answers.q18?.value === 1

  // 객관식 응답 setter — 라벨까지 함께 저장
  const setRating = (id, labels) => (v) => {
    const found = labels.find((opt) => opt.value === v)
    setAnswers((prev) => ({ ...prev, [id]: { value: v, label: found?.label || null } }))
  }
  const setSingle = (id) => (v) => {
    const opt = SINGLE_QUESTIONS[id].options.find((o) => o.value === v)
    setAnswers((prev) => ({ ...prev, [id]: { value: v, label: opt?.label || null } }))
  }
  const toggleMulti = (key) => (opt) => {
    setMultiChoices((prev) => {
      const cur = prev[key] || []
      const next = cur.includes(opt) ? cur.filter((o) => o !== opt) : [...cur, opt]
      return { ...prev, [key]: next }
    })
  }
  const setText = (key) => (v) => {
    setFreeTexts((prev) => ({ ...prev, [key]: v }))
  }

  // SINGLE_QUESTIONS 자동 렌더링 — q11/q18/q22 가 같은 패턴이라 헬퍼로 통합.
  const renderSingleQuestion = (id) => {
    const def = SINGLE_QUESTIONS[id]
    if (!def) return null
    return (
      <QuestionCard title={`${def.titlePrefix}. ${def.title}`}>
        <SingleChoice
          value={answers[id]?.value}
          onChange={setSingle(id)}
          options={def.options}
        />
      </QuestionCard>
    )
  }

  // ── 자동 저장 (디바운스 2000ms) ──
  const buildPayload = (status) => ({
    session_uuid: sessionUuidRef.current,
    status,
    resp_age: respAge === '' ? null : Number(respAge),
    resp_gender: respGender,
    resp_kiosk_freq: respKioskFreq,
    answers,
    multi_choices: multiChoices,
    free_texts: freeTexts,
    q7_no_experience: q7NoExperience,
    survey_snapshot: null,  // 백엔드가 코드북을 자동 첨부
    duration_ms: Date.now() - startedAtRef.current,
  })

  // beforeunload handler 가 빈 deps 로 등록되어 첫 렌더 클로저를 잡으므로,
  // ref 로 최신 buildPayload 를 미러링해 stale closure 를 회피한다.
  const buildPayloadRef = useRef(buildPayload)
  useEffect(() => { buildPayloadRef.current = buildPayload })

  // 디바운스 2000ms — 응답 한 번에 평균 2~4회 호출. 페이지 이탈 시 keepalive fetch 로 추가 안전망.
  const saveDebouncedRef = useRef(null)
  useEffect(() => {
    if (!sessionUuidRef.current || isFinalizedRef.current) return
    if (saveDebouncedRef.current) clearTimeout(saveDebouncedRef.current)
    saveDebouncedRef.current = setTimeout(() => {
      // 종결(submit/skip) 직후 디바운스가 발화하지 않도록 콜백 안에서도 한 번 더 잠금 확인.
      if (isFinalizedRef.current) return
      api.post('/api/v1/survey/responses', buildPayload('partial')).catch((err) => {
        console.warn('[survey] partial save failed (ignored):', err.message)
      })
    }, 2000)
    return () => { if (saveDebouncedRef.current) clearTimeout(saveDebouncedRef.current) }
  }, [respAge, respGender, respKioskFreq, answers, multiChoices, freeTexts, q7NoExperience]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── 페이지 떠날 때 best-effort 저장 ──
  useEffect(() => {
    const handler = () => {
      if (isFinalizedRef.current || !sessionUuidRef.current) return
      try {
        // ref 를 통해 항상 최신 응답 상태를 직렬화 (빈 응답으로 덮어쓰는 사고 방지).
        const payload = JSON.stringify(buildPayloadRef.current('partial'))
        const baseURL = api.defaults.baseURL || ''
        const token = getSessionToken()
        if (!token) return
        const headers = {
          'Content-Type': 'application/json',
          'X-Session-Token': token,
        }
        if (sessionUuidRef.current) {
          headers['X-Session-UUID'] = sessionUuidRef.current
        }
        fetch(`${baseURL}/api/v1/survey/responses`, {
          method: 'POST',
          headers,
          body: payload,
          keepalive: true,
        }).catch(() => {})
      } catch { /* ignore */ }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [])

  const handleSkip = async () => {
    isFinalizedRef.current = true
    if (sessionUuidRef.current) {
      try {
        await api.post('/api/v1/survey/responses', buildPayload('skipped'))
      } catch (err) {
        console.warn('[survey] skip save failed (ignored):', err.message)
      }
    }
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleSubmit = async () => {
    isFinalizedRef.current = true
    if (sessionUuidRef.current) {
      try {
        await api.post('/api/v1/survey/responses', buildPayload('completed'))
      } catch (err) {
        console.warn('[survey] complete save failed (ignored):', err.message)
      }
    }
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true, state: { surveyCompleted: true } })
  }

  // 진행률 계산 (필수 문항 응답 비율, 시각적 안내 용도)
  const requiredQuestions = useMemo(() => {
    const ids = [
      ...RATING_QUESTIONS.map((q) => q.id),
      ...Object.keys(SINGLE_QUESTIONS),
      'q23',
    ]
    if (usedVoice) ids.push(...VOICE_RATING_QUESTIONS.map((q) => q.id))
    return ids
  }, [usedVoice])
  // q7 은 "경험 없음" 체크 시 응답한 것으로 간주
  const answeredCount = requiredQuestions.filter((id) => {
    if (id === 'q7' && q7NoExperience) return true
    return answers[id] !== undefined
  }).length
  const progressPct = Math.round((answeredCount / requiredQuestions.length) * 100)

  // 세션 없는 상태로 진입 시 — 테스트 환경 안내
  const hasSession = !!sessionUuidRef.current

  return (
    <div className="min-h-screen bg-amber-50">
      {/* 상단 바 */}
      <div className="bg-white shadow-sm sticky top-0 z-30">
        <div className="px-4 py-3 flex items-center justify-between max-w-3xl mx-auto">
          <div>
            <p className="text-base font-black text-gray-800">의견을 들려주세요</p>
            <p className="text-xs text-gray-400 mt-0.5">
              약 4~5분 · 익명 처리 · 진행률 {progressPct}%
            </p>
          </div>
          <button
            type="button"
            onClick={handleSkip}
            className="px-4 py-2 rounded-xl text-sm font-bold text-gray-500 bg-gray-100 hover:bg-gray-200 transition-colors"
          >
            건너뛰기
          </button>
        </div>
        {/* 진행률 바 */}
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-amber-500 transition-all duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6">
        {!hasSession && (
          <div className="bg-yellow-50 border-2 border-yellow-300 rounded-2xl px-4 py-3 mb-4 text-sm">
            <p className="font-bold text-yellow-700">⚠️ 세션 정보가 없습니다 (테스트 모드)</p>
            <p className="text-yellow-600 text-xs mt-1">설문 응답이 백엔드에 저장되지 않습니다. 정상 흐름은 결제 완료 → 의견 들려주기 입니다.</p>
          </div>
        )}

        <p className="text-sm text-gray-600 leading-relaxed mb-6">
          본 키오스크는 카메라로 얼굴을 인식해 나이·성별에 맞는 화면을 자동으로 보여주고, 음성 주문과 AI 메뉴 추천을 제공합니다. 여러분의 의견이 더 편리한 키오스크를 만드는 데 직접 반영됩니다.
        </p>

        {/* A. 응답자 정보 */}
        <SectionTitle id="A">A. 응답자 정보</SectionTitle>

        <QuestionCard title="A-1. 만 나이를 적어 주세요">
          <input
            type="number"
            min={0}
            max={120}
            value={respAge}
            onChange={(e) => setRespAge(e.target.value)}
            placeholder="예: 28"
            className="w-32 px-3 py-2.5 rounded-xl border-2 border-gray-200 focus:border-amber-400 outline-none text-sm font-semibold"
          />
          <span className="ml-2 text-sm text-gray-400">세</span>
        </QuestionCard>

        <QuestionCard title="A-2. 성별">
          <SingleChoice value={respGender} onChange={setRespGender} options={GENDER_OPTIONS} />
        </QuestionCard>

        <QuestionCard title="A-3. 평소 키오스크(맥도날드·스타벅스 등)를 얼마나 사용하시나요?">
          <SingleChoice value={respKioskFreq} onChange={setRespKioskFreq} options={FREQ_OPTIONS} />
        </QuestionCard>

        {/* B. 전반적 사용 경험 */}
        <SectionTitle id="B">B. 전반적 사용 경험</SectionTitle>
        <p className="text-xs text-gray-500 mb-3">아래 5단계는 모두 ① 불만족 ② 비선호 ③ 보통 ④ 선호 ⑤ 만족 입니다.</p>

        {RATING_QUESTIONS.filter((q) => q.section === 'B').map((q) => (
          <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
            <div className={q.id === 'q7' && q7NoExperience ? 'opacity-40 pointer-events-none' : ''}>
              <RatingRow
                value={answers[q.id]?.value}
                onChange={setRating(q.id, q.labels)}
                labels={q.labels}
              />
            </div>
            {q.id === 'q7' && (
              <label className="mt-3 flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={q7NoExperience}
                  onChange={(e) => {
                    const checked = e.target.checked
                    setQ7NoExperience(checked)
                    if (checked) {
                      // 체크 시 q7 응답값 초기화
                      setAnswers((prev) => {
                        const next = { ...prev }
                        delete next.q7
                        return next
                      })
                    }
                  }}
                  className="w-4 h-4"
                />
                다른 키오스크 사용 경험 없음
              </label>
            )}
            {q.freeTextKey && (
              <div className="mt-3">
                <FreeText
                  value={freeTexts[q.freeTextKey]}
                  onChange={setText(q.freeTextKey)}
                  placeholder={q.freeTextHint}
                />
              </div>
            )}
          </QuestionCard>
        ))}

        {/* C. 얼굴 인식 — q9, q10(5단계), q11(분류), q12(5단계) 순 */}
        <SectionTitle id="C">C. 얼굴 인식</SectionTitle>

        {RATING_QUESTIONS.filter((q) => q.id === 'q9').map((q) => (
          <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
            <RatingRow value={answers[q.id]?.value} onChange={setRating(q.id, q.labels)} labels={q.labels} />
          </QuestionCard>
        ))}

        {RATING_QUESTIONS.filter((q) => q.id === 'q10').map((q) => (
          <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
            <RatingRow value={answers[q.id]?.value} onChange={setRating(q.id, q.labels)} labels={q.labels} />
          </QuestionCard>
        ))}

        {renderSingleQuestion('q11')}

        {RATING_QUESTIONS.filter((q) => q.id === 'q12').map((q) => (
          <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
            <RatingRow value={answers[q.id]?.value} onChange={setRating(q.id, q.labels)} labels={q.labels} />
          </QuestionCard>
        ))}

        {/* D. 추천 */}
        <SectionTitle id="D">D. AI 메뉴 추천</SectionTitle>

        {RATING_QUESTIONS.filter((q) => q.section === 'D').map((q) => (
          <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
            <RatingRow value={answers[q.id]?.value} onChange={setRating(q.id, q.labels)} labels={q.labels} />
            {q.freeTextKey && (
              <div className="mt-3">
                <FreeText
                  value={freeTexts[q.freeTextKey]}
                  onChange={setText(q.freeTextKey)}
                  placeholder={q.freeTextHint}
                />
              </div>
            )}
          </QuestionCard>
        ))}

        {/* E. 음성 주문 */}
        <SectionTitle id="E">E. 음성 주문</SectionTitle>

        {renderSingleQuestion('q18')}

        {usedVoice && (
          <>
            {VOICE_RATING_QUESTIONS.map((q) => (
              <QuestionCard key={q.id} title={`${q.id.toUpperCase()}. ${q.title}`}>
                <RatingRow value={answers[q.id]?.value} onChange={setRating(q.id, q.labels)} labels={q.labels} />
              </QuestionCard>
            ))}
            <QuestionCard title="음성 주문에 대한 의견 (선택)">
              <FreeText
                value={freeTexts.e4}
                onChange={setText('e4')}
                placeholder="음성 주문에 대해 의견이 있다면 자유롭게 적어주세요"
              />
            </QuestionCard>
          </>
        )}

        {/* F. 디자인 */}
        <SectionTitle id="F">F. 디자인</SectionTitle>

        <QuestionCard title="F-1. 마음에 들었던 부분을 모두 골라 주세요" hint="여러 개 선택 가능">
          <MultiChoice
            values={multiChoices.f1}
            onToggle={toggleMulti('f1')}
            options={MULTI_OPTIONS_DESIGN}
          />
        </QuestionCard>

        <QuestionCard title="F-2. 개선되었으면 하는 부분을 골라 주세요" hint="여러 개 선택 가능">
          <MultiChoice
            values={multiChoices.f2}
            onToggle={toggleMulti('f2')}
            options={MULTI_OPTIONS_DESIGN}
          />
        </QuestionCard>

        <QuestionCard title="F-3. 디자인 자유 의견 (선택)">
          <FreeText
            value={freeTexts.f3}
            onChange={setText('f3')}
            placeholder="디자인에 대해 자유롭게 의견을 적어주세요"
          />
        </QuestionCard>

        {/* G. 막힌 단계 */}
        <SectionTitle id="G">G. 막힌 단계</SectionTitle>

        <QuestionCard title="G-1. 주문 중 어려움을 겪었거나 막힌 단계가 있다면 모두 골라 주세요" hint="여러 개 선택 가능">
          <MultiChoice
            values={multiChoices.g1}
            onToggle={toggleMulti('g1')}
            options={MULTI_OPTIONS_STUCK}
          />
        </QuestionCard>

        {/* H. 간편 모드 */}
        <SectionTitle id="H">H. 간편 모드</SectionTitle>

        {renderSingleQuestion('q22')}

        <QuestionCard title="H-2. 간편 모드에 대한 의견 (선택)">
          <FreeText
            value={freeTexts.h2}
            onChange={setText('h2')}
            placeholder="의견이 있다면 적어주세요"
          />
        </QuestionCard>

        {/* I. 마무리 */}
        <SectionTitle id="I">I. 마무리</SectionTitle>

        <QuestionCard title="Q23. 이 키오스크를 친구나 가족에게 추천할 의향이 얼마나 있으신가요?" hint="0(전혀 아니다) ~ 10(매우 그렇다)">
          <NpsRow
            value={answers.q23?.value}
            onChange={(v) => setAnswers((prev) => ({ ...prev, q23: { value: v, label: String(v) } }))}
          />
        </QuestionCard>

        <QuestionCard title="I-2. 가장 인상 깊었던 점 (선택)">
          <FreeText
            value={freeTexts.i2}
            onChange={setText('i2')}
            placeholder="가장 인상 깊었던 점을 적어주세요"
          />
        </QuestionCard>

        <QuestionCard title="I-3. 꼭 개선되었으면 하는 점 (선택)">
          <FreeText
            value={freeTexts.i3}
            onChange={setText('i3')}
            placeholder="꼭 개선되었으면 하는 점이 있다면 알려주세요"
          />
        </QuestionCard>

        {/* 제출 버튼 */}
        <div className="flex gap-3 mt-8 mb-12">
          <button
            type="button"
            onClick={handleSkip}
            className="flex-1 py-4 rounded-2xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition-colors"
          >
            건너뛰기
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            className="flex-[2] py-4 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white font-black text-lg transition-colors shadow-md"
          >
            제출하기
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 pb-6">
          답변하지 못하신 항목이 있어도 제출하실 수 있습니다.
        </p>
      </div>
    </div>
  )
}
