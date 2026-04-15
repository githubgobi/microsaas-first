import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { historyApi } from '../api/history'
import { Layout } from '../components/Layout'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import type { HistoryDetail, HistorySummary } from '../types'

function fmt(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function HistoryDetailPanel({ id }: { id: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['history', id],
    queryFn: () => historyApi.get(id).then((r) => r.data),
  })

  if (isLoading) return <p className="text-sm text-gray-400 mt-3">Loading…</p>
  if (!data) return null

  const d = data as HistoryDetail

  return (
    <div className="mt-4 pt-4 border-t border-gray-100 space-y-4">
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Summary
        </p>
        <p className="text-sm text-gray-700">{d.summary}</p>
      </div>
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Root cause
        </p>
        <p className="text-sm text-gray-700">{d.root_cause}</p>
      </div>
      {d.suggestions.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Suggestions
          </p>
          <ol className="space-y-2">
            {d.suggestions.map((s, i) => (
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
        {d.ai_model} · {d.tokens_used ?? '?'} tokens
        {d.duration_ms != null ? ` · ${(d.duration_ms / 1000).toFixed(1)}s` : ''}
      </p>
    </div>
  )
}

function HistoryRow({ item }: { item: HistorySummary }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: () => historyApi.delete(item.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['history-list'] }),
  })

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <button
          className="flex items-start gap-2 text-left flex-1 min-w-0"
          onClick={() => setOpen((o) => !o)}
        >
          <svg
            className={`h-4 w-4 text-gray-400 shrink-0 mt-0.5 transition-transform ${open ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="min-w-0">
            <p className="font-medium text-sm text-gray-900 truncate">{item.error_title}</p>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{item.summary}</p>
          </div>
        </button>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-gray-400 hidden sm:block">{fmt(item.created_at)}</span>
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

      {open && <HistoryDetailPanel id={item.id} />}
    </Card>
  )
}

export function HistoryPage() {
  const [page, setPage] = useState(1)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['history-list', page],
    queryFn: () => historyApi.list(page).then((r) => r.data),
  })

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">History</h1>
        <p className="text-sm text-gray-500 mt-0.5">All past AI analyses</p>
      </div>

      {isLoading && (
        <p className="text-sm text-gray-400 text-center py-12">Loading…</p>
      )}

      {isError && (
        <p className="text-sm text-red-600 text-center py-12">Failed to load history.</p>
      )}

      {data && data.items.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">📭</p>
          <p className="text-sm">No analyses yet. Go to Dashboard to submit an error.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="flex flex-col gap-3">
            {data.items.map((item) => (
              <HistoryRow key={item.id} item={item} />
            ))}
          </div>

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
