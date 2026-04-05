/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_NAME: string
  readonly VITE_PLATFORM_API_URL: string
  readonly VITE_REQUEST_TIMEOUT_MS: string
  readonly VITE_DEV_PORT: string
  readonly VITE_DEV_PROXY_TARGET: string
  readonly VITE_LANGGRAPH_DEBUG_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, any>
  export default component
}
