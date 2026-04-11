import type { AuthTokenSet } from '@/types/management'

const TOKEN_STORAGE_KEY = 'pw:auth:token-set'

function parseTokenSet(raw: string): AuthTokenSet | null {
  try {
    return JSON.parse(raw) as AuthTokenSet
  } catch {
    return null
  }
}

function clearStoredTokenSet() {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function getTokenSet(): AuthTokenSet | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!raw) {
    return null
  }

  return parseTokenSet(raw)
}

export function setTokenSet(tokenSet: AuthTokenSet): void {
  if (typeof window === 'undefined') {
    return
  }

  clearStoredTokenSet()
  window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokenSet))
}

export function clearTokenSet(): void {
  clearStoredTokenSet()
}

export function clearAllTokenSets(): void {
  clearStoredTokenSet()
}

export function getAccessToken(): string {
  return getTokenSet()?.accessToken?.trim() || ''
}

export function getRefreshToken(): string {
  return getTokenSet()?.refreshToken?.trim() || ''
}

export function hasStoredAuthSession(): boolean {
  return Boolean(getAccessToken() || getRefreshToken())
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const normalizedToken = token.trim()
  if (!normalizedToken) {
    return null
  }

  const segments = normalizedToken.split('.')
  if (segments.length < 2) {
    return null
  }

  const payloadSegment = segments[1]?.replace(/-/g, '+').replace(/_/g, '/') || ''
  if (!payloadSegment) {
    return null
  }

  const paddedPayload = payloadSegment.padEnd(Math.ceil(payloadSegment.length / 4) * 4, '=')

  try {
    if (typeof atob !== 'function') {
      return null
    }
    return JSON.parse(atob(paddedPayload)) as Record<string, unknown>
  } catch {
    return null
  }
}

export function getAccessTokenExpiresAt(token = getAccessToken()): number | null {
  const payload = decodeJwtPayload(token)
  const exp = payload?.exp
  return typeof exp === 'number' && Number.isFinite(exp) ? exp : null
}

export function isAccessTokenExpiringSoon(token = getAccessToken(), skewSeconds = 30): boolean {
  const normalizedToken = token.trim()
  if (!normalizedToken) {
    return true
  }

  const expiresAt = getAccessTokenExpiresAt(normalizedToken)
  if (expiresAt === null) {
    return false
  }

  return Math.floor(Date.now() / 1000) >= expiresAt - Math.max(0, skewSeconds)
}
