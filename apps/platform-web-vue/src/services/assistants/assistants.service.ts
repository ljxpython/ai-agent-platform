import { httpClient } from '@/services/http/client'
import type { ManagementAssistantListResponse } from '@/types/management'

export async function listAssistantsPage(
  projectId: string,
  options?: {
    limit?: number
    offset?: number
    query?: string
    graphId?: string
  }
): Promise<ManagementAssistantListResponse> {
  if (!projectId) {
    return { items: [], total: 0 }
  }

  const response = await httpClient.get(`/_management/projects/${projectId}/assistants`, {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      graph_id: options?.graphId?.trim() || undefined
    },
    headers: {
      'x-project-id': projectId
    }
  })

  return response.data as ManagementAssistantListResponse
}
