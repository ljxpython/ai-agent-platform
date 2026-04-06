import { httpClient, platformV2HttpClient } from '@/services/http/client'
import {
  submitOperation,
  waitForOperationTerminalState
} from '@/services/operations/operations.service'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type {
  ManagementAssistant,
  ManagementAssistantListResponse,
  ManagementOperation
} from '@/types/management'

export type AssistantServiceMode = 'legacy' | 'runtime'

type AssistantServiceOptions = {
  mode?: AssistantServiceMode
}

function useRuntimeAssistantsApi(options?: AssistantServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('assistants') === 'v2'
}

function getProjectHeaders(projectId?: string) {
  return projectId
    ? {
        'x-project-id': projectId
      }
    : undefined
}

export async function listAssistantsPage(
  projectId: string,
  options?: {
    limit?: number
    offset?: number
    query?: string
    graphId?: string
  },
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistantListResponse> {
  if (!projectId) {
    return { items: [], total: 0 }
  }

  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/projects/${projectId}/assistants`
    : `/_management/projects/${projectId}/assistants`

  const response = await client.get(endpoint, {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      graph_id: options?.graphId?.trim() || undefined
    },
    headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
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
  },
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistant> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/projects/${projectId}/assistants`
    : `/_management/projects/${projectId}/assistants`
  const response = await client.post(endpoint, payload, {
    headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
  })

  return response.data as ManagementAssistant
}

export async function getAssistant(
  assistantId: string,
  projectId?: string,
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistant> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/assistants/${assistantId}`
    : `/_management/assistants/${assistantId}`
  const response = await client.get(endpoint, {
    headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
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
  projectId?: string,
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistant> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/assistants/${assistantId}`
    : `/_management/assistants/${assistantId}`
  const response = await client.patch(endpoint, payload, {
    headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
  })

  return response.data as ManagementAssistant
}

export async function resyncAssistant(
  assistantId: string,
  projectId?: string,
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistant> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/assistants/${assistantId}/resync`
    : `/_management/assistants/${assistantId}/resync`
  const response = await client.post(
    endpoint,
    {},
    {
      headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
    }
  )

  return response.data as ManagementAssistant
}

export async function resyncAssistantByOperation(
  assistantId: string,
  projectId: string,
  options?: {
    idempotencyKey?: string
  }
): Promise<ManagementOperation> {
  const submitted = await submitOperation({
    kind: 'assistant.resync',
    project_id: projectId,
    idempotency_key: options?.idempotencyKey,
    input_payload: {
      assistant_id: assistantId
    }
  })
  return waitForOperationTerminalState(submitted.id, {
    pollMs: 1000,
    timeoutMs: 60000
  })
}

export async function deleteAssistant(
  assistantId: string,
  options?: {
    deleteRuntime?: boolean
    deleteThreads?: boolean
  },
  projectId?: string,
  requestOptions?: AssistantServiceOptions
): Promise<{ ok: boolean }> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/assistants/${assistantId}`
    : `/_management/assistants/${assistantId}`
  const response = await client.delete(endpoint, {
    params: {
      delete_runtime: options?.deleteRuntime || undefined,
      delete_threads: options?.deleteThreads || undefined
    },
    headers: useRuntimeApi ? undefined : getProjectHeaders(projectId)
  })

  return response.data as { ok: boolean }
}

export async function getAssistantParameterSchema(
  graphId: string,
  projectId?: string,
  requestOptions?: AssistantServiceOptions
): Promise<Record<string, unknown>> {
  const useRuntimeApi = useRuntimeAssistantsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`
    : `/_management/graphs/${encodeURIComponent(graphId)}/assistant-parameter-schema`
  const response = await client.get(
    endpoint,
    {
      headers: getProjectHeaders(projectId)
    }
  )

  return response.data as Record<string, unknown>
}

export async function findAssistantByTargetId(
  projectId: string,
  targetAssistantId: string,
  requestOptions?: AssistantServiceOptions
): Promise<ManagementAssistant | null> {
  const normalizedTargetId = targetAssistantId.trim()
  if (!projectId || !normalizedTargetId) {
    return null
  }

  const payload = await listAssistantsPage(
    projectId,
    {
      limit: 50,
      offset: 0,
      query: normalizedTargetId
    },
    requestOptions
  )

  return (
    payload.items.find((item) => {
      const assistantId = item.id?.trim() || ''
      const langgraphAssistantId = item.langgraph_assistant_id?.trim() || ''
      return assistantId === normalizedTargetId || langgraphAssistantId === normalizedTargetId
    }) || null
  )
}
