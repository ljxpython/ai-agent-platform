import { Client } from '@langchain/langgraph-sdk'
import { getPlatformAccessToken, getPlatformApiBaseUrl } from '@/services/platform/control-plane'

function getLanggraphApiUrl() {
  const normalizedBase = getPlatformApiBaseUrl('runtime_gateway').replace(/\/+$/, '')
  return normalizedBase.endsWith('/api/langgraph') ? normalizedBase : `${normalizedBase}/api/langgraph`
}

export function createLanggraphClient(projectId?: string): Client {
  const accessToken = getPlatformAccessToken('runtime_gateway')

  return new Client({
    apiUrl: getLanggraphApiUrl(),
    defaultHeaders: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(projectId?.trim() ? { 'x-project-id': projectId.trim() } : {})
    }
  })
}

export { getLanggraphApiUrl }
