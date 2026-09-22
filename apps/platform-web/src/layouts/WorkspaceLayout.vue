<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import TopContextBar from '@/components/layout/TopContextBar.vue'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'
import { useAuthorization } from '@/composables/useAuthorization'
import StateBanner from '@/components/platform/StateBanner.vue'

const route = useRoute()
const uiStore = useUiStore()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const { can } = useAuthorization()
const routeAccessAllowed = computed(() => {
  const permissions = route.meta.requiredPermissions ?? []
  const projectId = typeof route.params.projectId === 'string' ? route.params.projectId : undefined
  const allowed = (permission: typeof permissions[number]) => can(permission, projectId)
  return route.meta.permissionMode === 'any' ? permissions.some(allowed) : permissions.every(allowed)
})
let accessRefreshTimer: number | undefined
let refreshingAccess = false

async function refreshAccess() {
  if (document.visibilityState !== 'visible' || refreshingAccess) return
  refreshingAccess = true
  try {
    await Promise.allSettled([
      authStore.fetchCurrentUser(),
      workspaceStore.refreshCurrentProjectAccess()
    ])
  } finally {
    refreshingAccess = false
  }
}

onMounted(() => {
  accessRefreshTimer = window.setInterval(() => { void refreshAccess() }, 60_000)
  document.addEventListener('visibilitychange', refreshAccess)
  window.addEventListener('focus', refreshAccess)
  window.addEventListener('platform-access-denied', refreshAccess)
})
onUnmounted(() => {
  window.clearInterval(accessRefreshTimer)
  document.removeEventListener('visibilitychange', refreshAccess)
  window.removeEventListener('focus', refreshAccess)
  window.removeEventListener('platform-access-denied', refreshAccess)
})
const { sidebarCollapsed } = storeToRefs(uiStore)

const isImmersive = computed(() => route.name === 'workspace-chat' || Boolean(route.meta?.immersive))
</script>

<template>
  <div class="flex h-screen h-[100dvh] overflow-hidden bg-gray-50 text-gray-900 dark:bg-dark-950 dark:text-white">
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient" />

    <AppSidebar />

    <div
      class="relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-64'"
    >
      <TopContextBar
        v-if="!isImmersive"
        class="shrink-0"
      />
      <main
        class="flex min-h-0 flex-1 flex-col overflow-hidden"
        :class="isImmersive ? 'p-0 m-0' : 'pw-workspace-main'"
      >
        <div
          class="flex min-h-0 w-full flex-1 flex-col"
          :class="isImmersive ? 'overflow-hidden' : 'overflow-y-auto'"
        >
          <router-view v-if="routeAccessAllowed" :key="authStore.sessionEpoch" />
          <section v-else class="p-6 space-y-4">
            <StateBanner title="当前页面权限已失效" description="请切换到有权限的项目，或联系项目管理员申请访问。正在进行的任务不会因页面关闭而自动停止。" variant="warning" />
            <RouterLink class="pw-btn pw-btn-secondary" to="/workspace/overview">返回总览 / 切换项目</RouterLink>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>
