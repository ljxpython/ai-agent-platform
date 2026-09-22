import type {
  ManagementUser,
  PermissionCode,
  PlatformRole,
  ProjectRole
} from '@/types/management'

const PLATFORM_ROLES: PlatformRole[] = [
  'platform_super_admin',
  'platform_operator',
  'platform_viewer'
]

const PROJECT_ROLES: ProjectRole[] = [
  'project_admin',
  'project_editor',
  'project_executor'
]

export function normalizePlatformRole(value: unknown): PlatformRole | null {
  return typeof value === 'string' && PLATFORM_ROLES.includes(value as PlatformRole)
    ? (value as PlatformRole)
    : null
}

export function normalizeProjectRole(value: unknown): ProjectRole | null {
  if (typeof value !== 'string') {
    return null
  }

  if (PROJECT_ROLES.includes(value as ProjectRole)) {
    return value as ProjectRole
  }

  const legacy = { admin: 'project_admin', editor: 'project_editor', executor: 'project_executor' } as const
  return legacy[value as keyof typeof legacy] ?? null
}

type ManagementUserPayload = Partial<Omit<ManagementUser, 'platform_roles'>> & {
  platform_roles?: unknown
}

export function normalizeManagementUser(payload: ManagementUserPayload): ManagementUser {
  const platformRoles = Array.isArray(payload.platform_roles)
    ? Array.from(
        new Set(
          payload.platform_roles
            .map((item) => normalizePlatformRole(item))
            .filter(Boolean)
        )
      ) as PlatformRole[]
    : []

  const isSuperAdmin = platformRoles.includes('platform_super_admin') || Boolean(payload.is_super_admin)

  return {
    id: String(payload.id || ''),
    username: String(payload.username || ''),
    email: payload.email ?? null,
    status: String(payload.status || 'active'),
    is_super_admin: isSuperAdmin,
    platform_roles: isSuperAdmin && !platformRoles.includes('platform_super_admin')
      ? ['platform_super_admin', ...platformRoles]
      : platformRoles,
    must_change_password: Boolean(payload.must_change_password),
    permissions: Array.isArray(payload.permissions)
      ? payload.permissions.filter(permission => typeof permission === 'string' && permission.startsWith('platform.'))
      : [],
    created_at: payload.created_at ?? null,
    updated_at: payload.updated_at ?? null
  }
}

export function isProjectPermission(permission: PermissionCode): boolean {
  return permission.startsWith('project.')
}

export function hasPlatformRole(user: ManagementUser | null | undefined, role: PlatformRole): boolean {
  if (!user) {
    return false
  }

  if (role === 'platform_super_admin' && user.is_super_admin) {
    return true
  }

  return user.platform_roles.includes(role)
}

export function hasPermission(
  user: ManagementUser | null | undefined,
  permission: PermissionCode
): boolean {
  if (!user || user.status !== 'active' || isProjectPermission(permission)) {
    return false
  }

  return user.permissions?.includes(permission) ?? false
}

export function formatPlatformRoleLabel(role: PlatformRole): string {
  if (role === 'platform_super_admin') {
    return '平台超级管理员'
  }
  if (role === 'platform_operator') {
    return '平台运维'
  }
  return '平台只读'
}

export function primaryPlatformRole(user: ManagementUser | null | undefined): PlatformRole | null {
  if (!user) {
    return null
  }

  if (hasPlatformRole(user, 'platform_super_admin')) {
    return 'platform_super_admin'
  }
  if (hasPlatformRole(user, 'platform_operator')) {
    return 'platform_operator'
  }
  if (hasPlatformRole(user, 'platform_viewer')) {
    return 'platform_viewer'
  }
  return null
}

export function formatProjectRoleLabel(role: ProjectRole | null | undefined): string {
  if (role === 'project_admin') {
    return '项目管理员'
  }
  if (role === 'project_editor') {
    return '项目编辑'
  }
  if (role === 'project_executor') {
    return '项目执行'
  }
  return '成员'
}

export function describePlatformRole(user: ManagementUser | null | undefined): string {
  const role = primaryPlatformRole(user)
  return role ? formatPlatformRoleLabel(role) : '成员'
}

export function defaultWorkspacePath(user: ManagementUser | null | undefined): string {
  return hasPlatformRole(user, 'platform_operator') ? '/workspace/control-plane' : '/workspace/overview'
}

export function describePrimaryRole(
  user: ManagementUser | null | undefined,
  projectRole?: ProjectRole | null
): string {
  if (!user) {
    return '成员'
  }

  const platformRole = describePlatformRole(user)
  if (platformRole !== '成员') {
    return platformRole
  }

  return formatProjectRoleLabel(projectRole)
}

export function isProjectAdminRole(role: ProjectRole | null | undefined): boolean {
  return role === 'project_admin'
}

export function isProjectEditorRole(role: ProjectRole | null | undefined): boolean {
  return role === 'project_editor'
}
