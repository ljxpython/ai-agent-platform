import type { AuthTokenSet } from '@/types/management'

const TOKEN_STORAGE_KEY = 'pw:auth:token-set'

export function getTokenSet(): AuthTokenSet | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as AuthTokenSet
  } catch {
    return null
  }
}

export function setTokenSet(tokenSet: AuthTokenSet): void {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokenSet))
}

export function clearTokenSet(): void {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function getAccessToken(): string {
  return getTokenSet()?.accessToken?.trim() || ''
}

export function getRefreshToken(): string {
  return getTokenSet()?.refreshToken?.trim() || ''
}
