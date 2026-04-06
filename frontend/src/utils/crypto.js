// AES-256-GCM 암호화 유틸리티
// Web Crypto API 사용 — 브라우저 내장 API, 별도 라이브러리 불필요
//
// 흐름:
//   generateSessionKey() → encryptFrames(frames) → { encryptedFrames, iv, sessionKey }
//   → 서버로 전송 → 서버에서 복호화 → InsightFace 추론

/**
 * 세션마다 고유한 AES-256 키 생성
 * @returns {Promise<CryptoKey>}
 */
async function generateSessionKey() {
  return window.crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,         // 내보내기 가능 (서버로 전송용)
    ['encrypt', 'decrypt'],
  )
}

/**
 * 단일 ArrayBuffer를 AES-256-GCM으로 암호화
 * @param {CryptoKey} key
 * @param {Uint8Array} iv - 12바이트 IV
 * @param {ArrayBuffer} buffer - 암호화할 데이터
 * @returns {Promise<ArrayBuffer>}
 */
async function encryptBuffer(key, iv, buffer) {
  return window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    buffer,
  )
}

/**
 * ArrayBuffer → Base64 문자열 변환
 * @param {ArrayBuffer} buffer
 * @returns {string}
 */
function bufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (const b of bytes) {
    binary += String.fromCharCode(b)
  }
  return window.btoa(binary)
}

/**
 * Base64 data URL에서 순수 Base64 추출 후 ArrayBuffer로 변환
 * @param {string} dataUrl - "data:image/jpeg;base64,..." 형식
 * @returns {ArrayBuffer}
 */
function dataUrlToBuffer(dataUrl) {
  // "data:image/jpeg;base64," 헤더 제거
  const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl
  const binary = window.atob(base64)
  const buffer = new ArrayBuffer(binary.length)
  const view = new Uint8Array(buffer)
  for (let i = 0; i < binary.length; i++) {
    view[i] = binary.charCodeAt(i)
  }
  return buffer
}

/**
 * 프레임 배열 전체를 AES-256-GCM으로 암호화
 * 모든 프레임에 동일한 키와 IV 사용 (세션 단위 암호화)
 *
 * @param {string[]} frameBase64Array - Base64 인코딩된 이미지 배열
 * @returns {Promise<{ encryptedFrames: string[], iv: string, sessionKey: string }>}
 *   모두 Base64 인코딩된 문자열로 반환
 */
export async function encryptFrames(frameBase64Array) {
  // 1. 세션 고유 AES-256 키 생성
  const key = await generateSessionKey()

  // 2. 랜덤 12바이트 IV 생성 (GCM 권장 크기)
  const iv = window.crypto.getRandomValues(new Uint8Array(12))

  // 3. 각 프레임 암호화
  const encryptedFrames = await Promise.all(
    frameBase64Array.map(async (frame) => {
      const buffer = dataUrlToBuffer(frame)
      const encrypted = await encryptBuffer(key, iv, buffer)
      return bufferToBase64(encrypted)
    })
  )

  // 4. 키를 Base64로 내보내기 (서버 전송용)
  const rawKey = await window.crypto.subtle.exportKey('raw', key)
  const sessionKeyB64 = bufferToBase64(rawKey)
  const ivB64 = bufferToBase64(iv.buffer)

  return {
    encryptedFrames,
    iv: ivB64,
    sessionKey: sessionKeyB64,
  }
}
