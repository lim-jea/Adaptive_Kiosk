import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { adminCheckSession, adminLogout } from '../../utils/adminApi'

const navItems = [
  { to: '/admin', label: '대시보드', end: true },
  { to: '/admin/analytics', label: '분석' },
  { to: '/admin/usability', label: '사용성 분석' },
  { to: '/admin/menus', label: '메뉴 관리' },
  { to: '/admin/options', label: '옵션 카탈로그' },
  { to: '/admin/orders', label: '주문 조회' },
  { to: '/admin/kiosks', label: '키오스크' },
]

export default function AdminLayout() {
  const navigate = useNavigate()
  // HttpOnly 쿠키 기반이라 JS 가 직접 토큰을 볼 수 없으므로 서버에 세션 유효성을 묻는다.
  // 'checking' | 'ok' | 'unauthorized'
  const [authState, setAuthState] = useState('checking')

  useEffect(() => {
    let cancelled = false
    adminCheckSession().then((ok) => {
      if (cancelled) return
      setAuthState(ok ? 'ok' : 'unauthorized')
    })
    return () => { cancelled = true }
  }, [])

  if (authState === 'checking') {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center text-slate-500">
        세션 확인 중...
      </div>
    )
  }
  if (authState === 'unauthorized') {
    return <Navigate to="/admin/login" replace />
  }

  const logout = async () => {
    await adminLogout()
    navigate('/admin/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <aside className="fixed inset-y-0 left-0 w-64 bg-slate-950 text-white">
        <div className="px-6 py-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-300">BREW AI</p>
          <h1 className="mt-1 text-xl font-bold">관리자</h1>
        </div>
        <nav className="px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-4 py-3 text-sm font-semibold transition ${
                  isActive ? 'bg-amber-400 text-slate-950' : 'text-slate-300 hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute bottom-0 left-0 right-0 p-4 space-y-2">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="w-full rounded-md bg-amber-500 hover:bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            키오스크 화면으로
          </button>
          <button
            type="button"
            onClick={logout}
            className="w-full rounded-md border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800"
          >
            로그아웃
          </button>
        </div>
      </aside>
      <main className="ml-64 min-h-screen p-8">
        <Outlet />
      </main>
    </div>
  )
}
