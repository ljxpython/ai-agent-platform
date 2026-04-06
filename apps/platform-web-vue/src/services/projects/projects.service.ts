import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type { ManagementProject, ManagementProjectListResponse } from '@/types/management'

export type ProjectServiceMode = 'legacy' | 'runtime'

type ProjectServiceOptions = {
  mode?: ProjectServiceMode
}

function useRuntimeProjectsApi(options?: ProjectServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('projects') === 'v2'
}

export async function listProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}, requestOptions?: ProjectServiceOptions): Promise<ManagementProjectListResponse> {
  const useRuntimeApi = useRuntimeProjectsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/projects' : '/_management/projects'
  const response = await client.get(endpoint, {
    params: {
      limit: options?.limit ?? 100,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined
    }
  })

  return response.data as ManagementProjectListResponse
}

export async function listProjects(
  requestOptions?: ProjectServiceOptions
): Promise<ManagementProject[]> {
  const payload = await listProjectsPage(undefined, requestOptions)
  return payload.items
}

export async function listRuntimeProjectsPage(options?: {
  limit?: number
  offset?: number
  query?: string
}): Promise<ManagementProjectListResponse> {
  return listProjectsPage(options, { mode: 'runtime' })
}

export async function listRuntimeProjects(): Promise<ManagementProject[]> {
  return listProjects({ mode: 'runtime' })
}

export async function createProject(payload: {
  name: string
  description?: string
}, requestOptions?: ProjectServiceOptions): Promise<ManagementProject> {
  const useRuntimeApi = useRuntimeProjectsApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/projects' : '/_management/projects'
  const response = await client.post(endpoint, payload)
  return response.data as ManagementProject
}

export async function createRuntimeProject(payload: {
  name: string
  description?: string
}): Promise<ManagementProject> {
  return createProject(payload, { mode: 'runtime' })
}
