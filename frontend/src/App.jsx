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
import SurveyPage from './pages/SurveyPage'
import OrderTypePage from './pages/OrderTypePage'
import CartReviewPage from './pages/CartReviewPage'
import DiscountPage from './pages/DiscountPage'
import AdminLayout from './pages/admin/AdminLayout'
import AdminLoginPage from './pages/admin/AdminLoginPage'
import AdminDashboardPage from './pages/admin/AdminDashboardPage'
import AdminMenuPage from './pages/admin/AdminMenuPage'
import AdminOptionsPage from './pages/admin/AdminOptionsPage'
import AdminOrdersPage from './pages/admin/AdminOrdersPage'
import AdminKiosksPage from './pages/admin/AdminKiosksPage'
import AdminAnalyticsLayout, {
  AnalyticsRevenueTab,
  AnalyticsUsersTab,
  AnalyticsRecommendationsTab,
} from './pages/admin/AdminAnalyticsPage'
import MiddleCompletePage from './pages/MiddleCompletePage'
import MiddleKioskPage from './pages/MiddleKioskPage'
import MiddlePaymentPage from './pages/MiddlePaymentPage'
import SeniorKioskPage from './pages/SeniorKioskPage'
import SeniorCompletePage from './pages/SeniorCompletePage'
import SeniorPaymentPage from './pages/SeniorPaymentPage'
import SurveyPage from './pages/SurveyPage'


export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/camera" element={<CameraPage />} />
          <Route path="/analyzing" element={<AnalyzingPage />} />
          <Route path="/result" element={<ResultPage />} />
          <Route path="/order-type" element={<OrderTypePage />} />
          <Route path="/kiosk" element={<KioskPage />} />
          <Route path="/cart-review" element={<CartReviewPage />} />
          <Route path="/discount" element={<DiscountPage />} />
          <Route path="/payment" element={<PaymentPage />} />
          <Route path="/complete" element={<CompletionPage />} />

          <Route path="/seniorkiosk" element={<SeniorKioskPage />} />
          <Route path="/seniorpayment" element={<SeniorPaymentPage />} />
          <Route path="/seniorcomplete" element={<SeniorCompletePage />} />
          <Route path="/middlecomplete" element={<MiddleCompletePage />} />
          <Route path="/middlepayment" element={<MiddlePaymentPage />} />
          <Route path="/middlekiosk" element={<MiddleKioskPage />} />    

          <Route path="/survey" element={<SurveyPage />} />
          <Route path="/admin/login" element={<AdminLoginPage />} />
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminDashboardPage />} />
            <Route path="analytics" element={<AdminAnalyticsLayout />}>
              <Route index element={<AnalyticsRevenueTab />} />
              <Route path="users" element={<AnalyticsUsersTab />} />
              <Route path="recommendations" element={<AnalyticsRecommendationsTab />} />
            </Route>
            <Route path="menus" element={<AdminMenuPage />} />
            <Route path="options" element={<AdminOptionsPage />} />
            <Route path="orders" element={<AdminOrdersPage />} />
            <Route path="kiosks" element={<AdminKiosksPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}

