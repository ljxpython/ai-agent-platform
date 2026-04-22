import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { env } from '@/config/env'
import {
  getAccessToken,
  getRefreshToken,
  isAccessTokenExpiringSoon,
  setTokenSet
} from '@/services/auth/token'
import { handleSessionExpired, hasStoredSession } from '@/services/auth/session-expiry'
import type { AuthTokenSet } from '@/types/management'

type RetriableRequest = InternalAxiosRequestConfig & {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

export const platformApiBaseUrl = env.platformApiUrl
export const authRefreshPath = '/api/identity/session/refresh'

function mapRefreshPayload(payload: {
  access_token?: string
  refresh_token?: string
  token_type?: string
}): AuthTokenSet {
  return {
    accessToken: payload.access_token || '',
    refreshToken: payload.refresh_token || '',
    tokenType: payload.token_type || 'bearer'
  }
}

export async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken()
  const hadSession = hasStoredSession()

  if (!refreshToken) {
    if (hadSession) {
      handleSessionExpired()
    }
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
        `${platformApiBaseUrl}${authRefreshPath}`,
        { refresh_token: refreshToken },
        {
          timeout: env.requestTimeoutMs,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      )

      const tokenSet = mapRefreshPayload(response.data)

      setTokenSet(tokenSet)
      return tokenSet.accessToken
    } catch {
      if (hadSession) {
        handleSessionExpired()
      }
      return ''
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function resolveAuthorizedAccessToken(skewSeconds = 30): Promise<string> {
  const currentToken = getAccessToken()
  if (currentToken && !isAccessTokenExpiringSoon(currentToken, skewSeconds)) {
    return currentToken
  }

  if (!getRefreshToken()) {
    return currentToken
  }

  const refreshedToken = (await refreshAccessToken()).trim()
  return refreshedToken || currentToken
}

function createPlatformHttpClient() {
  const client = axios.create({
    baseURL: platformApiBaseUrl,
    timeout: env.requestTimeoutMs,
    headers: {
      'Content-Type': 'application/json'
    }
  })

  client.interceptors.request.use(async (config) => {
    const token = await resolveAuthorizedAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as RetriableRequest | undefined

      if (error.response?.status === 401 && originalRequest?._retry && hasStoredSession()) {
        handleSessionExpired()
      }

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
      return client(originalRequest)
    }
  )

  return client
}

export const platformHttpClient = createPlatformHttpClient()
