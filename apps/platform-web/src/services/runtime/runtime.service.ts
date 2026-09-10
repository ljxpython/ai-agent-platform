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

export async function listRuntimeTools(projectId?: string): Promise<RuntimeToolsResponse> {
  const response = await platformHttpClient.get('/api/runtime/tools', {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data as RuntimeToolsResponse
}

export async function refreshRuntimeGraphs(projectId: string): Promise<{ count: number }> {
  const response = await platformHttpClient.post('/api/runtime/graphs/refresh', undefined, {
    headers: buildRuntimeHeaders(projectId)
  })
  return response.data
}
