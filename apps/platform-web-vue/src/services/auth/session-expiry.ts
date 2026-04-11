import { clearAllTokenSets, hasStoredAuthSession } from '@/services/auth/token'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

export const SESSION_EXPIRED_REASON = 'session_expired'

let redirectingToLogin = false

export function hasStoredSession(): boolean {
  return hasStoredAuthSession()
}

export function resolveSessionRedirectTarget(
  pathname: string,
  search = '',
  hash = ''
): string {
  const normalizedPath = pathname.trim()
  if (normalizedPath.startsWith('/workspace')) {
    return `${normalizedPath}${search}${hash}`
  }

  return '/workspace/overview'
}

export function buildSessionExpiredLoginUrl(
  pathname: string,
  search = '',
  hash = ''
): string {
  const params = new URLSearchParams({
    reason: SESSION_EXPIRED_REASON,
    redirect: resolveSessionRedirectTarget(pathname, search, hash)
  })
  return `/auth/login?${params.toString()}`
}

function clearClientSessionState() {
  clearAllTokenSets()

  try {
    useAuthStore().clearSessionState()
  } catch {
    // ignore store teardown errors during early bootstrap
  }

  try {
    useWorkspaceStore().reset()
  } catch {
    // ignore store teardown errors during early bootstrap
  }
}

export function handleSessionExpired(): void {
  clearClientSessionState()

  if (typeof window === 'undefined' || redirectingToLogin) {
    return
  }

  redirectingToLogin = true
  const nextUrl = buildSessionExpiredLoginUrl(
    window.location.pathname,
    window.location.search,
    window.location.hash
  )

  window.location.replace(nextUrl)
}
