import 'vue-router'
import type { PermissionCode } from '@/types/management'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    eyebrow?: string
    requiredPermissions?: PermissionCode[]
    permissionMode?: 'all' | 'any'
    permissionProjectSource?: 'workspace' | 'route'
    allowWithoutProject?: boolean
  }
}
