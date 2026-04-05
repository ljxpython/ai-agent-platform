import { z } from 'zod'

const envSchema = z.object({
  VITE_APP_NAME: z.string().min(1).default('Agent Platform Console'),
  VITE_PLATFORM_API_URL: z.string().url().default('http://localhost:2024'),
  VITE_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(30000),
  VITE_DEV_PORT: z.coerce.number().int().positive().default(3000),
  VITE_DEV_PROXY_TARGET: z.string().url().default('http://localhost:2024'),
  VITE_LANGGRAPH_DEBUG_URL: z.string().optional().default('')
})

const parsed = envSchema.parse(import.meta.env)

export const env = {
  appName: parsed.VITE_APP_NAME,
  platformApiUrl: parsed.VITE_PLATFORM_API_URL.replace(/\/+$/, ''),
  requestTimeoutMs: parsed.VITE_REQUEST_TIMEOUT_MS,
  devPort: parsed.VITE_DEV_PORT,
  devProxyTarget: parsed.VITE_DEV_PROXY_TARGET.replace(/\/+$/, ''),
  langgraphDebugUrl: parsed.VITE_LANGGRAPH_DEBUG_URL.trim()
}
