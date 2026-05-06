// src/pages/SurveyPage.jsx
import { useNavigate } from 'react-router-dom'

export default function SurveyPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-amber-50 flex flex-col items-center justify-center px-6">
      <div className="text-6xl mb-6">📝</div>
      <h1 className="text-2xl font-black text-gray-800 mb-2">설문 조사</h1>
      <p className="text-gray-400 mb-8">준비 중입니다</p>
      <button
        onClick={() => navigate('/')}
        className="px-8 py-4 bg-amber-500 hover:bg-amber-600 text-white font-bold text-lg rounded-2xl"
      >
        처음으로 돌아가기
      </button>
    </div>
  )
}