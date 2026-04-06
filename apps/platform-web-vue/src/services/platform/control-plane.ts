import { env } from '@/config/env'
import { getAccessToken } from '@/services/auth/token'
import {
  httpClient,
  legacyBaseUrl,
  platformV2BaseUrl,
  platformV2HttpClient
} from '@/services/http/client'

export type PlatformClientModule =
  | 'system'
  | 'identity'
  | 'projects'
  | 'members'
  | 'users'
  | 'announcements'
  | 'audit'
  | 'operations'
  | 'assistants'
  | 'testcase'
  | 'runtime_catalog'
  | 'runtime_gateway'

export type PlatformClientScope = 'legacy' | 'v2'

function wantsV2(module: PlatformClientModule) {
  return (
    env.platformApiV2RuntimeEnabled &&
    (module === 'system' ||
      module === 'identity' ||
      module === 'users' ||
      module === 'testcase' ||
      module === 'runtime_gateway' ||
      module === 'runtime_catalog' ||
      module === 'projects' ||
      module === 'operations' ||
      module === 'assistants' ||
      module === 'announcements' ||
      module === 'audit')
  )
}

export function resolvePlatformClientScope(module: PlatformClientModule): PlatformClientScope {
  if (wantsV2(module) && getAccessToken('v2')) {
    return 'v2'
  }
  return 'legacy'
}

export function getPlatformHttpClient(module: PlatformClientModule) {
  return resolvePlatformClientScope(module) === 'v2' ? platformV2HttpClient : httpClient
}

export function getPlatformApiBaseUrl(module: PlatformClientModule): string {
  return resolvePlatformClientScope(module) === 'v2' ? platformV2BaseUrl : legacyBaseUrl
}

export function getPlatformAccessToken(module: PlatformClientModule): string {
  const scope = resolvePlatformClientScope(module)
  return getAccessToken(scope)
}
