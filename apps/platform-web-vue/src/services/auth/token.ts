import type { AuthTokenSet } from '@/types/management'

const TOKEN_STORAGE_KEY = 'pw:auth:token-set'
export type AuthTokenScope = 'legacy' | 'v2'

function getStorageKey(scope: AuthTokenScope) {
  return scope === 'legacy' ? TOKEN_STORAGE_KEY : `${TOKEN_STORAGE_KEY}:${scope}`
}

export function getTokenSet(scope: AuthTokenScope = 'legacy'): AuthTokenSet | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(getStorageKey(scope))
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as AuthTokenSet
  } catch {
    return null
  }
}

export function setTokenSet(tokenSet: AuthTokenSet, scope: AuthTokenScope = 'legacy'): void {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(getStorageKey(scope), JSON.stringify(tokenSet))
}

export function clearTokenSet(scope: AuthTokenScope = 'legacy'): void {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(getStorageKey(scope))
}

export function clearAllTokenSets(): void {
  clearTokenSet('legacy')
  clearTokenSet('v2')
}

export function getAccessToken(scope: AuthTokenScope = 'legacy'): string {
  return getTokenSet(scope)?.accessToken?.trim() || ''
}

export function getRefreshToken(scope: AuthTokenScope = 'legacy'): string {
  return getTokenSet(scope)?.refreshToken?.trim() || ''
}
