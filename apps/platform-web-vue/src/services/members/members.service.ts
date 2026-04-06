import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type { ManagementProjectMember } from '@/types/management'

type MemberListResponse = {
  items: ManagementProjectMember[]
}

export type MemberServiceMode = 'legacy' | 'runtime'

type MemberServiceOptions = {
  mode?: MemberServiceMode
}

function useRuntimeProjectMembersApi(options?: MemberServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('projects') === 'v2'
}

export async function listProjectMembers(
  projectId: string,
  options?: { query?: string },
  requestOptions?: MemberServiceOptions
): Promise<ManagementProjectMember[]> {
  if (!projectId) {
    return []
  }

  const useRuntimeApi = useRuntimeProjectMembersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/projects/${projectId}/members`
    : `/_management/projects/${projectId}/members`
  const response = await client.get(endpoint, {
    params: {
      query: options?.query?.trim() || undefined
    }
  })

  const payload = response.data as MemberListResponse
  return Array.isArray(payload.items) ? payload.items : []
}

export async function upsertProjectMember(payload: {
  projectId: string
  userId: string
  role: 'admin' | 'editor' | 'executor'
}, requestOptions?: MemberServiceOptions): Promise<ManagementProjectMember> {
  const useRuntimeApi = useRuntimeProjectMembersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const response = useRuntimeApi
    ? await client.put(`/api/projects/${payload.projectId}/members/${payload.userId}`, {
        role: payload.role
      })
    : await client.post(`/_management/projects/${payload.projectId}/members`, {
        user_id: payload.userId,
        role: payload.role
      })

  return response.data as ManagementProjectMember
}

export async function deleteProjectMember(
  projectId: string,
  userId: string,
  requestOptions?: MemberServiceOptions
): Promise<{ ok: boolean }> {
  const useRuntimeApi = useRuntimeProjectMembersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? `/api/projects/${projectId}/members/${userId}`
    : `/_management/projects/${projectId}/members/${userId}`
  const response = await client.delete(endpoint)

  return response.data as { ok: boolean }
}
