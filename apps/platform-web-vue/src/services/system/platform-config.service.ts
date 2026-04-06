import { getPlatformHttpClient } from '@/services/platform/control-plane'
import type { PlatformConfigSnapshot } from '@/types/management'

export async function getPlatformConfigSnapshot(): Promise<PlatformConfigSnapshot> {
  const client = getPlatformHttpClient('system')
  const response = await client.get('/_system/platform-config')
  return response.data as PlatformConfigSnapshot
}

export async function updatePlatformFeatureFlags(featureFlags: Record<string, boolean>): Promise<PlatformConfigSnapshot> {
  const client = getPlatformHttpClient('system')
  const response = await client.patch('/_system/platform-config/feature-flags', {
    feature_flags: featureFlags
  })
  return response.data as PlatformConfigSnapshot
}
