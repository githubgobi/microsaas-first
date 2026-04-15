import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="border-b border-gray-100">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
          <span className="font-semibold text-gray-900">AI Error Debugger</span>
          <div className="flex items-center gap-3">
            <Link to="/login">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link to="/register">
              <Button size="sm">Get started</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-3xl mx-auto px-4 pt-24 pb-16 text-center">
        <span className="inline-block text-xs font-semibold text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full mb-6">
          AI-powered debugging
        </span>
        <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight mb-6">
          Debug API errors<br />in seconds
        </h1>
        <p className="text-lg text-gray-500 mb-10 max-w-xl mx-auto">
          Paste your error, get an instant AI-powered root cause analysis and
          actionable fix suggestions — no more stack overflow spelunking.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link to="/register">
            <Button size="lg">Start for free</Button>
          </Link>
          <Link to="/login">
            <Button variant="secondary" size="lg">Sign in</Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-4 pb-24">
        <div className="grid sm:grid-cols-3 gap-6">
          {[
            {
              title: 'Instant analysis',
              desc: 'Submit any API error and get a structured diagnosis — summary, root cause, and ranked fix suggestions.',
            },
            {
              title: 'Full history',
              desc: 'Every analysis is stored. Browse past errors, compare solutions, and track your debugging patterns.',
            },
            {
              title: 'Context-aware',
              desc: 'Attach metadata like language, environment, and service name to get more targeted recommendations.',
            },
          ].map((f) => (
            <div key={f.title} className="bg-gray-50 rounded-xl p-6 border border-gray-100">
              <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
