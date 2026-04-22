import { env } from '@/config/env'

const normalizedVersion = __APP_VERSION__.trim().replace(/^v/i, '') || '0.0.0'

export const appMeta = {
  name: env.appName,
  version: normalizedVersion,
  versionLabel: `v${normalizedVersion}`
}
