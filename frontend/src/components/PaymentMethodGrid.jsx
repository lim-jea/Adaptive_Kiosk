import { getPaymentVisual } from '../utils/paymentVisuals'

export default function PaymentMethodGrid({
  methods,
  onSelect,
  variant = 'default',
  compact = false,
  className = '',
}) {
  return (
    <div className={`grid grid-cols-2 gap-3 ${className}`}>
      {methods.map((method) => (
        <PaymentMethodCard
          key={method.id}
          method={method}
          variant={variant}
          compact={compact}
          onClick={() => onSelect(method)}
        />
      ))}
    </div>
  )
}

function PaymentMethodCard({ method, variant, compact, onClick }) {
  const visual = getPaymentVisual(method.id)
  const isSenior = variant === 'senior'
  const isChild = variant === 'child'
  const isMiddle = variant === 'middle'

  const cardHeight = compact
    ? 'min-h-[104px]'
    : isSenior
      ? 'min-h-[170px]'
      : isChild
        ? 'min-h-[150px]'
        : 'min-h-[132px]'

  const markSize = compact
    ? 'w-12 h-12 text-lg'
    : isSenior
      ? 'w-20 h-20 text-3xl rounded-3xl'
      : 'w-16 h-16 text-xl'

  const cardStyle = isChild
    ? { background: method.bg || visual.bg, color: '#ffffff' }
    : isMiddle
      ? { background: '#fff', borderColor: '#e5e7eb', color: '#374151' }
      : undefined

  const markStyle = isChild
    ? { background: 'rgba(255,255,255,0.95)', color: visual.bg }
    : { background: visual.bg, color: visual.fg }

  return (
    <button
      onClick={onClick}
      className={`${cardHeight} rounded-2xl border-2 active:scale-[0.98] transition-all duration-150 shadow-sm hover:shadow-md flex flex-col items-center justify-center text-center
        ${isChild ? 'px-3 py-5 border-transparent' : 'bg-white text-gray-800 border-gray-200 hover:border-gray-300 px-3 py-4'}`}
      style={cardStyle}
    >
      <div
        className={`${markSize} rounded-2xl flex items-center justify-center font-black shadow-sm`}
        style={markStyle}
      >
        {visual.icon || visual.mark}
      </div>
      <p className={`${compact ? 'text-sm' : isSenior ? 'text-2xl' : isChild ? 'text-xl' : 'text-base'} font-black mt-3 leading-tight`}>
        {method.label}
      </p>
      {!compact && (
        <p className={`${isSenior ? 'text-base' : 'text-xs'} mt-1 ${isChild ? 'opacity-85' : 'text-gray-400'} leading-tight`}>
          {method.desc}
        </p>
      )}
    </button>
  )
}
