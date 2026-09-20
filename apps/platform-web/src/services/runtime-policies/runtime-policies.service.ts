import { platformHttpClient } from '@/services/http/client'
import type {
  CreateToolRestrictionPayload,
  RuntimeGraphPolicyListResponse,
  RuntimeGraphPolicyValue,
  RuntimeModelPolicyListResponse,
  RuntimeModelPolicyValue,
  ToolRestrictionItem,
  ToolRestrictionListResponse
} from '@/types/management'

function runtimePolicyPath(projectId: string, suffix: string) {
  return `/api/projects/${encodeURIComponent(projectId)}/runtime-policies/${suffix}`
}

export async function listRuntimeGraphPolicies(projectId: string): Promise<RuntimeGraphPolicyListResponse> {
  const response = await platformHttpClient.get(runtimePolicyPath(projectId, 'graphs'))
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
  const response = await platformHttpClient.put(
    runtimePolicyPath(projectId, `graphs/${encodeURIComponent(catalogId)}`),
    payload
  )
  return response.data as RuntimeGraphPolicyValue
}

export async function listToolRestrictions(projectId: string): Promise<ToolRestrictionListResponse> {
  const response = await platformHttpClient.get(runtimePolicyPath(projectId, 'tool-restrictions'))
  return response.data as ToolRestrictionListResponse
}

export async function createToolRestriction(
  projectId: string,
  payload: CreateToolRestrictionPayload
): Promise<ToolRestrictionItem> {
  const response = await platformHttpClient.post(runtimePolicyPath(projectId, 'tool-restrictions'), payload)
  return response.data as ToolRestrictionItem
}

export async function deleteToolRestriction(
  projectId: string,
  restrictionId: string
): Promise<void> {
  await platformHttpClient.delete(runtimePolicyPath(projectId, `tool-restrictions/${encodeURIComponent(restrictionId)}`))
}

export async function listRuntimeModelPolicies(projectId: string): Promise<RuntimeModelPolicyListResponse> {
  const response = await platformHttpClient.get(runtimePolicyPath(projectId, 'models'))
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
  const response = await platformHttpClient.put(
    runtimePolicyPath(projectId, `models/${encodeURIComponent(catalogId)}`),
    payload
  )
  return response.data as RuntimeModelPolicyValue
}
