import { platformHttpClient } from '@/services/http/client'
import type {
  ManagementGraph,
  ManagementGraphListResponse,
  RuntimeGraphsResponse
} from '@/types/management'

function filterAndSliceGraphs(
  rows: ManagementGraphListResponse['items'],
  options?: { limit?: number; offset?: number; query?: string }
) {
  const normalizedQuery = options?.query?.trim().toLowerCase() || ''
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
    normalizedQuery,
    filtered,
    items: filtered.slice(offset, offset + limit),
    total: filtered.length
  }
}

export async function listGraphsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string }
): Promise<ManagementGraphListResponse> {
  if (!projectId) {
    return { items: [], total: 0, last_synced_at: null }
  }

  const payload = await platformHttpClient
    .get('/api/runtime/graphs', {
      headers: {
        'x-project-id': projectId
      }
    })
    .then((response) => response.data as RuntimeGraphsResponse)

  const normalizedRows = Array.isArray(payload.graphs)
    ? payload.graphs.filter((item) => typeof item.graph_id === 'string' && item.graph_id.trim().length > 0)
    : []

  const filtered = filterAndSliceGraphs(normalizedRows, options)

  return {
    items: filtered.items,
    total: filtered.normalizedQuery.length > 0 ? filtered.total : payload.count ?? filtered.total,
    last_synced_at: payload.last_synced_at ?? null
  }
}

export async function getGraphCatalogItem(
  projectId: string,
  graphId: string
): Promise<ManagementGraph | null> {
  const normalizedGraphId = graphId.trim()
  if (!projectId || !normalizedGraphId) {
    return null
  }

  const payload = await listGraphsPage(
    projectId,
    {
      limit: 200,
      offset: 0,
      query: normalizedGraphId
    }
  )

  return (
    payload.items.find((item) => item.graph_id?.trim() === normalizedGraphId) || null
  )
}
