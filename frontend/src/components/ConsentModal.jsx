// 얼굴(생체) 정보 수집 동의 모달
// 개인정보보호법 제23조(민감정보) · 정보통신망법 제22조: 생체정보 수집 시 명시적 동의 필요.
// 모달은 카메라 진입 직전에 표시되며, 동의하지 않으면 진행되지 않는다.
// 동의 시각은 sessionStorage 와 useLogger payload 에 기록한다 (DB 마이그레이션 없음).

import { useState } from 'react'

export default function ConsentModal({ open, onAccept, onDecline }) {
  const [checked, setChecked] = useState(false)

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-modal-title"
    >
      <div
        className="bg-white rounded-3xl w-full max-w-md p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center mb-4">
          <div className="text-4xl mb-2">📷</div>
          <h2 id="consent-modal-title" className="text-xl font-black text-gray-800">
            얼굴 정보 수집 동의
          </h2>
          <p className="text-sm text-gray-500 mt-1">서비스 이용 전 확인해 주세요</p>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-2xl px-4 py-3 mb-4 text-sm text-amber-900 space-y-2">
          <p className="font-bold">수집·이용 목적</p>
          <ul className="list-disc pl-5 space-y-1 text-amber-800">
            <li>연령대 자동 추정 및 그에 맞는 화면 제공</li>
            <li>주문 편의를 위한 추천 메뉴 제공</li>
          </ul>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-2xl px-4 py-3 mb-4 text-sm text-gray-700 space-y-2">
          <p className="font-bold text-gray-800">처리 방식</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>촬영된 이미지는 분석 후 <span className="font-bold">즉시 폐기</span>되며 서버에 저장되지 않습니다.</li>
            <li>추정된 연령대 그룹(예: 청년/중년) 정보만 세션에 기록됩니다.</li>
            <li>분석 결과는 본 매장의 키오스크 서비스 개선 목적으로만 사용됩니다.</li>
          </ul>
        </div>

        <div className="bg-red-50 border border-red-200 rounded-2xl px-4 py-3 mb-4 text-sm text-red-800">
          <p className="font-bold mb-1">⚠️ 14세 미만 이용자</p>
          <p>보호자와 함께 이용해 주세요. 보호자의 동의 없이 진행하면 안 됩니다.</p>
        </div>

        <label className="flex items-start gap-3 mb-5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-1 w-5 h-5 accent-amber-500"
          />
          <span className="text-sm text-gray-800 font-semibold leading-relaxed">
            (필수) 위 내용을 확인했으며, 얼굴 이미지 분석에 동의합니다.
          </span>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={onDecline}
            className="py-3 rounded-2xl border-2 border-gray-200 text-gray-600 font-bold hover:bg-gray-50 active:scale-95 transition-all"
          >
            동의하지 않음
          </button>
          <button
            type="button"
            onClick={() => onAccept(new Date().toISOString())}
            disabled={!checked}
            className="py-3 rounded-2xl bg-amber-500 hover:bg-amber-600 disabled:bg-gray-200 disabled:text-gray-400 text-white font-bold active:scale-95 transition-all"
          >
            동의하고 진행
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          카메라 없이도 연령대를 직접 선택해 이용하실 수 있어요.
        </p>
      </div>
    </div>
  )
}
