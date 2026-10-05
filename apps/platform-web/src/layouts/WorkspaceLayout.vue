<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import AppSidebar from "@/components/layout/AppSidebar.vue";
import TopContextBar from "@/components/layout/TopContextBar.vue";
import { useUiStore } from "@/stores/ui";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";
import { resolveRouteAccess } from "@/services/auth/route-access";
import { accessDeniedDetail } from "@/services/auth/access-events";
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

watch(
  () => route.params.projectId,
  (projectId) => {
    if (
      typeof workspaceStore.setProjectId === "function" &&
      typeof projectId === "string" &&
      projectId &&
      projectId !== workspaceStore.currentProjectId
    ) {
      void workspaceStore.setProjectId(projectId).catch(() => {
        /* Store 提供可重试状态。 */
      });
    }
  },
  { immediate: true },
);

let accessRefreshTimer: number | undefined;
const refreshingAccess = ref(false);

const routeAccess = computed(() =>
  resolveRouteAccess(route, authStore.user, workspaceStore),
);
const routeAccessAllowed = computed(() => routeAccess.value === "allowed");
const accessTitle = computed(
  () =>
    ({
      allowed: "",
      loading: "正在确认访问权限",
      unavailable: "暂时无法确认访问权限",
      denied: "当前页面权限已失效",
    })[routeAccess.value],
);

watch(
  () => workspaceStore.accessStatus,
  (status) => {
    if (status === "denied") {
      chatSessionPool.clearScope();
      chatSessionStore.clearAll();
    }
  },
);

watch(routeAccessAllowed, (allowed) => {
  if (!allowed && !authStore.isAuthenticated) {
    chatSessionPool.clearScope();
    chatSessionStore.clearAll();
  }
});

let lastRefresh = 0;
let pendingRefresh: ReturnType<typeof setTimeout> | undefined;
async function refreshAccess(force = false) {
  if (document.visibilityState !== "visible" || refreshingAccess.value) return;
  if (!force && lastRefresh && Date.now() - lastRefresh < 10_000) {
    pendingRefresh ??= setTimeout(
      () => {
        pendingRefresh = undefined;
        void refreshAccess();
      },
      10_000 - (Date.now() - lastRefresh),
    );
    return;
  }
  clearTimeout(pendingRefresh);
  pendingRefresh = undefined;
  lastRefresh = Date.now();
  refreshingAccess.value = true;
  try {
    await Promise.allSettled([
      authStore.fetchCurrentUser(),
      workspaceStore.refreshCurrentProjectAccess(),
    ]);
  } catch {
    // 静默吸收后台刷新错误，绝不中断前台交互
  } finally {
    refreshingAccess.value = false;
  }
}

function handleVisibilityChange() {
  void refreshAccess();
}

function handleFocus() {
  void refreshAccess();
}

function handleAccessDenied(event: Event) {
  const detail = accessDeniedDetail(event);
  if (
    detail?.scope === "platform" ||
    (detail?.scope === "project" &&
      detail.projectId === workspaceStore.currentProjectId)
  ) {
    void refreshAccess(true);
  }
}

onMounted(() => {
  accessRefreshTimer = window.setInterval(() => {
    void refreshAccess();
  }, 60_000);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  window.addEventListener("focus", handleFocus);
  window.addEventListener("platform-access-denied", handleAccessDenied);
});
onUnmounted(() => {
  chatSessionPool.clearScope();
  chatSessionStore.clearAll();
  window.clearInterval(accessRefreshTimer);
  clearTimeout(pendingRefresh);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  window.removeEventListener("focus", handleFocus);
  window.removeEventListener("platform-access-denied", handleAccessDenied);
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
          <div
            v-if="
              routeAccessAllowed &&
              workspaceStore.currentProjectAccess &&
              workspaceStore.accessStatus === 'unavailable'
            "
            role="status"
            class="flex shrink-0 items-center justify-between gap-3 px-4 py-2 text-sm text-amber-800 dark:text-amber-200"
          >
            <span>权限同步暂时不可用，已保留当前页面。</span>
            <button
              class="pw-btn pw-btn-secondary"
              :disabled="refreshingAccess"
              @click="refreshAccess(true)"
            >
              重试
            </button>
          </div>
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
              :title="accessTitle"
              :description="
                routeAccess === 'denied'
                  ? '请切换到有权限的项目，或联系项目管理员申请访问。正在进行的任务不会因页面关闭而自动停止。'
                  : '连接暂时不可用，请稍后重试。正在进行的任务不会因此自动停止。'
              "
              variant="warning"
            />
            <button
              v-if="routeAccess !== 'denied'"
              class="pw-btn pw-btn-secondary"
              :disabled="refreshingAccess || workspaceStore.accessLoading"
              @click="refreshAccess(true)"
            >
              重新连接
            </button>
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
