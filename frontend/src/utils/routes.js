export function getKioskRoute(ageGroup) {
  if (ageGroup === '노년') return '/seniorkiosk'
  if (ageGroup === '중년' || ageGroup === '중장년') return '/middlekiosk'
  if (ageGroup === '어린이') return '/childkiosk'
  if (ageGroup === '청년') return '/youngkiosk'
  return '/kiosk'
}

export function getPaymentRoute(ageGroup) {
  if (ageGroup === '노년') return '/seniorpayment'
  if (ageGroup === '중년' || ageGroup === '중장년') return '/middlepayment'
  if (ageGroup === '어린이') return '/childpayment'
  if (ageGroup === '청년') return '/youngpayment'
  return '/payment'
}

export function getCompleteRoute(ageGroup) {
  if (ageGroup === '노년') return '/seniorcomplete'
  if (ageGroup === '중년' || ageGroup === '중장년') return '/middlecomplete'
  if (ageGroup === '어린이') return '/childcomplete'
  if (ageGroup === '청년') return '/youngcomplete'
  return '/complete'
}
