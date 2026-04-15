import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/auth'
import { Button } from '../components/ui/Button'

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setErrorMsg('No verification token found in the URL.')
      return
    }
    authApi
      .verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((err) => {
        setStatus('error')
        import('../api/client').then(({ getErrorMessage }) =>
          setErrorMsg(getErrorMessage(err)),
        )
      })
  }, [token])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        {status === 'loading' && (
          <p className="text-gray-500 text-sm">Verifying your email…</p>
        )}

        {status === 'success' && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
            <div className="text-4xl mb-4">✅</div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Email verified</h2>
            <p className="text-sm text-gray-500 mb-6">Your account is now active.</p>
            <Link to="/login">
              <Button className="w-full">Sign in</Button>
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
            <div className="text-4xl mb-4">❌</div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Verification failed</h2>
            <p className="text-sm text-red-600 mb-6">{errorMsg}</p>
            <Link to="/login">
              <Button variant="secondary" className="w-full">
                Back to sign in
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
