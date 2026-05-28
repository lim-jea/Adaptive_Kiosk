// idle timeout 경고 오버레이 — 만료 N초 전 표시되어 사용자에게 계속 사용할지 묻는다.
// 응답 없으면 useIdleTimeout 의 onTimeout 이 발화되어 세션이 리셋된다.

export default function IdleWarningOverlay({ open, remainingSec, onExtend, onCancel }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[80] bg-black/70 flex items-center justify-center px-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded-3xl w-full max-w-sm p-6 text-center" onClick={(e) => e.stopPropagation()}>
        <div className="text-5xl mb-3">⏰</div>
        <h2 className="text-xl font-black text-gray-800 mb-2">계속 사용하시겠어요?</h2>
        <p className="text-sm text-gray-500 mb-4">
          잠시 후 처음 화면으로 돌아갑니다.
        </p>
        <div className="text-4xl font-black text-amber-500 mb-5">{Math.max(0, remainingSec)}초</div>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="py-3 rounded-2xl border-2 border-gray-200 text-gray-600 font-bold hover:bg-gray-50"
          >
            처음으로
          </button>
          <button
            type="button"
            onClick={onExtend}
            className="py-3 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white font-bold active:scale-95"
          >
            계속 사용하기
          </button>
        </div>
      </div>
    </div>
  )
}
