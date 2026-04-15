import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { errorsApi } from '../api/errors'
import { getErrorMessage } from '../api/client'
import { Layout } from '../components/Layout'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input, Textarea } from '../components/ui/Input'
import type { AnalysisData, ErrorStatusValue, ErrorSummary } from '../types'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const STATUS_STYLE: Record<ErrorStatusValue, string> = {
  pending: 'bg-gray-100 text-gray-600',
  analyzing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

// ── submit modal ──────────────────────────────────────────────────────────────

function SubmitModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [rawError, setRawError] = useState('')
  const [formErr, setFormErr] = useState('')

  const { mutate, isPending } = useMutation({
    mutationFn: () => errorsApi.submit(title.trim(), rawError).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['errors'] })
      onClose()
    },
    onError: (err) => setFormErr(getErrorMessage(err)),
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-20 p-4">
      <Card className="w-full max-w-xl p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Submit new error</h2>

        {formErr && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2 mb-4">
            {formErr}
          </div>
        )}

        <div className="flex flex-col gap-4">
          <Input
            label="Title"
            placeholder="e.g. Stripe webhook 400 on checkout.session.completed"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Textarea
            label="Error / stack trace"
            placeholder="Paste the full error message or stack trace here…"
            rows={10}
            value={rawError}
            onChange={(e) => setRawError(e.target.value)}
          />
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="secondary" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button
            loading={isPending}
            disabled={!title.trim() || !rawError.trim()}
            onClick={() => mutate()}
          >
            Submit
          </Button>
        </div>
      </Card>
    </div>
  )
}

// ── analysis panel ────────────────────────────────────────────────────────────

function AnalysisPanel({ errorId, status }: { errorId: string; status: ErrorStatusValue }) {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['analysis', errorId],
    queryFn: () => errorsApi.getAnalysis(errorId).then((r) => r.data),
    enabled: status === 'completed' || status === 'analyzing' || status === 'failed',
    refetchInterval: status === 'analyzing' ? 2000 : false,
    // When analysis completes, refresh the error list to update status badge
    select: (d) => {
      if (d.status === 'completed' || d.status === 'failed') {
        qc.invalidateQueries({ queryKey: ['errors'] })
      }
      return d
    },
  })

  const triggerMutation = useMutation({
    mutationFn: () => errorsApi.triggerAnalysis(errorId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['errors'] })
      qc.invalidateQueries({ queryKey: ['analysis', errorId] })
    },
  })

  if (status === 'pending') {
    return (
      <div className="mt-3 pt-3 border-t border-gray-100">
        <Button
          size="sm"
          loading={triggerMutation.isPending}
          onClick={() => triggerMutation.mutate()}
        >
          Analyze with AI
        </Button>
        {triggerMutation.isError && (
          <p className="text-xs text-red-600 mt-2">
            {getErrorMessage(triggerMutation.error)}
          </p>
        )}
      </div>
    )
  }

  if (status === 'analyzing' || isLoading) {
    return (
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-sm text-blue-600 flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Analysing…
        </p>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-sm text-red-600">Analysis failed.</p>
        <Button
          size="sm"
          variant="secondary"
          className="mt-2"
          loading={triggerMutation.isPending}
          onClick={() => triggerMutation.mutate()}
        >
          Retry
        </Button>
      </div>
    )
  }

  const analysis = data?.analysis as AnalysisData | null
  if (!analysis) return null

  return (
    <div className="mt-3 pt-3 border-t border-gray-100 space-y-4">
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Summary
        </p>
        <p className="text-sm text-gray-700">{analysis.summary}</p>
      </div>
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Root cause
        </p>
        <p className="text-sm text-gray-700">{analysis.root_cause}</p>
      </div>
      {analysis.suggestions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Suggestions
          </p>
          <ol className="space-y-2">
            {analysis.suggestions.map((s, i) => (
              <li key={i} className="text-sm bg-gray-50 rounded-md p-3 border border-gray-100">
                {typeof s.title === 'string' && (
                  <p className="font-medium text-gray-800 mb-1">{s.title}</p>
                )}
                {typeof s.description === 'string' && (
                  <p className="text-gray-600">{s.description}</p>
                )}
                {typeof s.code === 'string' && (
                  <pre className="mt-2 text-xs bg-gray-900 text-green-300 rounded p-2 overflow-x-auto">
                    {s.code}
                  </pre>
                )}
                {!s.title && !s.description && (
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                    {JSON.stringify(s, null, 2)}
                  </pre>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="text-xs text-gray-400">
        {analysis.ai_model} · {analysis.tokens_used ?? '?'} tokens
        {analysis.duration_ms != null ? ` · ${(analysis.duration_ms / 1000).toFixed(1)}s` : ''}
      </p>
    </div>
  )
}

// ── error row ─────────────────────────────────────────────────────────────────

function ErrorRow({ error, onDelete }: { error: ErrorSummary; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  const qc = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => errorsApi.delete(error.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['errors'] }),
  })

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <button
          className="flex items-center gap-2 text-left flex-1 min-w-0"
          onClick={() => setOpen((o) => !o)}
        >
          <svg
            className={`h-4 w-4 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="font-medium text-sm text-gray-900 truncate">{error.title}</span>
        </button>

        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[error.status]}`}
          >
            {error.status}
          </span>
          <span className="text-xs text-gray-400">{fmt(error.created_at)}</span>
          <button
            className="text-gray-400 hover:text-red-500 transition-colors"
            title="Delete"
            onClick={() => deleteMutation.mutate()}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {open && <AnalysisPanel errorId={error.id} status={error.status} />}
    </Card>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const [showModal, setShowModal] = useState(false)
  const [page, setPage] = useState(1)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['errors', page],
    queryFn: () => errorsApi.list(page).then((r) => r.data),
  })

  return (
    <Layout>
      {showModal && <SubmitModal onClose={() => setShowModal(false)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Submit errors and run AI analysis
          </p>
        </div>
        <Button onClick={() => setShowModal(true)}>+ New error</Button>
      </div>

      {isLoading && (
        <p className="text-sm text-gray-400 text-center py-12">Loading…</p>
      )}

      {isError && (
        <p className="text-sm text-red-600 text-center py-12">Failed to load errors.</p>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">🐛</p>
          <p className="text-sm">No errors yet. Submit one to get started.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="flex flex-col gap-3">
            {data.items.map((err) => (
              <ErrorRow key={err.id} error={err} onDelete={() => {}} />
            ))}
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-6">
              <Button
                variant="secondary"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </Button>
              <span className="text-sm text-gray-500">
                {page} / {data.pages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </Button>
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
