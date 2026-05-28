// 어린이 결제 완료 페이지 — 노년과 동일한 형식 (sky 색상 유지)
import { useEffect, useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { formatOrderDisplayNo } from '../utils/orderDisplay'

const TOTAL_STAMPS = 10

function getSimulatedStamps() {
  return parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
}

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
    <div className="grid grid-cols-5 gap-2">
      {labels.map(({ value: v, label }) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`py-3 rounded-2xl text-sm font-semibold transition-all border-2
            ${value === v
              ? 'bg-sky-500 text-white border-sky-500 shadow-md'
              : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'}`}
        >
          <div className="text-lg font-black">{v}</div>
          <div className="text-xs mt-0.5 leading-tight">{label}</div>
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
          className={`px-5 py-3 rounded-2xl text-base font-semibold transition-all border-2
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

function NumPad({ value, onChange, maxLength = 11 }) {
  const keys = ['1','2','3','4','5','6','7','8','9','','0','⌫']
  return (
    <div className="grid grid-cols-3 gap-2 mt-4">
      {keys.map((key, i) => (
        <button
          key={i}
          onClick={() => {
            if (key === '⌫') onChange(value.slice(0, -1))
            else if (key === '') return
            else if (value.length < maxLength) onChange(value + key)
          }}
          disabled={key === ''}
          className={`h-14 rounded-2xl text-2xl font-bold transition-all
            ${key === '' ? 'invisible' : 'bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-800'}
            ${key === '⌫' ? 'text-red-500' : ''}`}
        >
          {key}
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

  const [orderNum] = useState(() => formatOrderDisplayNo(orderUuid) || String(Math.floor(Math.random() * 9000 + 1000)))
  const [toast, setToast] = useState(null)

  // 주차 등록 상태
  const [parkingDone, setParkingDone] = useState(false)
  const [showParkingPopup, setShowParkingPopup] = useState(false)
  const [carNumber, setCarNumber] = useState('')

  // 스탬프 상태
  const [stampDone, setStampDone] = useState(false)
  const [showStampPopup, setShowStampPopup] = useState(false)
  const [stampMethod, setStampMethod] = useState(null) // null | 'phone'
  const [phoneNumber, setPhoneNumber] = useState('')

  const prevStamps = getSimulatedStamps()
  const earnedStamps = 1
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + earnedStamps)
  const isReward = newStamps >= TOTAL_STAMPS

  // 의견 토글
  const [surveyOpen, setSurveyOpen] = useState(false)
  const [surveyDone, setSurveyDone] = useState(false)
  const [surveySubmitting, setSurveySubmitting] = useState(false)
  const [surveyError, setSurveyError] = useState('')

  const [respAge, setRespAge] = useState('')
  const [agepadOpen, setAgepadOpen] = useState(false)
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

  const showToast = (icon, message) => {
    setToast({ icon, message })
    setTimeout(() => setToast(null), 3000)
  }

  const handleGoHome = async () => {
    logger.log('navigation', 'child_complete', { actionName: 'go_home', targetType: 'button', targetLabel: 'home' })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleParkingConfirm = () => {
    if (carNumber.length < 4) return
    logger.log('click', 'child_complete', { actionName: 'parking_register', targetType: 'button', targetLabel: 'parking_register' })
    setParkingDone(true)
    setShowParkingPopup(false)
    setCarNumber('')
    showToast('🚗', `${carNumber} 주차 등록 완료! 1시간 무료`)
  }

  const handleStampConfirm = () => {
    if (stampMethod === 'phone' && phoneNumber.length < 10) return
    logger.log('click', 'child_complete', { actionName: 'stamp_register', targetType: 'button', targetLabel: 'stamp_register' })
    sessionStorage.setItem('stamp_count', String(isReward ? 0 : newStamps))
    setStampDone(true)
    setShowStampPopup(false)
    setStampMethod(null)
    setPhoneNumber('')
    const msg = isReward
      ? '스탬프 가득 찼어요! 다음 방문 시 무료 음료'
      : `스탬프 ${earnedStamps}개 적립! (${newStamps}/${TOTAL_STAMPS})`
    showToast('⭐', msg)
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
    setSurveyError('')
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
      setSurveyDone(true)
      setSurveyOpen(false)
    } catch (err) {
      console.warn('[survey] submit failed:', err.message)
      setSurveyError('의견 저장에 실패했어요. 잠시 후 다시 눌러주세요.')
    } finally {
      setSurveySubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center px-6 py-10" style={{ background: '#ECFEFF' }}>

      {/* 완료 아이콘 + 문구 */}
      <div className="text-6xl mb-4 animate-bounce">🎉</div>
      <h1 className="text-3xl font-black text-gray-800 mb-2">주문 완료!</h1>
      <p className="text-xl text-gray-500 mb-8">{paymentMethod}으로 결제되었어요</p>

      {/* 주문번호 */}
      <div className="bg-white rounded-3xl shadow-md border-2 border-sky-200 px-12 py-8 mb-6 w-full max-w-sm text-center">
        <p className="text-xl font-medium text-gray-400 mb-2">주문번호</p>
        <p className="text-6xl font-black text-sky-500">#{orderNum}</p>
        <p className="text-lg text-gray-400 mt-3">번호가 나오면 음료를 받아가세요</p>
      </div>

      {/* 주차 + 스탬프 버튼 */}
      <div className="flex gap-4 w-full max-w-sm mb-4">
        <button
          onClick={() => !parkingDone && setShowParkingPopup(true)}
          disabled={parkingDone}
          className={`flex-1 flex flex-col items-center justify-center gap-2 py-5 rounded-2xl border-2 font-bold text-lg transition-all
            ${parkingDone
              ? 'border-green-300 bg-green-50 text-green-600'
              : 'border-gray-200 bg-white text-gray-600 hover:border-sky-300 hover:bg-sky-50 active:scale-95'}`}
        >
          <span className="text-4xl">{parkingDone ? '✅' : '🚗'}</span>
          <span>{parkingDone ? '등록 완료' : '주차 등록'}</span>
        </button>

        <button
          onClick={() => !stampDone && setShowStampPopup(true)}
          disabled={stampDone}
          className={`flex-1 flex flex-col items-center justify-center gap-2 py-5 rounded-2xl border-2 font-bold text-lg transition-all
            ${stampDone
              ? 'border-sky-300 bg-sky-50 text-sky-600'
              : 'border-gray-200 bg-white text-gray-600 hover:border-sky-300 hover:bg-sky-50 active:scale-95'}`}
        >
          <span className="text-4xl">{stampDone ? '✅' : '⭐'}</span>
          <span>{stampDone ? '적립 완료' : '스탬프 적립'}</span>
        </button>
      </div>

      {/* 의견 들려주기 토글 */}
      <div className="w-full max-w-sm rounded-3xl border-2 border-emerald-600 shadow-lg mb-5 overflow-hidden bg-emerald-500">
        <button
          onClick={() => !surveyDone && setSurveyOpen((o) => !o)}
          className="w-full flex items-center justify-between px-6 py-6 text-white"
        >
          <div className="flex items-center gap-4">
            <span className="text-4xl">📝</span>
            <div className="text-left">
              <p className="font-black text-2xl">
                {surveyDone ? '의견 제출 완료! 감사해요 😊' : '의견 들려주기'}
              </p>
              {!surveyDone && (
                <p className="text-base font-semibold text-emerald-50 mt-1">2~3분 · 서비스 개선에 반영됩니다</p>
              )}
            </div>
          </div>
          {!surveyDone && (
            <span className="text-white text-3xl font-black transition-transform duration-200"
              style={{ transform: surveyOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}>
              ▾
            </span>
          )}
        </button>

        {/* 설문 본문 */}
        {surveyOpen && !surveyDone && (
          <div className="px-5 pb-6 space-y-6 pt-5 bg-white border-t border-emerald-100">

            {/* 만 나이 */}
            <div>
              <p className="text-lg font-bold text-gray-800 mb-2">만 나이</p>
              <button
                type="button"
                onClick={() => setAgepadOpen((o) => !o)}
                className={`w-full border-2 rounded-2xl px-4 py-3 text-lg text-left transition-colors
                  ${agepadOpen ? 'border-sky-400 bg-sky-50' : 'border-gray-200 bg-white'}
                  ${respAge ? 'text-gray-800 font-bold' : 'text-gray-400'}`}
              >
                {respAge ? `${respAge}세` : '터치하여 입력'}
              </button>
              {agepadOpen && (
                <div className="mt-2">
                  <NumPad value={respAge} onChange={(v) => setRespAge(v)} maxLength={3} />
                  <button
                    type="button"
                    onClick={() => setAgepadOpen(false)}
                    className="w-full mt-2 py-2.5 rounded-2xl bg-sky-500 text-white font-bold text-base"
                  >
                    확인
                  </button>
                </div>
              )}
            </div>

            {/* 성별 */}
            <div>
              <p className="text-lg font-bold text-gray-800 mb-2">성별</p>
              <SingleChoice value={respGender} onChange={setRespGender} options={GENDER_OPTIONS} />
            </div>

            {/* 섹션별 rating 문항 */}
            {SECTIONS.map((section) => (
              <div key={section.label}>
                <p className="text-sm font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
                  {section.label}
                </p>
                <div className="space-y-5">
                  {section.ids.map((id) => {
                    const q = RATING_QUESTIONS.find((r) => r.id === id)
                    if (!q) return null
                    return (
                      <div key={id}>
                        <p className="text-base font-semibold text-gray-700 mb-2">{q.title}</p>
                        {q.hasNoExperience && (
                          <label className="flex items-center gap-2 mb-2 text-sm text-gray-500 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={q7NoExperience}
                              onChange={(e) => setQ7NoExperience(e.target.checked)}
                              className="rounded w-4 h-4"
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

            {/* G-1 막힌 단계 */}
            <div>
              <p className="text-sm font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
                막힌 단계
              </p>
              <p className="text-base font-semibold text-gray-700 mb-2">
                주문 중 어려움이 있었던 단계가 있다면 골라 주세요
              </p>
              <p className="text-sm text-gray-400 mb-2">여러 개 선택 가능</p>
              <div className="flex flex-wrap gap-2">
                {STUCK_OPTIONS.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => toggleG1(opt)}
                    className={`px-4 py-2.5 rounded-2xl text-sm font-semibold transition-all border-2
                      ${g1Choices.includes(opt)
                        ? 'bg-sky-500 text-white border-sky-500'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-sky-300'}`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            {/* H-1 간편 모드 */}
            <div>
              <p className="text-sm font-black text-sky-600 uppercase tracking-wider mb-3 pb-1 border-b border-sky-100">
                간편 모드
              </p>
              <p className="text-base font-semibold text-gray-700 mb-2">
                큰 글씨와 음성 안내가 강화된 "간편 모드"를 안내받으면 사용해보고 싶으신가요?
              </p>
              <SingleChoice value={easyMode} onChange={setEasyMode} options={EASY_MODE_OPTIONS} />
            </div>

            {surveyError && (
              <p className="text-base font-bold text-red-600 text-center">{surveyError}</p>
            )}

            <button
              onClick={handleSurveySubmit}
              disabled={surveySubmitting}
              className="w-full py-4 bg-sky-500 hover:bg-sky-600 disabled:opacity-60 text-white font-black text-xl rounded-2xl transition-colors"
            >
              {surveySubmitting ? '제출 중...' : '의견 제출하기'}
            </button>
          </div>
        )}
      </div>

      {/* 처음으로 버튼 */}
      <button
        onClick={handleGoHome}
        className="w-full max-w-sm py-6 bg-sky-500 hover:bg-sky-600 active:bg-sky-700 text-white font-black text-2xl rounded-2xl transition-colors shadow-lg"
      >
        처음으로 돌아가기
      </button>

      {/* 토스트 */}
      {toast && (
        <div className="fixed top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white px-6 py-4 rounded-2xl shadow-xl flex items-center gap-3 z-50">
          <span className="text-3xl">{toast.icon}</span>
          <span className="font-bold text-lg">{toast.message}</span>
        </div>
      )}

      {/* 주차 등록 팝업 */}
      {showParkingPopup && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowParkingPopup(false)}>
          <div className="bg-white rounded-3xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-2xl font-black text-gray-800 mb-1">주차 등록</h2>
            <p className="text-base text-gray-400 mb-4">차량 번호를 입력해 주세요</p>
            <div className="bg-gray-100 rounded-2xl px-4 py-4 text-center mb-2">
              <p className="text-3xl font-black text-gray-800 tracking-widest">
                {carNumber || '차량 번호 입력'}
              </p>
            </div>
            <NumPad value={carNumber} onChange={setCarNumber} maxLength={9} />
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => { setShowParkingPopup(false); setCarNumber('') }}
                className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
              >
                취소
              </button>
              <button
                onClick={handleParkingConfirm}
                disabled={carNumber.length < 4}
                className={`flex-1 py-4 rounded-2xl text-xl font-bold transition-colors
                  ${carNumber.length >= 4
                    ? 'bg-sky-500 hover:bg-sky-600 text-white'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
              >
                등록
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 스탬프 적립 팝업 */}
      {showStampPopup && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => { setShowStampPopup(false); setStampMethod(null); setPhoneNumber('') }}>
          <div className="bg-white rounded-3xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}>

            {!stampMethod && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">스탬프 적립</h2>
                <p className="text-base text-gray-400 mb-6">적립 방법을 선택해 주세요</p>
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => setStampMethod('phone')}
                    className="w-full py-5 rounded-2xl border-2 border-gray-200 bg-white text-gray-700 text-xl font-bold hover:border-sky-400 hover:bg-sky-50 transition-all flex items-center gap-4 px-5"
                  >
                    <span className="text-3xl">📱</span>
                    <span>전화번호로 적립</span>
                  </button>
                </div>
                <button
                  onClick={() => setShowStampPopup(false)}
                  className="w-full mt-4 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                >
                  취소
                </button>
              </>
            )}

            {stampMethod === 'phone' && (
              <>
                <h2 className="text-2xl font-black text-gray-800 mb-1">전화번호 입력</h2>
                <p className="text-base text-gray-400 mb-4">등록된 전화번호를 입력해 주세요</p>
                <div className="bg-gray-100 rounded-2xl px-4 py-4 text-center mb-2">
                  <p className="text-3xl font-black text-gray-800 tracking-widest">
                    {phoneNumber
                      ? phoneNumber.replace(/(\d{3})(\d{0,4})(\d{0,4})/, (_, a, b, c) => [a, b, c].filter(Boolean).join('-'))
                      : '010-0000-0000'}
                  </p>
                </div>
                <NumPad value={phoneNumber} onChange={setPhoneNumber} maxLength={11} />
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => setStampMethod(null)}
                    className="flex-1 py-4 rounded-2xl border-2 border-gray-300 text-gray-600 text-xl font-bold"
                  >
                    뒤로
                  </button>
                  <button
                    onClick={handleStampConfirm}
                    disabled={phoneNumber.length < 10}
                    className={`flex-1 py-4 rounded-2xl text-xl font-bold transition-colors
                      ${phoneNumber.length >= 10
                        ? 'bg-sky-500 hover:bg-sky-600 text-white'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
                  >
                    적립
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
