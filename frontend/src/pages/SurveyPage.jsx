// 설문 조사 페이지
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/sessionStore.jsx'
import api from '../utils/api'

const LIKERT = [
  { value: 1, label: '😞', desc: '불만족' },
  { value: 2, label: '😕', desc: '비선호' },
  { value: 3, label: '😐', desc: '보통' },
  { value: 4, label: '🙂', desc: '선호' },
  { value: 5, label: '😊', desc: '만족' },
]

const DESIGN_OPTIONS = [
  '버튼 크기', '색깔', '글씨 크기', '메뉴 설명', '레이아웃', '전체적인 분위기'
]

function LikertScale({ value, onChange }) {
  return (
    <div className="flex gap-2 justify-between mt-3">
      {LIKERT.map((item) => (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          className="flex-1 flex flex-col items-center gap-1 py-3 rounded-2xl border-2 transition-all active:scale-95"
          style={{
            borderColor: value === item.value ? '#f4a261' : '#fde8d8',
            background: value === item.value ? '#fff3ec' : '#fff',
          }}
        >
          <span className="text-2xl">{item.label}</span>
          <span className="text-xs font-medium" style={{ color: value === item.value ? '#c2703a' : '#9ca3af' }}>
            {item.desc}
          </span>
        </button>
      ))}
    </div>
  )
}

function YesNo({ value, onChange }) {
  return (
    <div className="flex gap-3 mt-3">
      {['예', '아니오'].map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className="flex-1 py-3 rounded-2xl border-2 font-bold transition-all active:scale-95"
          style={{
            borderColor: value === opt ? '#f4a261' : '#fde8d8',
            background: value === opt ? '#fff3ec' : '#fff',
            color: value === opt ? '#c2703a' : '#9ca3af',
          }}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}

function MultiSelect({ options, value = [], onChange }) {
  const toggle = (opt) => {
    if (value.includes(opt)) onChange(value.filter((v) => v !== opt))
    else onChange([...value, opt])
  }
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => toggle(opt)}
          className="px-4 py-2 rounded-full border-2 text-sm font-medium transition-all active:scale-95"
          style={{
            borderColor: value.includes(opt) ? '#f4a261' : '#fde8d8',
            background: value.includes(opt) ? '#fff3ec' : '#fff',
            color: value.includes(opt) ? '#c2703a' : '#9ca3af',
          }}
        >
          {value.includes(opt) ? '✓ ' : ''}{opt}
        </button>
      ))}
    </div>
  )
}

function Section({ title, emoji, children }) {
  return (
    <div className="rounded-2xl overflow-hidden mb-4" style={{ border: '1px solid #fde8d8' }}>
      <div className="px-5 py-3 flex items-center gap-2" style={{ background: '#fff3ec' }}>
        <span className="text-xl">{emoji}</span>
        <h2 className="font-black text-base" style={{ color: '#c2703a' }}>{title}</h2>
      </div>
      <div className="px-5 py-4 space-y-5" style={{ background: '#fff' }}>
        {children}
      </div>
    </div>
  )
}

function Question({ label, required, children }) {
  return (
    <div>
      <p className="text-sm font-bold" style={{ color: '#374151' }}>
        {label}
        {required && <span className="ml-1" style={{ color: '#ef4444' }}>*</span>}
      </p>
      {children}
    </div>
  )
}

