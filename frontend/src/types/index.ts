export interface User {
  id: string
  email: string
  is_verified: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export type ErrorStatusValue = 'pending' | 'analyzing' | 'completed' | 'failed'

export interface ErrorSummary {
  id: string
  title: string
  status: ErrorStatusValue
  created_at: string
}

export interface ErrorDetail {
  id: string
  user_id: string
  title: string
  raw_error: string
  context: Record<string, unknown> | null
  status: ErrorStatusValue
  created_at: string
}

export interface AnalysisData {
  id: string
  summary: string
  root_cause: string
  suggestions: Array<Record<string, unknown>>
  ai_model: string
  tokens_used: number | null
  duration_ms: number | null
  created_at: string
}

export interface AnalysisResultResponse {
  error_id: string
  status: ErrorStatusValue
  analysis: AnalysisData | null
}

export interface HistorySummary {
  id: string
  error_id: string
  error_title: string
  summary: string
  ai_model: string
  tokens_used: number | null
  created_at: string
}

export interface HistoryDetail extends HistorySummary {
  root_cause: string
  suggestions: Array<Record<string, unknown>>
  duration_ms: number | null
}

export interface PagedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export type PlanTier = 'free' | 'pro'

export interface SubscriptionResponse {
  plan: PlanTier
  status: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}
