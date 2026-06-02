const DEFAULT_LABEL = '\uC544\uB798\uB85C \uB354 \uBCFC \uC218 \uC788\uC2B5\uB2C8\uB2E4'

export default function CartScrollHint({ visible, label = DEFAULT_LABEL }) {
  if (!visible) return null

  return (
    <div className="pointer-events-none absolute bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white/90 to-transparent px-4 pb-1 pt-8 text-center">
      <span className="inline-flex rounded-full bg-gray-900/75 px-3 py-1 text-xs font-bold text-white shadow-sm">
        {label}
      </span>
    </div>
  )
}
