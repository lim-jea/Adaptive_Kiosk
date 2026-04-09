// 키오스크 화면 위에 떠 있는 음성 주문 오버레이.
// 마이크 토글 + 실시간 인식 결과 + AI 응답을 보여준다.

import LiveTranscript from './LiveTranscript'

export default function VoiceOverlay({
  voice,
  onClose,
}) {
  const { status, interim, lastUserText, lastResponseText, sttSupported, error, start, stop } = voice
  const isActive = status !== 'idle' && status !== 'ended'

  return (
    <div className="fixed bottom-24 right-4 z-30 flex flex-col items-end gap-3 pointer-events-none">
      {isActive && (
        <div className="pointer-events-auto">
          <LiveTranscript
            status={status}
            interim={interim}
            lastUserText={lastUserText}
            lastResponseText={lastResponseText}
          />
        </div>
      )}
      {error && (
        <div className="pointer-events-auto bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 rounded-xl">
          {error}
        </div>
      )}
      <div className="flex gap-2 pointer-events-auto">
        {isActive ? (
          <button
            onClick={() => { stop(); onClose?.() }}
            className="w-14 h-14 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-lg flex items-center justify-center text-2xl"
            title="음성 주문 종료"
          >
            ⏹
          </button>
        ) : (
          <button
            onClick={start}
            disabled={!sttSupported}
            className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-2xl
              ${sttSupported ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'bg-gray-200 text-gray-400'}`}
            title={sttSupported ? '음성 주문 시작' : '브라우저가 음성 인식을 지원하지 않아요'}
          >
            🎤
          </button>
        )}
      </div>
    </div>
  )
}
