// 중장년 결제 완료 페이지
// 스탬프 카드 시각화, 주차 등록 팝업, 영수증, 인라인 짧은 설문 (청년/어린이 동일 11문항)
import { useEffect, useState, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import { formatOrderDisplayNo } from '../utils/orderDisplay'
import { splitVAT } from '../utils/price'

const TOTAL_STAMPS = 10
const REWARD_STAMP = 10

function getSimulatedStamps() {
  return parseInt(sessionStorage.getItem('stamp_count') || '4', 10)
}

// ── 설문 상수 (CompletionPage/ChildCompletePage 와 동일 셋) ──────────────────
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

// 중장년 톤(주황 #f4a261)에 맞춘 RatingRow / SingleChoice
function RatingRow({ value, onChange, labels }) {
  return (
    <div className="grid grid-cols-5 gap-1.5">
      {labels.map(({ value: v, label }) => {
        const selected = value === v
        return (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className="py-2.5 rounded-xl text-xs font-semibold transition-all border-2"
            style={{
              background: selected ? '#f4a261' : '#fff',
              color: selected ? '#fff' : '#6b7280',
              borderColor: selected ? '#f4a261' : '#fde8d8',
              boxShadow: selected ? '0 2px 4px rgba(244,162,97,0.3)' : 'none',
            }}
          >
            <div className="text-sm font-black">{v}</div>
            <div className="text-[10px] mt-0.5 leading-tight">{label}</div>
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
        const selected = value === opt.value
        return (
          <button
            key={i}
            type="button"
            onClick={() => onChange(opt.value)}
            className="px-4 py-2 rounded-xl text-sm font-semibold transition-all border-2"
            style={{
              background: selected ? '#f4a261' : '#fff',
              color: selected ? '#fff' : '#6b7280',
              borderColor: selected ? '#f4a261' : '#fde8d8',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

// 숫자 키패드
function NumPad({ value, onChange, maxLength = 9 }) {
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
          className={`h-12 rounded-xl text-xl font-bold transition-all
            ${key === '' ? 'invisible' : 'hover:opacity-80 active:scale-95'}
            ${key === '⌫' ? 'text-red-400' : 'text-gray-700'}`}
          style={{ background: key === '' ? 'transparent' : '#fff3ec', border: '1px solid #fde8d8' }}
        >
          {key}
        </button>
      ))}
    </div>
  )
}

export default function MiddleCompletePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const { paymentMethod, totalPrice, totalCount, isMembership, orderUuid, discount, originalPrice } = location.state || {}
  const vat = splitVAT(totalPrice)

  const [orderNum] = useState(() => formatOrderDisplayNo(orderUuid) || String(Math.floor(Math.random() * 9000 + 1000)))
  const [showStampAnim, setShowStampAnim] = useState(false)

  // 주차 팝업
  const [showParkingPopup, setShowParkingPopup] = useState(false)
  const [parkingDone, setParkingDone] = useState(false)
  const [carNumber, setCarNumber] = useState('')
  const [parkingToast, setParkingToast] = useState(false)

  // 스탬프 계산
  const prevStamps = getSimulatedStamps()
  const earnedStamps = isMembership ? 2 : 1
  const newStamps = Math.min(TOTAL_STAMPS, prevStamps + earnedStamps)
  const isReward = newStamps >= TOTAL_STAMPS

  // 영수증
  const [showReceiptPopup, setShowReceiptPopup] = useState(false)

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
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('completion', {
        payment_method: paymentMethod,
        total_price: totalPrice,
      })
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
        await api.patch(`/api/v1/sessions/${state.sessionUuid}`, {
          status: 'ended',
          end_reason: 'completed',
        })
        await logger.flush()
      } catch (err) {
        console.warn('세션 종료 실패 (무시):', err.message)
      }
    }
    endSession()
  }, [])

  useEffect(() => {
    sessionStorage.setItem('stamp_count', String(isReward ? 0 : newStamps))
    const t = setTimeout(() => setShowStampAnim(true), 400)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleGoHome = async () => {
    logger.log('navigation', 'completion', { actionName: 'go_home', targetType: 'button', targetLabel: 'home' })
    await logger.flush()
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }

  const handleParkingConfirm = () => {
    if (carNumber.length < 4) return
    logger.log('click', 'completion', { actionName: 'parking_register', targetType: 'button', targetLabel: 'parking_register' })
    setParkingDone(true)
    setShowParkingPopup(false)
    setCarNumber('')
    setParkingToast(true)
    setTimeout(() => setParkingToast(false), 3000)
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
    <div className="min-h-screen flex flex-col" style={{ background: '#fdf6f0' }}>

      {/* 상단 성공 배너 */}
      <div className="px-4 pt-12 pb-8 text-center text-white" style={{ background: '#f4a261' }}>
        <div className="text-5xl mb-3">✅</div>
        <h1 className="text-2xl font-black mb-1">결제 완료!</h1>

        {/* 할인 적용 시 */}
        {discount ? (
          <div>
            <p className="line-through text-sm opacity-70">
              {originalPrice?.toLocaleString()}원
            </p>
            <p className="text-xl font-black">
              {totalPrice?.toLocaleString()}원
              <span className="text-sm ml-1 opacity-80">({discount * 100}% 할인 적용)</span>
            </p>
          </div>
        ) : (
          <p className="text-sm opacity-80">
            {paymentMethod}으로 {totalPrice?.toLocaleString()}원 결제되었어요
          </p>
        )}

        <div className="mt-3 inline-block rounded-full px-4 py-1.5" style={{ background: 'rgba(255,255,255,0.2)' }}>
          <span className="text-sm font-bold">주문번호 #{orderNum}</span>
        </div>
      </div>

      <div className="flex-1 px-4 py-5 space-y-4">

        {/* 스탬프 카드 */}
        <div className="rounded-2xl shadow-sm overflow-hidden" style={{ background: '#fff', border: '1px solid #fde8d8' }}>
          <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: '#fde8d8', background: '#fff8f3' }}>
            <div>
              <p className="font-bold" style={{ color: '#374151' }}>스탬프 카드</p>
              <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>
                {isReward ? '🎉 무료 음료 적립 완료!' : `${REWARD_STAMP - newStamps}개 더 모으면 무료 음료`}
              </p>
            </div>
            {isMembership && (
              <span className="text-xs font-bold px-2 py-1 rounded-full" style={{ background: '#ede9fe', color: '#7c3aed' }}>
                멤버십 2배
              </span>
            )}
          </div>
          <div className="px-4 py-5">
            <div className="grid grid-cols-5 gap-2 mb-4">
              {Array.from({ length: TOTAL_STAMPS }).map((_, i) => {
                const isNew = i >= prevStamps && i < newStamps
                const isFilled = i < newStamps
                return (
                  <div
                    key={i}
                    className="aspect-square rounded-full border-2 flex items-center justify-center text-lg transition-all duration-500"
                    style={{
                      borderColor: isFilled ? '#f4a261' : '#fde8d8',
                      background: isFilled
                        ? isNew && showStampAnim ? '#f4a261' : '#fbbf7a'
                        : '#fff8f3',
                      transform: isNew && showStampAnim ? 'scale(1.1)' : 'scale(1)',
                      transitionDelay: isNew ? `${(i - prevStamps) * 150}ms` : '0ms',
                    }}
                  >
                    {isFilled ? (
                      <span className={isNew && showStampAnim ? 'animate-bounce' : ''}>☕</span>
                    ) : (
                      <span className="text-xs" style={{ color: '#fde8d8' }}>{i + 1}</span>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="rounded-xl px-4 py-2.5 flex items-center gap-2" style={{ background: '#fff3ec' }}>
              <span className="text-lg">🎁</span>
              <div>
                <p className="text-sm font-bold" style={{ color: '#c2703a' }}>
                  {earnedStamps}개 적립 완료
                  {isMembership && <span className="ml-1" style={{ color: '#7c3aed' }}>(멤버십 2배!)</span>}
                </p>
                <p className="text-xs" style={{ color: '#f4a261' }}>
                  현재 {newStamps} / {TOTAL_STAMPS} 스탬프
                  {isReward && ' · 다음 방문 시 무료 음료!'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 주차 등록 */}
        <div className="rounded-2xl shadow-sm overflow-hidden" style={{ background: '#fff', border: '1px solid #fde8d8' }}>
          <div className="px-4 py-3 border-b" style={{ borderColor: '#fde8d8', background: '#fff8f3' }}>
            <p className="font-bold" style={{ color: '#374151' }}>주차 등록</p>
            <p className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>구매 시 1시간 무료 주차</p>
          </div>
          <div className="px-4 py-4">
            {parkingDone ? (
              <div className="flex items-center gap-3 rounded-xl px-4 py-3" style={{ background: '#f0fdf4' }}>
                <span className="text-2xl">✅</span>
                <div>
                  <p className="font-bold" style={{ color: '#15803d' }}>주차 등록 완료</p>
                  <p className="text-xs" style={{ color: '#16a34a' }}>1시간 무료 주차가 적용되었습니다</p>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowParkingPopup(true)}
                className="w-full py-4 rounded-xl border-2 border-dashed transition-all flex items-center justify-center gap-3 font-semibold"
                style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
              >
                <span className="text-2xl">🚗</span>
                <div className="text-left">
                  <p className="font-bold">주차 등록하기</p>
                  <p className="text-xs font-normal opacity-70">차량 번호 직접 입력</p>
                </div>
              </button>
            )}
          </div>
        </div>

        {/* 영수증 */}
        <button
          onClick={() => setShowReceiptPopup(true)}
          className="w-full rounded-2xl py-3 flex items-center justify-center gap-2 transition-colors hover:opacity-80"
          style={{ background: '#fff', border: '1px solid #fde8d8', color: '#6b7280' }}
        >
          <span className="text-xl">🧾</span>
          <span className="text-sm font-medium">영수증 보기</span>
        </button>

        {/* 의견 들려주기 토글 — 청년/어린이와 동일한 11문항 셋 */}
        <div className="rounded-2xl shadow-lg overflow-hidden" style={{ background: '#10b981', border: '2px solid #059669' }}>
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
                  <p className="text-sm font-semibold mt-1" style={{ color: '#d1fae5' }}>2~3분 · 서비스 개선에 직접 반영됩니다</p>
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
            <div className="px-4 pb-5 space-y-5 pt-4 bg-white" style={{ borderTop: '1px solid #d1fae5' }}>

              {/* 만 나이 */}
              <div>
                <p className="text-sm font-bold mb-2" style={{ color: '#374151' }}>만 나이</p>
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={respAge}
                  onChange={(e) => setRespAge(e.target.value)}
                  placeholder="예: 50"
                  className="w-full border-2 rounded-xl px-4 py-2.5 text-sm focus:outline-none"
                  style={{ borderColor: '#fde8d8' }}
                />
              </div>

              {/* 성별 */}
              <div>
                <p className="text-sm font-bold mb-2" style={{ color: '#374151' }}>성별</p>
                <SingleChoice value={respGender} onChange={setRespGender} options={GENDER_OPTIONS} />
              </div>

              {/* 섹션별 rating 문항 */}
              {SECTIONS.map((section) => (
                <div key={section.label}>
                  <p className="text-xs font-black uppercase tracking-wider mb-3 pb-1 border-b" style={{ color: '#c2703a', borderColor: '#fde8d8' }}>
                    {section.label}
                  </p>
                  <div className="space-y-4">
                    {section.ids.map((id) => {
                      const q = RATING_QUESTIONS.find((r) => r.id === id)
                      if (!q) return null
                      return (
                        <div key={id}>
                          <p className="text-sm font-semibold mb-2" style={{ color: '#374151' }}>{q.title}</p>
                          {q.hasNoExperience && (
                            <label className="flex items-center gap-2 mb-2 text-xs cursor-pointer" style={{ color: '#9ca3af' }}>
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
                <p className="text-xs font-black uppercase tracking-wider mb-3 pb-1 border-b" style={{ color: '#c2703a', borderColor: '#fde8d8' }}>
                  막힌 단계
                </p>
                <p className="text-sm font-semibold mb-2" style={{ color: '#374151' }}>
                  주문 중 어려움을 겪었거나 막힌 단계가 있다면 골라 주세요
                </p>
                <p className="text-xs mb-2" style={{ color: '#9ca3af' }}>여러 개 선택 가능</p>
                <div className="flex flex-wrap gap-2">
                  {STUCK_OPTIONS.map((opt) => {
                    const selected = g1Choices.includes(opt)
                    return (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => toggleG1(opt)}
                        className="px-3 py-2 rounded-xl text-xs font-semibold transition-all border-2"
                        style={{
                          background: selected ? '#f4a261' : '#fff',
                          color: selected ? '#fff' : '#6b7280',
                          borderColor: selected ? '#f4a261' : '#fde8d8',
                        }}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* H-1 간편 모드 */}
              <div>
                <p className="text-xs font-black uppercase tracking-wider mb-3 pb-1 border-b" style={{ color: '#c2703a', borderColor: '#fde8d8' }}>
                  간편 모드
                </p>
                <p className="text-sm font-semibold mb-2" style={{ color: '#374151' }}>
                  큰 글씨와 음성 안내가 강화된 "간편 모드"를 안내받으면 사용해보고 싶으신가요?
                </p>
                <SingleChoice value={easyMode} onChange={setEasyMode} options={EASY_MODE_OPTIONS} />
              </div>

              {/* 제출 */}
              <button
                onClick={handleSurveySubmit}
                disabled={surveySubmitting}
                className="w-full py-3 rounded-2xl font-bold text-white transition-colors disabled:opacity-60"
                style={{ background: '#f4a261' }}
              >
                {surveySubmitting ? '제출 중...' : '의견 제출하기'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 하단 홈으로 버튼 */}
      <div className="px-4 pb-8 pt-2">
        <button
          onClick={handleGoHome}
          className="w-full py-4 text-white font-bold text-lg rounded-2xl transition-colors"
          style={{ background: '#f4a261' }}
        >
          처음으로 돌아가기
        </button>
      </div>

      {/* 주차 등록 팝업 */}
      {showParkingPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowParkingPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-6"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-black mb-1" style={{ color: '#374151' }}>주차 등록</h2>
            <p className="text-sm mb-4" style={{ color: '#9ca3af' }}>차량 번호를 입력해 주세요</p>

            <div className="rounded-2xl px-4 py-4 text-center mb-2" style={{ background: '#fff3ec' }}>
              <p className="text-2xl font-black tracking-widest" style={{ color: '#374151' }}>
                {carNumber || '차량 번호 입력'}
              </p>
            </div>

            <NumPad value={carNumber} onChange={setCarNumber} maxLength={9} />

            <div className="flex gap-3 mt-4">
              <button
                onClick={() => { setShowParkingPopup(false); setCarNumber('') }}
                className="flex-1 py-3 rounded-2xl border-2 font-bold"
                style={{ borderColor: '#fde8d8', color: '#9ca3af' }}
              >
                취소
              </button>
              <button
                onClick={handleParkingConfirm}
                disabled={carNumber.length < 4}
                className="flex-1 py-3 rounded-2xl font-bold text-white transition-colors"
                style={{
                  background: carNumber.length >= 4 ? '#f4a261' : '#e5e7eb',
                  color: carNumber.length >= 4 ? '#fff' : '#9ca3af',
                }}
              >
                등록
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 영수증 팝업 */}
      {showReceiptPopup && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-6"
          onClick={() => setShowReceiptPopup(false)}
        >
          <div
            className="rounded-3xl w-full max-w-sm p-8 text-center"
            style={{ background: '#fff8f3' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-5xl mb-4 animate-bounce">🖨️</div>
            <h2 className="text-xl font-black mb-2" style={{ color: '#374151' }}>영수증 출력 중</h2>
            <p className="text-sm mb-4" style={{ color: '#9ca3af' }}>
              주문번호 #{orderNum} 영수증이 출력되고 있습니다.
            </p>
            <div className="rounded-2xl px-5 py-3 mb-4 text-left text-sm space-y-1" style={{ background: '#fff3ec' }}>
              <div className="flex justify-between"><span style={{ color: '#9ca3af' }}>공급가액</span><span className="font-semibold" style={{ color: '#374151' }}>{vat.net.toLocaleString()}원</span></div>
              <div className="flex justify-between"><span style={{ color: '#9ca3af' }}>부가세 (10%)</span><span className="font-semibold" style={{ color: '#374151' }}>{vat.tax.toLocaleString()}원</span></div>
              <div className="flex justify-between pt-1 border-t" style={{ borderColor: '#fde8d8' }}><span className="font-bold" style={{ color: '#374151' }}>합계</span><span className="font-black" style={{ color: '#f4a261' }}>{vat.gross.toLocaleString()}원</span></div>
            </div>
            <button
              onClick={() => setShowReceiptPopup(false)}
              className="w-full py-3 rounded-2xl font-bold text-white"
              style={{ background: '#f4a261' }}
            >
              확인
            </button>
          </div>
        </div>
      )}

      {/* 주차 완료 토스트 */}
      {parkingToast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 text-white px-5 py-3 rounded-2xl shadow-xl flex items-center gap-2 z-50 animate-bounce"
          style={{ background: '#16a34a' }}>
          <span>🚗</span>
          <span className="font-bold text-sm">주차 등록 완료! 1시간 무료</span>
        </div>
      )}
    </div>
  )
}
