import { httpClient } from '@/services/http/client'
import type { ManagementUser, ManagementUserListResponse } from '@/types/management'

export async function getMe(): Promise<ManagementUser> {
  const response = await httpClient.get('/_management/users/me')
  return response.data as ManagementUser
}

export async function updateMe(payload: {
  username?: string
  email?: string
}): Promise<ManagementUser> {
  const response = await httpClient.patch('/_management/users/me', payload)
  return response.data as ManagementUser
}

export async function listUsersPage(options?: {
  limit?: number
  offset?: number
  query?: string
  status?: string
}): Promise<ManagementUserListResponse> {
  const response = await httpClient.get('/_management/users', {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      status: options?.status?.trim() || undefined
    }
  })

  return response.data as ManagementUserListResponse
}