export default function SurveyPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const ageGroup = state.ageGroup

  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 기본 정보
  const [age, setAge] = useState('')
  const [gender, setGender] = useState('')

  // 키오스크 사용 경험
  const [convenience, setConvenience] = useState(null)
  const [fontSize, setFontSize] = useState(null)
  const [menuFind, setMenuFind] = useState(null)
  const [orderProcess, setOrderProcess] = useState(null)
  const [paymentProcess, setPaymentProcess] = useState(null)
  const [overallSatisfaction, setOverallSatisfaction] = useState(null)
  const [overallReason, setOverallReason] = useState('')

  // 디자인
  const [designLikes, setDesignLikes] = useState([])

  // 얼굴 인식
  const [faceSpeed, setFaceSpeed] = useState(null)
  const [faceAgeAccurate, setFaceAgeAccurate] = useState('')
  const [faceGenderAccurate, setFaceGenderAccurate] = useState('')
  const [faceConvenience, setFaceConvenience] = useState(null)

  // 기능
  const [aiRecommend, setAiRecommend] = useState(null)
  const [voiceUsed, setVoiceUsed] = useState('')
  const [voiceConvenience, setVoiceConvenience] = useState(null)

  // 추가 의견
  const [extraMenu, setExtraMenu] = useState('')
  const [extraOpinion, setExtraOpinion] = useState('')

  const handleSubmit = useCallback(async () => {
    if (!age || !gender || !overallSatisfaction) {
      alert('나이, 성별, 전체 만족도는 필수입니다!')
      return
    }

    setSubmitting(true)
    try {
      await api.post('/api/v1/surveys', {
        session_uuid: state.sessionUuid,
        age_group: ageGroup,
        age: parseInt(age),
        gender,
        answers: {
          convenience,
          font_size: fontSize,
          menu_find: menuFind,
          order_process: orderProcess,
          payment_process: paymentProcess,
          overall_satisfaction: overallSatisfaction,
          overall_reason: overallReason,
          design_likes: designLikes,
          face_speed: faceSpeed,
          face_age_accurate: faceAgeAccurate,
          face_gender_accurate: faceGenderAccurate,
          face_convenience: faceConvenience,
          ai_recommend: aiRecommend,
          voice_used: voiceUsed,
          voice_convenience: voiceConvenience,
          extra_menu: extraMenu,
          extra_opinion: extraOpinion,
        },
      })
    } catch (err) {
      console.warn('설문 저장 실패 (무시):', err.message)
    } finally {
      setSubmitting(false)
      setSubmitted(true)
    }
  }, [
    age, gender, overallSatisfaction, convenience, fontSize, menuFind,
    orderProcess, paymentProcess, overallReason, designLikes, faceSpeed,
    faceAgeAccurate, faceGenderAccurate, faceConvenience, aiRecommend,
    voiceUsed, voiceConvenience, extraMenu, extraOpinion, state.sessionUuid, ageGroup,
  ])

  const handleGoHome = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_SESSION })
    navigate('/', { replace: true })
  }, [dispatch, ACTIONS, navigate])

  // 완료 화면
  if (submitted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6" style={{ background: '#fdf6f0' }}>
        <div className="text-6xl mb-4 animate-bounce">🎉</div>
        <h1 className="text-2xl font-black mb-2" style={{ color: '#374151' }}>설문 완료!</h1>
        <p className="text-center mb-8" style={{ color: '#9ca3af' }}>
          소중한 의견 감사합니다.<br />더 좋은 키오스크를 만들겠습니다!
        </p>
        <button
          onClick={handleGoHome}
          className="w-full max-w-sm py-4 rounded-2xl font-bold text-white text-lg"
          style={{ background: '#f4a261' }}
        >
          처음으로 돌아가기
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#fdf6f0' }}>
      {/* 헤더 */}
      <header className="px-4 py-3 flex items-center sticky top-0 z-10 shadow-sm" style={{ background: '#f4a261' }}>
        <button onClick={() => navigate(-1)} className="p-2 -ml-2 mr-2 text-white font-bold">← 뒤로</button>
        <h1 className="text-base font-black text-white tracking-widest">설문 조사</h1>
      </header>

      <div className="flex-1 px-4 py-5 space-y-4 pb-32">

        {/* 프로젝트 소개 */}
        <div className="rounded-2xl p-5" style={{ background: '#fff3ec', border: '1px solid #fde8d8' }}>
          <h2 className="text-lg font-black mb-2" style={{ color: '#c2703a' }}>안녕하세요! 😊</h2>
          <p className="text-sm leading-relaxed mb-3" style={{ color: '#374151' }}>
            저희는 <strong>AI 기반 카페 키오스크</strong> 프로젝트를 진행 중인 팀입니다.
            이 키오스크는 카메라로 고객의 얼굴을 인식해 나이대에 맞는 화면을 자동으로 보여주는 시스템입니다.
          </p>
          <div className="space-y-1 text-sm mb-3" style={{ color: '#6b7280' }}>
            <p>🧒 <strong>어린이</strong> — 친근한 모드</p>
            <p>😊 <strong>청년</strong> — 일반 모드</p>
            <p>🙂 <strong>중장년층</strong> — 통신사 할인, 다양한 결제 수단</p>
            <p>👴 <strong>노년층</strong> — 큰 글씨, 음성 주문 지원</p>
          </div>
          <p className="text-sm" style={{ color: '#9ca3af' }}>
            설문은 약 <strong>2분</strong> 소요되며 <strong>익명</strong>으로 처리됩니다. 감사합니다 🙏
          </p>
        </div>

        {/* 기본 정보 */}
        <Section title="기본 정보" emoji="👤">
          <Question label="나이를 입력해 주세요" required>
            <input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="예) 45"
              className="w-full mt-2 px-4 py-3 rounded-xl border-2 text-base outline-none"
              style={{ borderColor: '#fde8d8', background: '#fff8f3', color: '#374151' }}
            />
          </Question>
          <Question label="성별을 선택해 주세요" required>
            <div className="flex gap-3 mt-3">
              {['남성', '여성', '선택 안함'].map((opt) => (
                <button
                  key={opt}
                  onClick={() => setGender(opt)}
                  className="flex-1 py-3 rounded-2xl border-2 font-bold text-sm transition-all active:scale-95"
                  style={{
                    borderColor: gender === opt ? '#f4a261' : '#fde8d8',
                    background: gender === opt ? '#fff3ec' : '#fff',
                    color: gender === opt ? '#c2703a' : '#9ca3af',
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </Question>
        </Section>

        {/* 키오스크 사용 경험 */}
        <Section title="키오스크 사용 경험" emoji="📱">
          <Question label="키오스크 이용이 편리하셨나요?">
            <LikertScale value={convenience} onChange={setConvenience} />
          </Question>
          <Question label="화면 글씨 크기가 적당하셨나요?">
            <LikertScale value={fontSize} onChange={setFontSize} />
          </Question>
          <Question label="원하는 메뉴를 쉽게 찾으셨나요?">
            <LikertScale value={menuFind} onChange={setMenuFind} />
          </Question>
          <Question label="주문 과정이 쉬우셨나요?">
            <LikertScale value={orderProcess} onChange={setOrderProcess} />
          </Question>
          <Question label="결제 과정이 편리하셨나요?">
            <LikertScale value={paymentProcess} onChange={setPaymentProcess} />
          </Question>
          <Question label="전체적인 만족도는 어떠셨나요?" required>
            <LikertScale value={overallSatisfaction} onChange={setOverallSatisfaction} />
            <textarea
              value={overallReason}
              onChange={(e) => setOverallReason(e.target.value)}
              placeholder="그 이유를 간단히 적어주세요 (선택)"
              rows={3}
              className="w-full mt-3 px-4 py-3 rounded-xl border-2 text-sm outline-none resize-none"
              style={{ borderColor: '#fde8d8', background: '#fff8f3', color: '#374151' }}
            />
          </Question>
        </Section>

        {/* 디자인 */}
        <Section title="디자인" emoji="🎨">
          <Question label="마음에 드셨던 부분을 선택해 주세요 (복수 선택 가능)">
            <MultiSelect options={DESIGN_OPTIONS} value={designLikes} onChange={setDesignLikes} />
          </Question>
        </Section>

        {/* 얼굴 인식 */}
        <Section title="얼굴 인식" emoji="📷">
          <Question label="얼굴 인식 속도가 빠르다고 느끼셨나요?">
            <LikertScale value={faceSpeed} onChange={setFaceSpeed} />
          </Question>
          <Question label="인식된 나이대가 정확했나요?">
            <YesNo value={faceAgeAccurate} onChange={setFaceAgeAccurate} />
          </Question>
          <Question label="인식된 성별이 정확했나요?">
            <YesNo value={faceGenderAccurate} onChange={setFaceGenderAccurate} />
          </Question>
          <Question label="얼굴 인식 방식이 편리했나요?">
            <LikertScale value={faceConvenience} onChange={setFaceConvenience} />
          </Question>
        </Section>

        {/* 기능 */}
        <Section title="기능" emoji="⚙️">
          <Question label="AI 추천 메뉴가 마음에 드셨나요?">
            <LikertScale value={aiRecommend} onChange={setAiRecommend} />
          </Question>
          <Question label="음성 주문을 사용해보셨나요?">
            <YesNo value={voiceUsed} onChange={setVoiceUsed} />
          </Question>
          {voiceUsed === '예' && (
            <Question label="음성 주문이 편리하셨나요?">
              <LikertScale value={voiceConvenience} onChange={setVoiceConvenience} />
            </Question>
          )}
        </Section>

        {/* 추가 의견 */}
        <Section title="추가 의견" emoji="💬">
          <Question label="추가됐으면 하는 메뉴가 있나요? (선택)">
            <input
              type="text"
              value={extraMenu}
              onChange={(e) => setExtraMenu(e.target.value)}
              placeholder="예) 디카페인 라떼, 쌍화차..."
              className="w-full mt-2 px-4 py-3 rounded-xl border-2 text-sm outline-none"
              style={{ borderColor: '#fde8d8', background: '#fff8f3', color: '#374151' }}
            />
          </Question>
          <Question label="개선됐으면 하는 점이 있나요? (선택)">
            <textarea
              value={extraOpinion}
              onChange={(e) => setExtraOpinion(e.target.value)}
              placeholder="자유롭게 작성해 주세요"
              rows={3}
              className="w-full mt-2 px-4 py-3 rounded-xl border-2 text-sm outline-none resize-none"
              style={{ borderColor: '#fde8d8', background: '#fff8f3', color: '#374151' }}
            />
          </Question>
        </Section>
      </div>

      {/* 하단 제출 버튼 */}
      <div className="fixed bottom-0 left-0 right-0 px-4 pb-6 pt-3" style={{ background: '#fdf6f0' }}>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-4 rounded-2xl font-bold text-white text-lg transition-all active:scale-95"
          style={{ background: submitting ? '#fbbf7a' : '#f4a261' }}
        >
          {submitting ? '제출 중...' : '설문 제출하기'}
        </button>
      </div>
    </div>
  )
}