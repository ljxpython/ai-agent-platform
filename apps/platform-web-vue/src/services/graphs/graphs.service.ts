import { httpClient } from '@/services/http/client'
import type { ManagementGraphListResponse } from '@/types/management'

type GraphRefreshResponse = {
  ok: boolean
  count: number
  last_synced_at: string | null
}

export async function listGraphsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string }
): Promise<ManagementGraphListResponse> {
  if (!projectId) {
    return { items: [], total: 0, last_synced_at: null }
  }

  const response = await httpClient.get('/_management/catalog/graphs', {
    headers: {
      'x-project-id': projectId
    }
  })

  const payload = response.data as ManagementGraphListResponse
  const normalizedQuery = options?.query?.trim().toLowerCase() || ''
  const rows = Array.isArray(payload.items) ? payload.items : []
  const filtered = normalizedQuery
    ? rows.filter((item) => {
        const graphId = item.graph_id?.toLowerCase() || ''
        const displayName = item.display_name?.toLowerCase() || ''
        const description = item.description?.toLowerCase() || ''
        return (
          graphId.includes(normalizedQuery) ||
          displayName.includes(normalizedQuery) ||
          description.includes(normalizedQuery)
        )
      })
    : rows

  const limit = options?.limit ?? 20
  const offset = options?.offset ?? 0

  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
    last_synced_at: payload.last_synced_at ?? null
  }
}

export async function refreshGraphsCatalog(projectId?: string): Promise<GraphRefreshResponse> {
  const response = await httpClient.post(
    '/_management/catalog/graphs/refresh',
    {},
    {
      headers: projectId
        ? {
            'x-project-id': projectId
          }
        : undefined
    }
  )

  return response.data as GraphRefreshResponse
}
