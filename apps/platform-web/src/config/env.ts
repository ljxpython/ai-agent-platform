import { z } from 'zod'

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]'
}

function normalizeApiBaseUrl(value: string | undefined): string {
  const normalized = (value || '/').trim()
  if (!normalized || normalized === '/') {
    return ''
  }

  if (normalized.startsWith('/')) {
    return normalized === '/' ? '' : stripTrailingSlash(normalized)
  }

  return stripTrailingSlash(normalized)
}

type ResolveBrowserApiBaseUrlOptions = {
  preferSameOriginLoopbackProxy?: boolean
}

export function resolveBrowserApiBaseUrl(
  value: string | undefined,
  options: ResolveBrowserApiBaseUrlOptions = {}
): string {
  const normalized = normalizeApiBaseUrl(value)
  if (typeof window === 'undefined') {
    return normalized
  }

  const preferSameOriginLoopbackProxy =
    options.preferSameOriginLoopbackProxy ?? import.meta.env.DEV

  try {
    if (!normalized) {
      return stripTrailingSlash(new URL('/', window.location.origin).toString())
    }

    const configuredUrl = new URL(normalized, window.location.origin)
    if (
      preferSameOriginLoopbackProxy &&
      /^https?:$/.test(configuredUrl.protocol) &&
      isLoopbackHostname(window.location.hostname) &&
      isLoopbackHostname(configuredUrl.hostname) &&
      configuredUrl.origin !== window.location.origin
    ) {
      // Only rewrite loopback API origins during Vite dev, where the proxy is
      // expected to terminate same-origin requests for the browser.
      const sameOriginPath = configuredUrl.pathname === '/' ? '' : stripTrailingSlash(configuredUrl.pathname)
      return `${stripTrailingSlash(window.location.origin)}${sameOriginPath}`
    }

    return stripTrailingSlash(configuredUrl.toString())
  } catch {
    return normalized
  }
}

const envSchema = z.object({
  VITE_APP_NAME: z.string().min(1).default('Agent Platform'),
  VITE_PLATFORM_API_URL: z.string().min(1).default('/'),
  VITE_PLATFORM_API_RUNTIME_ENABLED: z.coerce.boolean().default(true),
  VITE_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(30000),
  VITE_DEV_PORT: z.coerce.number().int().positive().default(3000),
  VITE_DEV_PROXY_TARGET: z.string().url().default('http://localhost:2142'),
  VITE_LANGGRAPH_DEBUG_URL: z.string().optional().default('')
})

const parsed = envSchema.parse(import.meta.env)

export const env = {
  appName: parsed.VITE_APP_NAME,
  platformApiUrl: resolveBrowserApiBaseUrl(parsed.VITE_PLATFORM_API_URL),
  platformApiRuntimeEnabled: parsed.VITE_PLATFORM_API_RUNTIME_ENABLED,
  requestTimeoutMs: parsed.VITE_REQUEST_TIMEOUT_MS,
  devPort: parsed.VITE_DEV_PORT,
  devProxyTarget: stripTrailingSlash(parsed.VITE_DEV_PROXY_TARGET),
  langgraphDebugUrl: parsed.VITE_LANGGRAPH_DEBUG_URL.trim()
}
