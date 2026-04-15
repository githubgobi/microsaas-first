import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()

  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.resetPassword(token, password)
      navigate('/login', {
        state: { message: 'Password reset. Sign in with your new password.' },
      })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-red-600 text-sm mb-4">Invalid or missing reset token.</p>
          <Link to="/forgot-password" className="text-indigo-600 hover:underline text-sm">
            Request a new link
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Link to="/" className="text-lg font-semibold text-gray-900">
            AI Error Debugger
          </Link>
          <p className="text-sm text-gray-500 mt-1">Choose a new password</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {error}
              </div>
            )}
            <Input
              label="New password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-xs text-gray-400">Minimum 8 characters</p>
            <Button type="submit" loading={loading} className="w-full">
              Reset password
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
