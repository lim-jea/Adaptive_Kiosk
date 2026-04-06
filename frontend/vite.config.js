// Vite 설정
// 실행: npm run dev  (개발 서버 포트 5173)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // HTTPS가 필요한 경우 (카메라 권한 — ngrok 없이 로컬 테스트 시)
    // https: true,
  },
})
