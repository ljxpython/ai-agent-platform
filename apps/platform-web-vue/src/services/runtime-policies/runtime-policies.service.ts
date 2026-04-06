import { platformV2HttpClient } from '@/services/http/client'
import type {
  RuntimeGraphPolicyListResponse,
  RuntimeGraphPolicyValue,
  RuntimeModelPolicyListResponse,
  RuntimeModelPolicyValue,
  RuntimeToolPolicyListResponse,
  RuntimeToolPolicyValue
} from '@/types/management'

function runtimePolicyPath(projectId: string, suffix: string) {
  return `/api/projects/${encodeURIComponent(projectId)}/runtime-policies/${suffix}`
}

export async function listRuntimeGraphPolicies(projectId: string): Promise<RuntimeGraphPolicyListResponse> {
  const response = await platformV2HttpClient.get(runtimePolicyPath(projectId, 'graphs'))
  return response.data as RuntimeGraphPolicyListResponse
}

export async function updateRuntimeGraphPolicy(
  projectId: string,
  catalogId: string,
  payload: {
    is_enabled: boolean
    display_order?: number | null
    note?: string | null
  }
): Promise<RuntimeGraphPolicyValue> {
  const response = await platformV2HttpClient.put(
    runtimePolicyPath(projectId, `graphs/${encodeURIComponent(catalogId)}`),
    payload
  )
  return response.data as RuntimeGraphPolicyValue
}

export async function listRuntimeToolPolicies(projectId: string): Promise<RuntimeToolPolicyListResponse> {
  const response = await platformV2HttpClient.get(runtimePolicyPath(projectId, 'tools'))
  return response.data as RuntimeToolPolicyListResponse
}

export async function updateRuntimeToolPolicy(
  projectId: string,
  catalogId: string,
  payload: {
    is_enabled: boolean
    display_order?: number | null
    note?: string | null
  }
): Promise<RuntimeToolPolicyValue> {
  const response = await platformV2HttpClient.put(
    runtimePolicyPath(projectId, `tools/${encodeURIComponent(catalogId)}`),
    payload
  )
  return response.data as RuntimeToolPolicyValue
}

export async function listRuntimeModelPolicies(projectId: string): Promise<RuntimeModelPolicyListResponse> {
  const response = await platformV2HttpClient.get(runtimePolicyPath(projectId, 'models'))
  return response.data as RuntimeModelPolicyListResponse
}

export async function updateRuntimeModelPolicy(
  projectId: string,
  catalogId: string,
  payload: {
    is_enabled: boolean
    is_default_for_project: boolean
    temperature_default?: number | null
    note?: string | null
  }
): Promise<RuntimeModelPolicyValue> {
  const response = await platformV2HttpClient.put(
    runtimePolicyPath(projectId, `models/${encodeURIComponent(catalogId)}`),
    payload
  )
  return response.data as RuntimeModelPolicyValue
}
