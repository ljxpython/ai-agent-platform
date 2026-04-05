import { httpClient } from '@/services/http/client'
import type { ManagementAssistant, ManagementAssistantListResponse } from '@/types/management'

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

export async function createAssistant(
  projectId: string,
  payload: {
    graph_id: string
    name: string
    description?: string
    assistant_id?: string
    config?: Record<string, unknown>
    context?: Record<string, unknown>
    metadata?: Record<string, unknown>
  }
): Promise<ManagementAssistant> {
  const response = await httpClient.post(`/_management/projects/${projectId}/assistants`, payload, {
    headers: {
      'x-project-id': projectId
    }
  })

  return response.data as ManagementAssistant
}

export async function getAssistant(
  assistantId: string,
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await httpClient.get(`/_management/assistants/${assistantId}`, {
    headers: projectId
      ? {
          'x-project-id': projectId
        }
      : undefined
  })

  return response.data as ManagementAssistant
}

export async function updateAssistant(
  assistantId: string,
  payload: {
    graph_id?: string
    name?: string
    description?: string
    status?: 'active' | 'disabled'
    config?: Record<string, unknown>
    context?: Record<string, unknown>
    metadata?: Record<string, unknown>
  },
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await httpClient.patch(`/_management/assistants/${assistantId}`, payload, {
    headers: projectId
      ? {
          'x-project-id': projectId
        }
      : undefined
  })

  return response.data as ManagementAssistant
}

export async function resyncAssistant(
  assistantId: string,
  projectId?: string
): Promise<ManagementAssistant> {
  const response = await httpClient.post(
    `/_management/assistants/${assistantId}/resync`,
    {},
    {
      headers: projectId
        ? {
            'x-project-id': projectId
          }
        : undefined
    }
  )

  return response.data as ManagementAssistant
}

export async function getAssistantParameterSchema(
  graphId: string,
  projectId?: string
): Promise<Record<string, unknown>> {
  const response = await httpClient.get(
    `/_management/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`,
    {
      headers: projectId
        ? {
            'x-project-id': projectId
          }
        : undefined
    }
  )

  return response.data as Record<string, unknown>
}
