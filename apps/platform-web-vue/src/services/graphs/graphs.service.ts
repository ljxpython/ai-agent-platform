import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type {
  ManagementGraph,
  ManagementGraphListResponse,
  RuntimeGraphsResponse,
  RuntimeRefreshResponse
} from '@/types/management'

type GraphRefreshResponse = RuntimeRefreshResponse

export type GraphServiceMode = 'legacy' | 'runtime'

type GraphServiceOptions = {
  mode?: GraphServiceMode
}

function useRuntimeGraphsApi(options?: GraphServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('runtime_gateway') === 'v2'
}

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

async function listLegacyCatalogGraphsFallback(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string }
): Promise<ManagementGraphListResponse> {
  const response = await httpClient.get('/_management/catalog/graphs', {
    headers: {
      'x-project-id': projectId
    }
  })
  const payload = response.data as ManagementGraphListResponse
  const rows = Array.isArray(payload.items) ? payload.items : []
  const filtered = filterAndSliceGraphs(rows, options)

  return {
    items: filtered.items,
    total: filtered.total,
    last_synced_at: payload.last_synced_at ?? null
  }
}

export async function listGraphsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string },
  requestOptions?: GraphServiceOptions
): Promise<ManagementGraphListResponse> {
  if (!projectId) {
    return { items: [], total: 0, last_synced_at: null }
  }

  if (useRuntimeGraphsApi(requestOptions)) {
    try {
      const payload = await platformV2HttpClient
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
    } catch {
      return await listLegacyCatalogGraphsFallback(projectId, options)
    }
  }

  const response = await httpClient.get('/_management/catalog/graphs', {
    headers: {
      'x-project-id': projectId
    }
  })

  const payload = response.data as ManagementGraphListResponse
  const rows = Array.isArray(payload.items) ? payload.items : []
  const filtered = filterAndSliceGraphs(rows, options)

  return {
    items: filtered.items,
    total: filtered.total,
    last_synced_at: payload.last_synced_at ?? null
  }
}

export async function refreshGraphsCatalog(
  projectId?: string,
  requestOptions?: GraphServiceOptions
): Promise<GraphRefreshResponse> {
  if (projectId && useRuntimeGraphsApi(requestOptions)) {
    try {
      const response = await platformV2HttpClient.post(
        '/api/runtime/graphs/refresh',
        {},
        {
          headers: {
            'x-project-id': projectId
          }
        }
      )
      return response.data as GraphRefreshResponse
    } catch {
      return await refreshGraphsCatalog(projectId)
    }
  }

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

export async function getGraphCatalogItem(
  projectId: string,
  graphId: string,
  requestOptions?: GraphServiceOptions
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
    },
    requestOptions
  )

  return (
    payload.items.find((item) => item.graph_id?.trim() === normalizedGraphId) || null
  )
}
