import { httpClient } from '@/services/http/client'
import type {
  ManagementUser,
  ManagementUserListResponse,
  ManagementUserProject
} from '@/types/management'

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
  excludeUserIds?: string[]
}): Promise<ManagementUserListResponse> {
  const response = await httpClient.get('/_management/users', {
    params: {
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0,
      query: options?.query?.trim() || undefined,
      status: options?.status?.trim() || undefined,
      exclude_user_ids:
        Array.isArray(options?.excludeUserIds) && options.excludeUserIds.length > 0
          ? options.excludeUserIds.map((item) => item.trim()).filter(Boolean).join(',')
          : undefined
    }
  })

  return response.data as ManagementUserListResponse
}

export async function createUser(payload: {
  username: string
  password: string
  is_super_admin?: boolean
}): Promise<ManagementUser> {
  const response = await httpClient.post('/_management/users', payload)
  return response.data as ManagementUser
}

export async function getUser(userId: string): Promise<ManagementUser> {
  const response = await httpClient.get(`/_management/users/${userId}`)
  return response.data as ManagementUser
}

export async function listUserProjects(userId: string): Promise<{
  items: ManagementUserProject[]
  total: number
}> {
  const response = await httpClient.get(`/_management/users/${userId}/projects`)
  const payload = response.data as {
    items?: ManagementUserProject[]
    total?: number
  }

  return {
    items: Array.isArray(payload.items) ? payload.items : [],
    total: typeof payload.total === 'number' ? payload.total : Array.isArray(payload.items) ? payload.items.length : 0
  }
}

export async function updateUser(
  userId: string,
  payload: {
    username?: string
    password?: string
    status?: 'active' | 'disabled'
    is_super_admin?: boolean
  }
): Promise<ManagementUser> {
  const response = await httpClient.patch(`/_management/users/${userId}`, payload)
  return response.data as ManagementUser
}
