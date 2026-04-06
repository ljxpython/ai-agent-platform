import {
  getPlatformHttpClient,
  resolvePlatformClientScope
} from '@/services/platform/control-plane'
import {
  submitOperation,
  waitForOperationTerminalState
} from '@/services/operations/operations.service'
import type {
  ManagementOperation,
  RuntimeModelsResponse,
  RuntimeRefreshResponse,
  RuntimeToolsResponse
} from '@/types/management'

function buildRuntimeHeaders(projectId?: string) {
  const normalizedProjectId = projectId?.trim()
  return normalizedProjectId
    ? {
        'x-project-id': normalizedProjectId
      }
    : undefined
}

function runtimePath(v2Path: string, legacyPath: string) {
  return resolvePlatformClientScope('runtime_catalog') === 'v2' ? v2Path : legacyPath
}

function runtimeOperationKind(resource: 'models' | 'tools' | 'graphs') {
  return `runtime.${resource}.refresh`
}

export async function listRuntimeModels(projectId?: string): Promise<RuntimeModelsResponse> {
  const response = await getPlatformHttpClient('runtime_catalog').get(
    runtimePath('/api/runtime/models', '/_management/runtime/models'),
    {
      headers: buildRuntimeHeaders(projectId)
    }
  )
  return response.data as RuntimeModelsResponse
}

export async function refreshRuntimeModels(projectId?: string): Promise<RuntimeRefreshResponse> {
  const response = await getPlatformHttpClient('runtime_catalog').post(
    runtimePath('/api/runtime/models/refresh', '/_management/catalog/models/refresh'),
    {},
    {
      headers: buildRuntimeHeaders(projectId)
    }
  )
  return response.data as RuntimeRefreshResponse
}

export async function listRuntimeTools(projectId?: string): Promise<RuntimeToolsResponse> {
  const response = await getPlatformHttpClient('runtime_catalog').get(
    runtimePath('/api/runtime/tools', '/_management/runtime/tools'),
    {
      headers: buildRuntimeHeaders(projectId)
    }
  )
  return response.data as RuntimeToolsResponse
}

export async function refreshRuntimeTools(projectId?: string): Promise<RuntimeRefreshResponse> {
  const response = await getPlatformHttpClient('runtime_catalog').post(
    runtimePath('/api/runtime/tools/refresh', '/_management/catalog/tools/refresh'),
    {},
    {
      headers: buildRuntimeHeaders(projectId)
    }
  )
  return response.data as RuntimeRefreshResponse
}

export async function submitRuntimeRefreshOperation(
  resource: 'models' | 'tools' | 'graphs',
  projectId?: string
): Promise<ManagementOperation> {
  return submitOperation({
    kind: runtimeOperationKind(resource),
    project_id: projectId?.trim() || undefined,
    idempotency_key: `${runtimeOperationKind(resource)}:${projectId?.trim() || 'platform'}:${Date.now()}`,
    input_payload: {
      resource
    },
    metadata: {
      resource,
      source: 'platform-web-vue'
    }
  })
}

export async function waitForRuntimeRefreshOperation(
  operationId: string,
  options?: {
    pollMs?: number
    timeoutMs?: number
  }
): Promise<ManagementOperation> {
  return waitForOperationTerminalState(operationId, options)
}
