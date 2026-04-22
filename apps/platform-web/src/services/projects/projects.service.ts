import { platformHttpClient } from '@/services/http/client'
import type { ManagementProject, ManagementProjectListResponse } from '@/types/management'

export async function listProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  const response = await platformHttpClient.get('/api/projects', {
    params: {
      limit: options?.limit ?? 100,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined
    }
  })

  return response.data as ManagementProjectListResponse
}

export async function listProjects(
): Promise<ManagementProject[]> {
  const payload = await listProjectsPage()
  return payload.items
}

export async function listRuntimeProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  return listProjectsPage(options)
}

export async function listRuntimeProjects(): Promise<ManagementProject[]> {
  return listProjects()
}

export async function createProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  const response = await platformHttpClient.post('/api/projects', payload)
  return response.data as ManagementProject
}

export async function createRuntimeProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  return createProject(payload)
}

export async function deleteProject(
  projectId: string
): Promise<{ ok: boolean }> {
  const response = await platformHttpClient.delete(`/api/projects/${projectId}`)
  return response.data as { ok: boolean }
}
