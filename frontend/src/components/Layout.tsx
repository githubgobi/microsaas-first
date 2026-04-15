import { ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { Button } from './ui/Button'

export function Layout({ children }: { children: ReactNode }) {
  const { user, refreshToken, clear } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken)
      } catch {
        // ignore — tokens expire anyway
      }
    }
    clear()
    navigate('/login')
  }

  const navLink = ({ isActive }: { isActive: boolean }) =>
    `text-sm font-medium px-3 py-2 rounded-md transition-colors ${
      isActive
        ? 'bg-indigo-50 text-indigo-700'
        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    }`

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
          <div className="flex items-center gap-1">
            <Link to="/dashboard" className="font-semibold text-gray-900 text-sm mr-4">
              AI Error Debugger
            </Link>
            <NavLink to="/dashboard" className={navLink}>
              Dashboard
            </NavLink>
            <NavLink to="/history" className={navLink}>
              History
            </NavLink>
            <NavLink to="/billing" className={navLink}>
              Billing
            </NavLink>
          </div>

          <div className="flex items-center gap-3">
            {user && !user.is_verified && (
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-md">
                Email not verified
              </span>
            )}
            <span className="text-sm text-gray-500 hidden sm:block">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
    </div>
  )
}
