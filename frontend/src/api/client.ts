import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach access token to every outgoing request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Queue of callbacks waiting for a fresh token
let refreshing = false
let waitQueue: Array<(token: string) => void> = []

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error)
    }

    // Refresh call itself returned 401 — tokens are invalid, sign out
    if ((original.url as string)?.includes('/auth/refresh')) {
      useAuthStore.getState().clear()
      window.location.href = '/login'
      return Promise.reject(error)
    }

    if (refreshing) {
      // Serialise retries behind the in-progress refresh
      return new Promise((resolve) => {
        waitQueue.push((token) => {
          original.headers.Authorization = `Bearer ${token}`
          resolve(apiClient(original))
        })
      })
    }

    original._retry = true
    refreshing = true

    try {
      const rt = useAuthStore.getState().refreshToken
      if (!rt) throw new Error('no refresh token')

      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: rt,
      })

      useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
      waitQueue.forEach((cb) => cb(data.access_token))
      waitQueue = []

      original.headers.Authorization = `Bearer ${data.access_token}`
      return apiClient(original)
    } catch {
      useAuthStore.getState().clear()
      window.location.href = '/login'
      return Promise.reject(error)
    } finally {
      refreshing = false
    }
  },
)

/** Extract a human-readable message from an Axios error. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d.msg ?? d).join(', ')
  }
  return 'An unexpected error occurred'
}
