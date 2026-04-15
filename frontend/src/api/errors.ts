import type {
  AnalysisResultResponse,
  ErrorDetail,
  ErrorSummary,
  PagedResponse,
} from '../types'
import { apiClient } from './client'

export const errorsApi = {
  submit: (title: string, raw_error: string, context?: Record<string, unknown>) =>
    apiClient.post<ErrorDetail>('/errors', { title, raw_error, context }),

  list: (page = 1, page_size = 20) =>
    apiClient.get<PagedResponse<ErrorSummary>>('/errors', {
      params: { page, page_size },
    }),

  get: (id: string) => apiClient.get<ErrorDetail>(`/errors/${id}`),

  delete: (id: string) => apiClient.delete(`/errors/${id}`),

  triggerAnalysis: (errorId: string) =>
    apiClient.post(`/errors/${errorId}/analyze`),

  getAnalysis: (errorId: string) =>
    apiClient.get<AnalysisResultResponse>(`/errors/${errorId}/analysis`),
}
