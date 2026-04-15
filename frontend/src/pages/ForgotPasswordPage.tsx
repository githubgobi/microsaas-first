import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/auth'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authApi.forgotPassword(email)
    } catch {
      // Always show success to prevent email enumeration
    } finally {
      setLoading(false)
      setSubmitted(true)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <Link to="/" className="text-lg font-semibold text-gray-900">
            AI Error Debugger
          </Link>
          <p className="text-sm text-gray-500 mt-1">Reset your password</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          {submitted ? (
            <div className="text-center py-4">
              <p className="text-sm text-gray-600">
                If an account with that email exists, a reset link has been sent. Check
                your inbox.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <p className="text-sm text-gray-500">
                Enter your email and we'll send you a reset link.
              </p>
              <Input
                label="Email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Button type="submit" loading={loading} className="w-full">
                Send reset link
              </Button>
            </form>
          )}
        </div>

        <p className="text-center text-sm text-gray-500 mt-4">
          <Link to="/login" className="text-indigo-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
