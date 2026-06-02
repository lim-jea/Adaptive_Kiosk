export function getPaymentVisual(methodId) {
  const visuals = {
    card: { mark: 'CARD', icon: null, bg: '#111827', fg: '#ffffff' },
    samsung_pay: { mark: 'S', icon: null, bg: '#1428a0', fg: '#ffffff' },
    apple_pay: { mark: 'Pay', icon: null, bg: '#111111', fg: '#ffffff' },
    naver_pay: { mark: 'N', icon: null, bg: '#03c75a', fg: '#ffffff' },
  }

  return visuals[methodId] || { mark: 'PAY', icon: null, bg: '#6b7280', fg: '#ffffff' }
}
