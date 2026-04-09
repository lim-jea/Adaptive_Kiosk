// 실시간 STT 인식 결과 + AI 응답을 표시하는 작은 패널.

export default function LiveTranscript({ status, interim, lastUserText, lastResponseText }) {
  return (
    <div className="bg-white/95 backdrop-blur rounded-2xl shadow-lg px-5 py-4 w-full max-w-md">
      <div className="flex items-center gap-2 mb-2">
        <StatusDot status={status} />
        <span className="text-xs text-gray-500 font-medium">{labelOf(status)}</span>
      </div>
      {lastResponseText && (
        <p className="text-sm text-gray-800 mb-2 leading-snug">🗣️ {lastResponseText}</p>
      )}
      {(interim || lastUserText) && (
        <p className="text-sm text-amber-700 leading-snug">
          🎤 {interim || lastUserText}
        </p>
      )}
    </div>
  )
}

function StatusDot({ status }) {
  const color = {
    listening: 'bg-green-500 animate-pulse',
    thinking: 'bg-amber-400 animate-pulse',
    speaking: 'bg-blue-500 animate-pulse',
    error: 'bg-red-500',
    ended: 'bg-gray-300',
    starting: 'bg-amber-300 animate-pulse',
    idle: 'bg-gray-300',
  }[status] || 'bg-gray-300'
  return <span className={`w-2 h-2 rounded-full ${color}`} />
}

function labelOf(status) {
  return ({
    idle: '대기 중',
    starting: '시작 중...',
    listening: '듣고 있어요',
    thinking: '생각 중...',
    speaking: '안내 중',
    error: '오류',
    ended: '종료',
  })[status] || status
}
