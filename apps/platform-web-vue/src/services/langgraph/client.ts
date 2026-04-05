import { Client } from '@langchain/langgraph-sdk'
import { env } from '@/config/env'
import { getAccessToken } from '@/services/auth/token'

function getLanggraphApiUrl() {
  const normalizedBase = env.platformApiUrl.replace(/\/+$/, '')
  return normalizedBase.endsWith('/api/langgraph') ? normalizedBase : `${normalizedBase}/api/langgraph`
}

export function createLanggraphClient(projectId?: string): Client {
  const accessToken = getAccessToken()

  return new Client({
    apiUrl: getLanggraphApiUrl(),
    defaultHeaders: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(projectId?.trim() ? { 'x-project-id': projectId.trim() } : {})
    }
  })
}

export { getLanggraphApiUrl }
