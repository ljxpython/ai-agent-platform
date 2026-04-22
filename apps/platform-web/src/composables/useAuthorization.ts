import { computed } from 'vue'
import {
  describePrimaryRole,
  describePlatformRole,
  hasAnyProjectPermission,
  hasPermission,
  projectRoleFor
} from '@/services/auth/permissions'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import type { PermissionCode } from '@/types/management'

export function useAuthorization() {
  const authStore = useAuthStore()
  const { activeProjectId } = useWorkspaceProjectContext()

  const currentProjectRole = computed(() => projectRoleFor(authStore.user, activeProjectId.value))
  const platformRoleLabel = computed(() => describePlatformRole(authStore.user))
  const roleLabel = computed(() => describePrimaryRole(authStore.user, activeProjectId.value))

  function can(permission: PermissionCode, projectId?: string | null) {
    return hasPermission(authStore.user, permission, projectId)
  }

  function canAnyProject(permission: PermissionCode) {
    return hasAnyProjectPermission(authStore.user, permission)
  }

  function currentProjectCan(permission: PermissionCode) {
    return hasPermission(authStore.user, permission, activeProjectId.value)
  }

  return {
    currentProjectId: activeProjectId,
    currentProjectRole,
    platformRoleLabel,
    roleLabel,
    can,
    canAnyProject,
    currentProjectCan
  }
}
