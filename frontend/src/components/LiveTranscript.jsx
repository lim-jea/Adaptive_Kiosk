// 실시간 STT 인식 결과 + AI 응답을 표시하는 패널.
// status에 따라 마이크/스피커 아이콘이 바뀌어 현재 뭘 하는지 즉시 알 수 있다.

export default function LiveTranscript({ status, interim, lastUserText, lastResponseText, isSimpleMode }) {
  const big = isSimpleMode

  return (
    <div className={`bg-white/95 backdrop-blur shadow-lg w-full
      ${big ? 'rounded-3xl px-7 py-6 max-w-lg' : 'rounded-2xl px-5 py-4 max-w-md'}`}
    >
      {/* 상태 바 — 아이콘 + 라벨 */}
      <div className={`flex items-center gap-3 mb-3 ${big ? '' : 'mb-2'}`}>
        <StatusIcon status={status} big={big} />
        <span className={`font-bold ${big ? 'text-lg' : 'text-sm'}
          ${status === 'listening' ? 'text-green-600' : status === 'speaking' ? 'text-blue-600' : 'text-gray-500'}`}>
          {labelOf(status)}
        </span>
      </div>

      {/* AI 응답 (speaking / 직후) */}
      {lastResponseText && (
        <p className={`text-gray-800 mb-3 leading-relaxed font-semibold
          ${big ? 'text-2xl' : 'text-sm'}`}>
          {lastResponseText}
        </p>
      )}

      {/* 사용자 발화 (listening 중 실시간 표시) */}
      {status === 'listening' && (
        <div className={`flex items-center gap-2 ${big ? 'mt-3' : 'mt-2'}`}>
          <MicPulse big={big} />
          <p className={`text-amber-700 leading-relaxed font-medium
            ${big ? 'text-xl' : 'text-sm'}`}>
            {interim || lastUserText || '말씀해 주세요...'}
          </p>
        </div>
      )}

      {/* thinking 중에는 사용자가 말한 내용 표시 */}
      {status === 'thinking' && lastUserText && (
        <p className={`text-gray-500 leading-relaxed italic
          ${big ? 'text-lg' : 'text-sm'}`}>
          "{lastUserText}"
        </p>
      )}
    </div>
  )
}

function StatusIcon({ status, big }) {
  const size = big ? 'text-3xl' : 'text-xl'
  switch (status) {
    case 'listening':
      return <span className={`${size} animate-pulse`}>&#127908;</span>
    case 'speaking':
      return <span className={`${size}`}>&#128264;</span>
    case 'thinking':
      return <span className={`${size} animate-spin`}>&#9203;</span>
    case 'starting':
      return <span className={`${size} animate-pulse`}>&#9203;</span>
    default:
      return <span className={`${size} opacity-40`}>&#127908;</span>
  }
}

function MicPulse({ big }) {
  return (
    <span className={`inline-flex items-center justify-center rounded-full bg-green-100
      ${big ? 'w-8 h-8' : 'w-5 h-5'}`}>
      <span className={`rounded-full bg-green-500 animate-pulse
        ${big ? 'w-4 h-4' : 'w-2.5 h-2.5'}`} />
    </span>
  )
}

function labelOf(status) {
  return ({
    idle: '대기 중',
    starting: '준비 중...',
    listening: '지금 말씀하세요',
    thinking: '답변 준비 중...',
    speaking: '안내를 듣고 계세요',
    error: '오류 발생',
    ended: '종료',
  })[status] || status
}
