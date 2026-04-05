import { httpClient } from '@/services/http/client'

export async function login(payload: {
  username: string
  password: string
}): Promise<{
  access_token: string
  refresh_token: string
  token_type: string
}> {
  const response = await httpClient.post('/_management/auth/login', payload)
  return response.data
}

export async function changePassword(payload: {
  oldPassword: string
  newPassword: string
}): Promise<{ ok: boolean }> {
  const response = await httpClient.post('/_management/auth/change-password', {
    old_password: payload.oldPassword,
    new_password: payload.newPassword
  })

  return response.data as { ok: boolean }
}
