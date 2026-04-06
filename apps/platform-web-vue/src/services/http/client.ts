import axios from 'axios'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { env } from '@/config/env'
import {
  clearTokenSet,
  getAccessToken,
  getRefreshToken,
  setTokenSet,
  type AuthTokenScope
} from '@/services/auth/token'
import type { AuthTokenSet } from '@/types/management'

type RetriableRequest = InternalAxiosRequestConfig & {
  _retry?: boolean
}

const refreshPromises: Partial<Record<AuthTokenScope, Promise<string> | null>> = {}

type ScopeConfig = {
  baseUrl: string
  refreshPath: string
  mapRefreshPayload: (payload: {
    access_token?: string
    refresh_token?: string
    token_type?: string
  }) => AuthTokenSet
}

const scopeConfig: Record<AuthTokenScope, ScopeConfig> = {
  legacy: {
    baseUrl: env.platformApiUrl,
    refreshPath: '/_management/auth/refresh',
    mapRefreshPayload: (payload) => ({
      accessToken: payload.access_token || '',
      refreshToken: payload.refresh_token || '',
      tokenType: payload.token_type || 'bearer'
    })
  },
  v2: {
    baseUrl: env.platformApiV2Url,
    refreshPath: '/api/identity/session/refresh',
    mapRefreshPayload: (payload) => ({
      accessToken: payload.access_token || '',
      refreshToken: payload.refresh_token || '',
      tokenType: payload.token_type || 'bearer'
    })
  }
}

async function refreshAccessToken(scope: AuthTokenScope): Promise<string> {
  const refreshToken = getRefreshToken(scope)
  if (!refreshToken) {
    clearTokenSet(scope)
    return ''
  }

  if (refreshPromises[scope]) {
    return refreshPromises[scope] as Promise<string>
  }

  const config = scopeConfig[scope]
  refreshPromises[scope] = (async () => {
    try {
      const response = await axios.post<{
        access_token: string
        refresh_token: string
        token_type?: string
      }>(
        `${config.baseUrl}${config.refreshPath}`,
        { refresh_token: refreshToken },
        {
          timeout: env.requestTimeoutMs,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      )

      const tokenSet = config.mapRefreshPayload(response.data)

      setTokenSet(tokenSet, scope)
      return tokenSet.accessToken
    } catch {
      clearTokenSet(scope)
      return ''
    } finally {
      refreshPromises[scope] = null
    }
  })()

  return refreshPromises[scope] as Promise<string>
}

function createScopedHttpClient(scope: AuthTokenScope) {
  const client = axios.create({
    baseURL: scopeConfig[scope].baseUrl,
    timeout: env.requestTimeoutMs,
    headers: {
      'Content-Type': 'application/json'
    }
  })

  client.interceptors.request.use((config) => {
    const token = getAccessToken(scope)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as RetriableRequest | undefined

      if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
        return Promise.reject(error)
      }

      originalRequest._retry = true
      const nextToken = await refreshAccessToken(scope)
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

export const httpClient = createScopedHttpClient('legacy')
export const platformV2HttpClient = createScopedHttpClient('v2')

export const legacyBaseUrl = scopeConfig.legacy.baseUrl
export const platformV2BaseUrl = scopeConfig.v2.baseUrl

export const legacyAuthRefreshPath = scopeConfig.legacy.refreshPath
export const platformV2AuthRefreshPath = scopeConfig.v2.refreshPath
