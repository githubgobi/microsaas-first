import type { SubscriptionResponse } from '../types'
import { apiClient } from './client'

export const billingApi = {
  getSubscription: () => apiClient.get<SubscriptionResponse>('/billing/subscription'),

  createCheckout: () =>
    apiClient.post<{ checkout_url: string }>('/billing/checkout'),

  createPortal: () =>
    apiClient.post<{ portal_url: string }>('/billing/portal'),
}
