import type { Router } from 'vue-router'
import { getAccessToken } from '@/services/auth/token'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import { getWorkspaceProjectContextModule } from '@/services/platform/workspace-context'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

export function registerRouterGuards(router: Router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore()
    const workspaceStore = useWorkspaceStore()

    await authStore.hydrate()
    if (getAccessToken() && !authStore.user) {
      await authStore.fetchCurrentUser()
    }

    const isAuthenticated = Boolean(getAccessToken()) && Boolean(authStore.user)

    if (to.path.startsWith('/workspace') && !isAuthenticated) {
      return {
        path: '/auth/login',
        query: { redirect: to.fullPath }
      }
    }

    if (to.path.startsWith('/auth') && isAuthenticated) {
      if (typeof to.query.redirect === 'string' && to.query.redirect.startsWith('/workspace')) {
        return to.query.redirect
      }

      return '/workspace/overview'
    }

    if (to.path.startsWith('/workspace') && isAuthenticated && !workspaceStore.projects.length) {
      await workspaceStore.hydrateContext()
    }

    const contextModule = getWorkspaceProjectContextModule(to.path)
    if (
      to.path.startsWith('/workspace') &&
      isAuthenticated &&
      contextModule &&
      resolvePlatformClientScope(contextModule) === 'v2' &&
      !workspaceStore.runtimeProjects.length
    ) {
      await workspaceStore.hydrateRuntimeContext()
    }

    return true
  })
}
