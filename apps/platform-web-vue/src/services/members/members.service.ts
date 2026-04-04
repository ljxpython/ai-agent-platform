import { httpClient } from '@/services/http/client'
import type { ManagementProjectMember } from '@/types/management'

type MemberListResponse = {
  items: ManagementProjectMember[]
}

export async function listProjectMembers(
  projectId: string,
  options?: { query?: string }
): Promise<ManagementProjectMember[]> {
  if (!projectId) {
    return []
  }

  const response = await httpClient.get(`/_management/projects/${projectId}/members`, {
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
}): Promise<ManagementProjectMember> {
  const response = await httpClient.post(
    `/_management/projects/${payload.projectId}/members`,
    {
      user_id: payload.userId,
      role: payload.role
    }
  )

  return response.data as ManagementProjectMember
}

export async function deleteProjectMember(
  projectId: string,
  userId: string
): Promise<{ ok: boolean }> {
  const response = await httpClient.delete(
    `/_management/projects/${projectId}/members/${userId}`
  )

  return response.data as { ok: boolean }
}
