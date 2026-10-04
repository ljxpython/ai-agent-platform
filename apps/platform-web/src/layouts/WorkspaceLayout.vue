<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import TopContextBar from "@/components/layout/TopContextBar.vue";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import { useAuthorization } from "@/composables/useAuthorization";
import StateBanner from "@/components/platform/StateBanner.vue";
import ChatSessionPool from "@/modules/chat/components/ChatSessionPool.vue";
import {
  createChatSessionPool,
  provideChatSessionPool,
} from "@/modules/chat/composables/useChatSessionPool";
import { useChatSessionStore } from "@/modules/chat/stores/useChatSessionStore";

const route = useRoute();
const uiStore = useUiStore();
const authStore = useAuthStore();
const workspaceStore = useWorkspaceStore();
const chatSessionPool = createChatSessionPool();
const chatSessionStore = useChatSessionStore();
provideChatSessionPool(chatSessionPool);
watch(
  () =>
    `${authStore.user?.id ?? ""}:${authStore.sessionEpoch}:${String(route.params.projectId ?? "")}`,
  (next, previous) => {
    if (previous && next !== previous) {
      chatSessionPool.clearScope();
      chatSessionStore.clearAll();
    }
  },
);
const { can } = useAuthorization();

watch(
  () => route.params.projectId,
  (projectId) => {
    if (
      typeof workspaceStore.setProjectId === "function" &&
      typeof projectId === "string" &&
      projectId &&
      projectId !== workspaceStore.currentProjectId
    ) {
      void workspaceStore.setProjectId(projectId);
    }
  },
  { immediate: true },
);

let accessRefreshTimer: number | undefined;
const refreshingAccess = ref(false);

const routeAccessAllowed = computed(() => {
  const permissions = route.meta.requiredPermissions ?? [];
  if (permissions.length === 0) return true;
  if (!authStore.isAuthenticated) return false;

  const projectId =
    typeof route.params.projectId === "string"
      ? route.params.projectId
      : undefined;

  // Stale-While-Revalidate 原则：当处于加载/刷新中，若本地已有该项目的访问权限，坚决保持现有权限，绝不误杀视图
  if (
    projectId &&
    (workspaceStore.accessLoading || refreshingAccess.value) &&
    workspaceStore.currentProjectAccess?.project_id === projectId
  ) {
    return true;
  }

  const allowed = (permission: (typeof permissions)[number]) =>
    can(permission, projectId);
  const result =
    route.meta.permissionMode === "any"
      ? permissions.some(allowed)
      : permissions.every(allowed);

  // 避免后台短暂抖动误判：如果当前项目已有授权记录且并未收到明确 403 移除通知，继续允许访问
  if (
    !result &&
    projectId &&
    workspaceStore.currentProjectAccess?.project_id === projectId
  ) {
    if (workspaceStore.currentProjectAccess.roles.length > 0) {
      return true;
    }
  }

  return result;
});

watch(routeAccessAllowed, (allowed) => {
  if (!allowed) {
    chatSessionPool.clearScope();
    chatSessionStore.clearAll();
  }
});

async function refreshAccess() {
  if (document.visibilityState !== "visible" || refreshingAccess.value) return;
  refreshingAccess.value = true;
  try {
    await Promise.allSettled([
      authStore.fetchCurrentUser(),
      workspaceStore.refreshCurrentProjectAccess(),
    ]);
  } finally {
    refreshingAccess.value = false;
  }
}

onMounted(() => {
  accessRefreshTimer = window.setInterval(() => {
    void refreshAccess();
  }, 60_000);
  document.addEventListener("visibilitychange", refreshAccess);
  window.addEventListener("focus", refreshAccess);
  window.addEventListener("platform-access-denied", refreshAccess);
});
onUnmounted(() => {
  chatSessionPool.clearScope();
  chatSessionStore.clearAll();
  window.clearInterval(accessRefreshTimer);
  document.removeEventListener("visibilitychange", refreshAccess);
  window.removeEventListener("focus", refreshAccess);
  window.removeEventListener("platform-access-denied", refreshAccess);
});
const { sidebarCollapsed } = storeToRefs(uiStore);

const isImmersive = computed(
  () => route.name === "workspace-chat" || Boolean(route.meta?.immersive),
);
</script>

<template>
  <div
    class="flex h-screen h-[100dvh] overflow-hidden bg-gray-50 text-gray-900 dark:bg-dark-950 dark:text-white"
  >
    <div class="pointer-events-none fixed inset-0 bg-mesh-gradient" />

    <AppSidebar />

    <div
      class="relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden transition-all duration-300"
      :class="sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-64'"
    >
      <TopContextBar v-if="!isImmersive" class="shrink-0" />
      <main
        class="flex min-h-0 flex-1 flex-col overflow-hidden"
        :class="isImmersive ? 'p-0 m-0' : 'pw-workspace-main'"
      >
        <ChatSessionPool :pool="chatSessionPool" />
        <div
          class="flex min-h-0 w-full flex-1 flex-col"
          :class="isImmersive ? 'overflow-hidden' : 'overflow-y-auto'"
        >
          <router-view v-if="routeAccessAllowed" v-slot="{ Component }">
            <keep-alive :include="['ChatPage', 'DearAgentPage']">
              <component
                :is="Component"
                :key="
                  route.name === 'workspace-chat' ||
                  route.name === 'workspace-dear-agent'
                    ? `${String(route.name)}:${authStore.sessionEpoch}:${String(route.params.projectId ?? '')}`
                    : `${String(route.name ?? route.path)}:${authStore.sessionEpoch}:${route.fullPath}`
                "
              />
            </keep-alive>
          </router-view>
          <section v-else class="p-6 space-y-4">
            <StateBanner
              title="当前页面权限已失效"
              description="请切换到有权限的项目，或联系项目管理员申请访问。正在进行的任务不会因页面关闭而自动停止。"
              variant="warning"
            />
            <RouterLink
              class="pw-btn pw-btn-secondary"
              to="/workspace/overview"
            >
              返回总览 / 切换项目
            </RouterLink>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>
