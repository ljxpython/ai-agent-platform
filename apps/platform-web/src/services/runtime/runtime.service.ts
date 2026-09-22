import { platformHttpClient } from '@/services/http/client'
import type {
  RuntimeModelItem,
  RuntimeModelsResponse,
  RuntimeToolsResponse
} from '@/types/management'

export type RuntimeModelInput = {
  provider: string
  display_name: string
  base_url: string
  protocol: string
  model: string
  api_key?: string
  enabled?: boolean
  scope_type?: 'platform' | 'project'
  project_id?: string | null
}

function buildRuntimeHeaders(projectId?: string) {
  const normalizedProjectId = projectId?.trim()
  return normalizedProjectId
    ? {
        'x-project-id': normalizedProjectId
      }
    : undefined
}

export async function listRuntimeModels(projectId?: string): Promise<RuntimeModelsResponse> {
  const response = await platformHttpClient.get('/api/runtime/models', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelsResponse
}

export async function listPlatformModels(): Promise<RuntimeModelsResponse> {
  const response = await platformHttpClient.get('/api/runtime/platform-models')
  return response.data as RuntimeModelsResponse
}

export async function createRuntimeModel(
  projectId: string,
  payload: RuntimeModelInput
): Promise<RuntimeModelItem> {
  const response = await platformHttpClient.post('/api/runtime/models', payload, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelItem
}

export async function updateRuntimeModel(
  projectId: string,
  modelId: string,
  payload: Partial<RuntimeModelInput>
): Promise<RuntimeModelItem> {
  const response = await platformHttpClient.patch(`/api/runtime/models/${encodeURIComponent(modelId)}`, payload, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeModelItem
}

export async function deleteRuntimeModel(
  projectId: string | undefined,
  modelId: string
): Promise<void> {
  await platformHttpClient.delete(`/api/runtime/models/${encodeURIComponent(modelId)}`, {
    headers: buildRuntimeHeaders(projectId)
  })
}

export async function listRuntimeTools(projectId?: string): Promise<RuntimeToolsResponse> {
  const response = await platformHttpClient.get('/api/runtime/tools', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeToolsResponse
}

export async function listRuntimeGraphs(projectId?: string): Promise<{ count: number; graphs: Array<{ graph_id: string; display_name?: string }> }> {
  const response = await platformHttpClient.get('/api/runtime/graphs', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data
}

export async function refreshRuntimeGraphs(projectId: string): Promise<{ count: number }> {
  const response = await platformHttpClient.post('/api/runtime/graphs/refresh', undefined, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data
}

export async function refreshRuntimeTools(projectId: string): Promise<{ count: number }> {
  const response = await platformHttpClient.post('/api/runtime/tools/refresh', undefined, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data
}
