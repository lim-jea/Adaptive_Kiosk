// 키오스크 화면 위에 떠 있는 음성 주문 오버레이.
// 옵션 모달(z-50)보다 위에 위치(z-[60]).
// 활성 상태에서는 현재 상태 아이콘(마이크/스피커/로딩) + 종료 버튼을 함께 표시.

import { useState } from 'react'
import LiveTranscript from './LiveTranscript'

export default function VoiceOverlay({ voice, isSimpleMode, onClose, onCallStaff }) {
  const { status, interim, lastUserText, lastResponseText, sttSupported, error, start, stop } = voice
  const [callingStaff, setCallingStaff] = useState(false)
  const isActive = status !== 'idle' && status !== 'ended'
  const big = isSimpleMode
  const actionSize = big ? 'min-h-[64px] px-5 text-xl' : 'min-h-[52px] px-4 text-base'

  const handleCallStaff = () => {
    onCallStaff?.()
    setCallingStaff(true)
    setTimeout(() => setCallingStaff(false), 2200)
  }

  return (
    <div className={`fixed z-[60] pointer-events-none
      ${big
        ? 'top-32 left-4 right-4 flex flex-col items-center gap-4'
        : 'top-28 left-4 right-4 flex flex-col items-center gap-3'}`}
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
      {callingStaff && (
        <div className={`pointer-events-auto rounded-2xl border-2 border-blue-200 bg-blue-50 text-blue-800 shadow-lg font-bold
          ${big ? 'text-xl px-6 py-4' : 'text-sm px-4 py-3'}`}>
          직원을 호출했습니다. 잠시만 기다려 주세요.
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
            <button
              onClick={handleCallStaff}
              className={`rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center gap-2 font-black
                ${big ? 'h-16 px-6 text-xl' : 'h-12 px-4 text-sm'}`}
              title="직원 호출"
            >
              <span>🔔</span>
              <span>직원 호출</span>
            </button>
          </>
        ) : (
          <>
            <button
              onClick={start}
              disabled={!sttSupported}
              className={`rounded-full shadow-lg flex items-center justify-center gap-2 font-black
                ${sttSupported ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'bg-gray-200 text-gray-400'}
                ${actionSize}`}
              title={sttSupported ? '음성 주문 시작' : '이 브라우저는 음성 인식을 지원하지 않아요'}
            >
              <span className={big ? 'text-3xl' : 'text-2xl'}>&#127908;</span>
              <span>음성 주문</span>
            </button>
            <button
              onClick={handleCallStaff}
              className={`rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center gap-2 font-black
                ${actionSize}`}
              title="직원 호출"
            >
              <span className={big ? 'text-3xl' : 'text-2xl'}>🔔</span>
              <span>직원 호출</span>
            </button>
          </>
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
