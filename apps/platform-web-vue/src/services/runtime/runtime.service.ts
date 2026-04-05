import { httpClient } from '@/services/http/client'
import type {
  RuntimeModelsResponse,
  RuntimeRefreshResponse,
  RuntimeToolsResponse
} from '@/types/management'

export async function listRuntimeModels(): Promise<RuntimeModelsResponse> {
  const response = await httpClient.get('/_management/runtime/models')
  return response.data as RuntimeModelsResponse
}

export async function refreshRuntimeModels(): Promise<RuntimeRefreshResponse> {
  const response = await httpClient.post('/_management/catalog/models/refresh', {})
  return response.data as RuntimeRefreshResponse
}

export async function listRuntimeTools(): Promise<RuntimeToolsResponse> {
  const response = await httpClient.get('/_management/runtime/tools')
  return response.data as RuntimeToolsResponse
}

export async function refreshRuntimeTools(): Promise<RuntimeRefreshResponse> {
  const response = await httpClient.post('/_management/catalog/tools/refresh', {})
  return response.data as RuntimeRefreshResponse
}
