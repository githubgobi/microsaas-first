import type { TokenResponse, User } from '../types'
import { apiClient } from './client'

export const authApi = {
  register: (email: string, password: string) =>
    apiClient.post<User>('/auth/register', { email, password }),

  login: (email: string, password: string) =>
    apiClient.post<TokenResponse>('/auth/login', { email, password }),

  logout: (refresh_token: string) =>
    apiClient.post('/auth/logout', { refresh_token }),

  me: () => apiClient.get<User>('/auth/me'),

  verifyEmail: (token: string) =>
    apiClient.post('/auth/verify-email', { token }),

  resendVerification: (email: string) =>
    apiClient.post('/auth/resend-verification', { email }),

  forgotPassword: (email: string) =>
    apiClient.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, new_password: string) =>
    apiClient.post('/auth/reset-password', { token, new_password }),
}
