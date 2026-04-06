import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type {
  ManagementUser,
  ManagementUserListResponse,
  ManagementUserProject
} from '@/types/management'

export type UserServiceMode = 'legacy' | 'runtime'

type UserServiceOptions = {
  mode?: UserServiceMode
}

function useRuntimeUsersApi(options?: UserServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('users') === 'v2'
}

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
}, requestOptions?: UserServiceOptions): Promise<ManagementUserListResponse> {
  const useRuntimeApi = useRuntimeUsersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/users' : '/_management/users'
  const response = await client.get(endpoint, {
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
}, requestOptions?: UserServiceOptions): Promise<ManagementUser> {
  const useRuntimeApi = useRuntimeUsersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/users' : '/_management/users'
  const response = await client.post(endpoint, payload)
  return response.data as ManagementUser
}

export async function getUser(
  userId: string,
  requestOptions?: UserServiceOptions
): Promise<ManagementUser> {
  const useRuntimeApi = useRuntimeUsersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? `/api/users/${userId}` : `/_management/users/${userId}`
  const response = await client.get(endpoint)
  return response.data as ManagementUser
}

export async function listUserProjects(
  userId: string,
  requestOptions?: UserServiceOptions
): Promise<{
  items: ManagementUserProject[]
  total: number
}> {
  const useRuntimeApi = useRuntimeUsersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? `/api/users/${userId}/projects` : `/_management/users/${userId}/projects`
  const response = await client.get(endpoint)
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
  },
  requestOptions?: UserServiceOptions
): Promise<ManagementUser> {
  const useRuntimeApi = useRuntimeUsersApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? `/api/users/${userId}` : `/_management/users/${userId}`
  const response = await client.patch(endpoint, payload)
  return response.data as ManagementUser
}
