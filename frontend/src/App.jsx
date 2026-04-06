// 앱 루트 컴포넌트 — React Router 라우팅 설정
// 화면 흐름: LandingPage → CameraPage → AnalyzingPage → ResultPage → KioskPage → PaymentPage → CompletionPage

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SessionProvider } from './store/sessionStore.jsx'
import LandingPage from './pages/LandingPage'
import CameraPage from './pages/CameraPage'
import AnalyzingPage from './pages/AnalyzingPage'
import ResultPage from './pages/ResultPage'
import KioskPage from './pages/KioskPage'
import PaymentPage from './pages/PaymentPage'
import CompletionPage from './pages/CompletionPage'

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/camera" element={<CameraPage />} />
          <Route path="/analyzing" element={<AnalyzingPage />} />
          <Route path="/result" element={<ResultPage />} />
          <Route path="/kiosk" element={<KioskPage />} />
          <Route path="/payment" element={<PaymentPage />} />
          <Route path="/complete" element={<CompletionPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}
