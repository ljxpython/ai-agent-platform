import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { env } from '@/config/env'
import { clearTokenSet, getAccessToken, getRefreshToken, setTokenSet } from '@/services/auth/token'
import type { AuthTokenSet } from '@/types/management'

type RetriableRequest = InternalAxiosRequestConfig & {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    clearTokenSet()
    return ''
  }

  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    try {
      const response = await axios.post<{
        access_token: string
        refresh_token: string
        token_type?: string
      }>(
        `${env.platformApiUrl}/_management/auth/refresh`,
        { refresh_token: refreshToken },
        {
          timeout: env.requestTimeoutMs,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      )

      const payload = response.data
      const tokenSet: AuthTokenSet = {
        accessToken: payload.access_token,
        refreshToken: payload.refresh_token,
        tokenType: payload.token_type || 'bearer'
      }

      setTokenSet(tokenSet)
      return tokenSet.accessToken
    } catch {
      clearTokenSet()
      return ''
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export const httpClient = axios.create({
  baseURL: env.platformApiUrl,
  timeout: env.requestTimeoutMs,
  headers: {
    'Content-Type': 'application/json'
  }
})

httpClient.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableRequest | undefined

    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    originalRequest._retry = true
    const nextToken = await refreshAccessToken()
    if (!nextToken) {
      return Promise.reject(error)
    }

    originalRequest.headers = originalRequest.headers || {}
    originalRequest.headers.Authorization = `Bearer ${nextToken}`
    return httpClient(originalRequest)
  }
)
