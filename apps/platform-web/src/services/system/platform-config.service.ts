import { platformHttpClient } from '@/services/http/client'
import type { PlatformConfigSnapshot } from '@/types/management'

export async function getPlatformConfigSnapshot(): Promise<PlatformConfigSnapshot> {
  const response = await platformHttpClient.get('/_system/platform-config')
  return response.data as PlatformConfigSnapshot
}

export async function updatePlatformFeatureFlags(featureFlags: Record<string, boolean>): Promise<PlatformConfigSnapshot> {
  const response = await platformHttpClient.patch('/_system/platform-config/feature-flags', {
    feature_flags: featureFlags
  })
  return response.data as PlatformConfigSnapshot
}
