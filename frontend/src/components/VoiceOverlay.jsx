// 키오스크 화면 위에 떠 있는 음성 주문 오버레이.
// 옵션 모달(z-50)보다 위에 위치(z-[60]).
// 활성 상태에서는 현재 상태 아이콘(마이크/스피커/로딩) + 종료 버튼을 함께 표시.

import LiveTranscript from './LiveTranscript'

export default function VoiceOverlay({ voice, isSimpleMode, onClose }) {
  const { status, interim, lastUserText, lastResponseText, sttSupported, error, start, stop } = voice
  const isActive = status !== 'idle' && status !== 'ended'
  const big = isSimpleMode

  return (
    <div className={`fixed z-[60] pointer-events-none
      ${big
        ? 'top-16 left-4 right-4 flex flex-col items-center gap-4'
        : 'top-16 left-4 right-4 flex flex-col items-center gap-3'}`}
    >
      {isActive && (
        <div className="pointer-events-auto w-full flex justify-center">
          <LiveTranscript
            status={status}
            interim={interim}
            lastUserText={lastUserText}
            lastResponseText={lastResponseText}
            isSimpleMode={big}
          />
        </div>
      )}
      {error && (
        <div className={`pointer-events-auto bg-red-50 border border-red-200 text-red-700 rounded-xl
          ${big ? 'text-base px-5 py-3' : 'text-xs px-3 py-2'}`}>
          {error}
        </div>
      )}
      <div className="flex gap-3 pointer-events-auto justify-center items-center">
        {isActive ? (
          <>
            {/* 현재 상태 아이콘 — 마이크 켜짐/안내 중/생각 중 표시 */}
            <StatusBadge status={status} big={big} />
            {/* 종료 버튼 */}
            <button
              onClick={() => { stop(); onClose?.() }}
              className={`rounded-full bg-red-500 hover:bg-red-600 text-white shadow-lg flex items-center justify-center
                ${big ? 'w-16 h-16 text-2xl' : 'w-12 h-12 text-lg'}`}
              title="음성 주문 종료"
            >
              &#9209;
            </button>
          </>
        ) : (
          <button
            onClick={start}
            disabled={!sttSupported}
            className={`rounded-full shadow-lg flex items-center justify-center
              ${sttSupported ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'bg-gray-200 text-gray-400'}
              ${big ? 'w-20 h-20 text-4xl' : 'w-14 h-14 text-2xl'}`}
            title={sttSupported ? '음성 주문 시작' : '이 브라우저는 음성 인식을 지원하지 않아요'}
          >
            &#127908;
          </button>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status, big }) {
  const config = {
    listening: { icon: '🎤', bg: 'bg-green-500', pulse: true, label: '듣는 중' },
    speaking:  { icon: '🔊', bg: 'bg-blue-500',  pulse: false, label: '안내 중' },
    thinking:  { icon: '⏳', bg: 'bg-amber-400', pulse: true, label: '생각 중' },
    starting:  { icon: '⏳', bg: 'bg-amber-300', pulse: true, label: '시작 중' },
  }[status] || { icon: '🎤', bg: 'bg-gray-400', pulse: false, label: '' }

  return (
    <div className={`rounded-full ${config.bg} ${config.pulse ? 'animate-pulse' : ''}
      text-white shadow-lg flex items-center justify-center gap-2
      ${big ? 'h-16 px-6 text-xl' : 'h-12 px-4 text-sm'}`}
    >
      <span className={big ? 'text-2xl' : 'text-lg'}>{config.icon}</span>
      <span className="font-bold">{config.label}</span>
    </div>
  )
}
