import type { HistoryDetail, HistorySummary, PagedResponse } from '../types'
import { apiClient } from './client'

export const historyApi = {
  list: (page = 1, page_size = 20) =>
    apiClient.get<PagedResponse<HistorySummary>>('/history', {
      params: { page, page_size },
    }),

  get: (id: string) => apiClient.get<HistoryDetail>(`/history/${id}`),

  delete: (id: string) => apiClient.delete(`/history/${id}`),
}
