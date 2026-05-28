// 부가가치세(VAT 10%) 분리 표시 유틸
// 한국 부가가치세법 시행령상 영수증·결제 화면에 공급가액·부가세 분리 표시 의무.
// 모든 금액은 부가세 포함 가격(VAT inclusive)으로 저장/전달되며, 표시 시점에만 분리한다.

export function splitVAT(grossPrice) {
  const gross = Number.isFinite(grossPrice) ? Math.max(0, Math.round(grossPrice)) : 0
  const tax = Math.round(gross / 11)
  const net = gross - tax
  return { net, tax, gross }
}
