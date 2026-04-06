import axios from 'axios'
import { env } from '@/config/env'
import { httpClient } from '@/services/http/client'
import type { AuthTokenSet } from '@/types/management'

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

export async function bootstrapPlatformV2Session(payload: {
  username: string
  password: string
}): Promise<AuthTokenSet | null> {
  try {
    const response = await axios.post<{
      tokens?: {
        access_token?: string
        refresh_token?: string
        token_type?: string
      }
    }>(
      `${env.platformApiV2Url}/api/identity/session`,
      payload,
      {
        timeout: env.requestTimeoutMs,
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )

    const tokens = response.data.tokens
    if (!tokens?.access_token || !tokens.refresh_token) {
      return null
    }

    return {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      tokenType: tokens.token_type || 'bearer'
    }
  } catch {
    return null
  }
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
