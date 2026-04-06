// 웹캠 제어 커스텀 훅
// 카메라 스트림 시작, 프레임 캡처(AES-256-GCM 암호화 포함), 스트림 정리를 담당

import { useRef, useState, useCallback } from 'react'
import { encryptFrames } from '../utils/crypto'

// VITE_ENCRYPTION_ENABLED=false 로 설정하면 평문 Base64 전송 (개발 편의)
const ENCRYPTION_ENABLED = import.meta.env.VITE_ENCRYPTION_ENABLED !== 'false'

/**
 * 웹캠을 제어하는 커스텀 훅
 * @returns {Object} videoRef, stream, error, startCamera, captureFrames, stopCamera
 */
export function useCamera() {
  const videoRef = useRef(null)         // <video> 엘리먼트 ref
  const streamRef = useRef(null)        // MediaStream 참조
  const [stream, setStream] = useState(null)
  const [error, setError] = useState(null)   // 'not_allowed' | 'not_found' | null

  /**
   * 카메라 스트림 시작
   * 전면 카메라(facingMode: "user") 우선
   */
  const startCamera = useCallback(async () => {
    setError(null)
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',   // 전면 카메라
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      })

      streamRef.current = mediaStream
      setStream(mediaStream)

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
      }

      return mediaStream
    } catch (err) {
      // 카메라 권한 거부
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('not_allowed')
        throw new Error('카메라 권한이 거부되었습니다. 브라우저 설정에서 권한을 허용해주세요.')
      }
      // 카메라를 찾을 수 없음
      if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setError('not_found')
        throw new Error('카메라를 찾을 수 없습니다. 카메라가 연결되어 있는지 확인해주세요.')
      }
      // 기타 오류
      setError('unknown')
      throw err
    }
  }, [])

  /**
   * 프레임 캡처 후 AES-256-GCM 암호화
   * @param {number} count 캡처할 프레임 수 (기본 5)
   * @param {number} intervalMs 캡처 간격 ms (기본 200)
   * @returns {Promise<
   *   { encryptedFrames: string[], iv: string, sessionKey: string } |  // 암호화 모드
   *   { frames: string[] }                                              // 평문 모드
   * >}
   */
  const captureFrames = useCallback(
    (count = 5, intervalMs = 200) => {
      return new Promise((resolve, reject) => {
        if (!videoRef.current || !streamRef.current) {
          reject(new Error('카메라가 시작되지 않았습니다.'))
          return
        }

        const video = videoRef.current
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth || 640
        canvas.height = video.videoHeight || 480
        const ctx = canvas.getContext('2d')

        const frames = []
        let captured = 0

        const capture = async () => {
          // 비디오 프레임을 canvas에 그린 후 Base64로 추출
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
          frames.push(dataUrl)
          captured++

          if (captured >= count) {
            try {
              if (ENCRYPTION_ENABLED) {
                // AES-256-GCM 암호화 후 반환
                const encrypted = await encryptFrames(frames)
                resolve(encrypted)
              } else {
                // 개발용 평문 모드
                resolve({ frames })
              }
            } catch (err) {
              reject(new Error(`암호화 실패: ${err.message}`))
            }
          } else {
            setTimeout(capture, intervalMs)
          }
        }

        // 비디오가 재생 중인지 확인 후 시작
        if (video.readyState >= 2) {
          capture()
        } else {
          video.onloadeddata = capture
        }
      })
    },
    []
  )

  /**
   * 카메라 스트림 정리 — 컴포넌트 언마운트 시 호출
   */
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      setStream(null)
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }, [])

  return {
    videoRef,
    stream,
    error,
    startCamera,
    captureFrames,
    stopCamera,
  }
}
