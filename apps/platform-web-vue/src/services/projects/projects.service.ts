import { httpClient } from '@/services/http/client'
import type { ManagementProject, ManagementProjectListResponse } from '@/types/management'

export async function listProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  const response = await httpClient.get('/_management/projects', {
    params: {
      limit: options?.limit ?? 100,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined
    }
  })

  return response.data as ManagementProjectListResponse
}

export async function listProjects(): Promise<ManagementProject[]> {
  const payload = await listProjectsPage()
  return payload.items
}

export async function createProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  const response = await httpClient.post('/_management/projects', payload)
  return response.data as ManagementProject
}
