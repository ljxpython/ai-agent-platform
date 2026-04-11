import { Client } from '@langchain/langgraph-sdk'
import {
  platformApiBaseUrl,
  refreshAccessToken,
  resolveAuthorizedAccessToken
} from '@/services/http/client'
import { getAccessToken } from '@/services/auth/token'
import { handleSessionExpired, hasStoredSession } from '@/services/auth/session-expiry'

function getLanggraphApiUrl() {
  const normalizedBase = platformApiBaseUrl.replace(/\/+$/, '')
  return normalizedBase.endsWith('/api/langgraph') ? normalizedBase : `${normalizedBase}/api/langgraph`
}

type LanggraphAuthorizedFetchOptions = {
  fetchImpl?: typeof fetch
  getAccessToken?: () => string
  refreshAccessToken?: () => Promise<string>
  hasStoredSession?: () => boolean
  onSessionExpired?: () => void
}

function withAccessToken(init: RequestInit | undefined, accessToken: string): RequestInit {
  const headers = new Headers(init?.headers)
  const normalizedToken = accessToken.trim()

  if (normalizedToken) {
    headers.set('Authorization', `Bearer ${normalizedToken}`)
  } else {
    headers.delete('Authorization')
  }

  return {
    ...init,
    headers
  }
}

export function createLanggraphAuthorizedFetch(options: LanggraphAuthorizedFetchOptions = {}) {
  const fetchImpl = options.fetchImpl ?? fetch
  const readAccessToken = options.getAccessToken ?? getAccessToken
  const renewAccessToken = options.refreshAccessToken ?? refreshAccessToken
  const readStoredSession = options.hasStoredSession ?? hasStoredSession
  const expireSession = options.onSessionExpired ?? handleSessionExpired

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const initialToken =
      (await resolveAuthorizedAccessToken()).trim() || readAccessToken().trim()
    const initialResponse = await fetchImpl(input, withAccessToken(init, initialToken))
    if (initialResponse.status !== 401) {
      return initialResponse
    }

    const nextAccessToken = (await renewAccessToken()).trim()
    if (!nextAccessToken) {
      if (readStoredSession()) {
        expireSession()
      }
      return initialResponse
    }

    const retryResponse = await fetchImpl(input, withAccessToken(init, nextAccessToken))
    if (retryResponse.status === 401 && readStoredSession()) {
      expireSession()
    }

    return retryResponse
  }
}

export function createLanggraphClient(projectId?: string): Client {
  const normalizedProjectId = projectId?.trim() || ''

  return new Client({
    apiUrl: getLanggraphApiUrl(),
    callerOptions: {
      fetch: createLanggraphAuthorizedFetch()
    },
    defaultHeaders: {
      ...(normalizedProjectId ? { 'x-project-id': normalizedProjectId } : {})
    }
  })
}

export { getLanggraphApiUrl }
