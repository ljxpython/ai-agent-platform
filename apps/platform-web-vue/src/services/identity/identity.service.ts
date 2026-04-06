import { httpClient, platformV2HttpClient } from '@/services/http/client'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import type { ManagementUser } from '@/types/management'

export type IdentityServiceMode = 'legacy' | 'runtime'

type IdentityServiceOptions = {
  mode?: IdentityServiceMode
}

type RuntimeUserProfile = {
  id: string
  username: string
  email?: string | null
  status: string
  platform_roles?: string[]
}

function useRuntimeIdentityApi(options?: IdentityServiceOptions) {
  return options?.mode === 'runtime' && resolvePlatformClientScope('identity') === 'v2'
}

function normalizeIdentityUserProfile(
  payload: RuntimeUserProfile | ManagementUser
): ManagementUser {
  if ('is_super_admin' in payload) {
    return payload
  }

  return {
    id: payload.id,
    username: payload.username,
    email: payload.email ?? null,
    status: payload.status,
    is_super_admin: Array.isArray(payload.platform_roles)
      ? payload.platform_roles.includes('platform_super_admin')
      : false
  }
}

export async function getCurrentProfile(
  requestOptions?: IdentityServiceOptions
): Promise<ManagementUser> {
  const useRuntimeApi = useRuntimeIdentityApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/identity/me' : '/_management/users/me'
  const response = await client.get(endpoint)
  return normalizeIdentityUserProfile(response.data as RuntimeUserProfile | ManagementUser)
}

export async function updateCurrentProfile(
  payload: {
    username?: string
    email?: string
  },
  requestOptions?: IdentityServiceOptions
): Promise<ManagementUser> {
  const useRuntimeApi = useRuntimeIdentityApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi ? '/api/identity/me' : '/_management/users/me'
  const requestBody = useRuntimeApi
    ? {
        username: payload.username?.trim() || undefined,
        email: payload.email?.trim() || ''
      }
    : payload
  const response = await client.patch(endpoint, requestBody)
  return normalizeIdentityUserProfile(response.data as RuntimeUserProfile | ManagementUser)
}

export async function changeCurrentPassword(
  payload: {
    oldPassword: string
    newPassword: string
  },
  requestOptions?: IdentityServiceOptions
): Promise<{ ok: boolean }> {
  const useRuntimeApi = useRuntimeIdentityApi(requestOptions)
  const client = useRuntimeApi ? platformV2HttpClient : httpClient
  const endpoint = useRuntimeApi
    ? '/api/identity/password/change'
    : '/_management/auth/change-password'
  const requestBody = {
    old_password: payload.oldPassword,
    new_password: payload.newPassword
  }
  const response = await client.post(endpoint, requestBody)
  return response.data as { ok: boolean }
}
