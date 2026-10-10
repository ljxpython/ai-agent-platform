<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import { useTopbarDropdown } from "@/composables/useTopbarDropdown";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useRunNotificationsStore } from "@/stores/run-notifications";
import {
  resolveFailurePresentation,
  formatNotificationTime,
} from "@/modules/chat/completion/presentation";
import type { RunNotification } from "@/modules/chat/completion/types";

const router = useRouter();
const notificationsStore = useRunNotificationsStore();
const { activeProjectId } = useWorkspaceProjectContext();

const {
  close,
  dropdownPlacement,
  dropdownRef,
  dropdownStyle,
  isOpen,
  open,
  rootRef,
  triggerRef,
} = useTopbarDropdown({
  alignment: "end",
  fallbackWidth: 380,
  minWidth: 340,
});

// 跳转拦截状态
const showConfirmLeaveDialog = ref(false);
const pendingNavigationTarget = ref<{ threadId: string; runId: string } | null>(
  null,
);

const items = computed(() => notificationsStore.items);
const unreadCount = computed(() => notificationsStore.unreadCount);
const isFetching = computed(() => notificationsStore.isFetching);
const hasMore = computed(() => notificationsStore.hasMore);
const isAvailable = computed(
  () => notificationsStore.availability === "available",
);

function toggle() {
  if (isOpen.value) {
    close();
  } else {
    open();
    // 打开时若尚未加载数据则刷新一次
    if (items.value.length === 0) {
      void notificationsStore.fetchFeed();
    }
  }
}

// 监听活动项目切换，重新启动项目级轮询
watch(
  () => activeProjectId.value,
  (newId) => {
    if (newId) {
      notificationsStore.startPolling(newId);
    } else {
      notificationsStore.stopPolling();
    }
  },
  { immediate: true },
);

onMounted(() => {
  if (activeProjectId.value) {
    notificationsStore.startPolling(activeProjectId.value);
  }
});

onUnmounted(() => {
  notificationsStore.stopPolling();
});

/**
 * 处理单条通知点击已读
 */
async function handleMarkRead(event: Event, item: RunNotification) {
  event.stopPropagation();
  if (item.read_at !== null) return;
  try {
    await notificationsStore.markAsRead(item.event_id);
  } catch (err) {
    console.error("标记已读失败:", err);
  }
}

/**
 * 执行实际的跳转
 */
function executeNavigation(threadId: string, runId: string) {
  close();
  void router.push({
    name: "chat",
    query: {
      thread_id: threadId,
      run_id: runId,
    },
  });
}

/**
 * 点击查看会话（带运行保护拦截）
 */
function handleViewSession(item: RunNotification) {
  // 检查当前聊天状态：如果当前正在运行，拦截并弹窗确认
  if (notificationsStore.isChatExecuting) {
    pendingNavigationTarget.value = {
      threadId: item.thread_id,
      runId: item.run_id,
    };
    showConfirmLeaveDialog.value = true;
    return;
  }

  // 顺便标记已读
  if (item.read_at === null) {
    void notificationsStore.markAsRead(item.event_id);
  }

  executeNavigation(item.thread_id, item.run_id);
}

function handleConfirmLeave() {
  showConfirmLeaveDialog.value = false;
  if (pendingNavigationTarget.value) {
    const { threadId, runId } = pendingNavigationTarget.value;
    pendingNavigationTarget.value = null;
    executeNavigation(threadId, runId);
  }
}

function handleCancelLeave() {
  showConfirmLeaveDialog.value = false;
  pendingNavigationTarget.value = null;
}
</script>

<template>
  <div
    v-if="isAvailable"
    ref="rootRef"
    class="relative inline-flex items-center"
  >
    <button
      ref="triggerRef"
      type="button"
      class="pw-topbar-action relative flex h-9 w-9 items-center justify-center rounded-lg border border-transparent text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:text-gray-300 dark:hover:bg-dark-800 dark:hover:text-white"
      :class="{ 'bg-gray-100 dark:bg-dark-800': isOpen }"
      aria-label="运行通知中心"
      :aria-expanded="isOpen"
      @click="toggle"
    >
      <BaseIcon name="bell" class="h-4 w-4" />
      <!-- 未读红点徽标 -->
      <span
        v-if="unreadCount > 0"
        data-testid="notification-unread-badge"
        class="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white shadow-sm ring-2 ring-white dark:ring-dark-900"
      >
        {{ unreadCount > 99 ? "99+" : unreadCount }}
      </span>
    </button>

    <!-- 下拉面板 -->
    <Teleport to="body">
      <div
        v-if="isOpen"
        ref="dropdownRef"
        class="pw-dropdown-surface fixed z-50 flex max-h-[85vh] flex-col rounded-xl border border-gray-200 bg-white shadow-xl dark:border-dark-700 dark:bg-dark-800"
        :style="dropdownStyle"
        :data-placement="dropdownPlacement"
      >
        <!-- 头部 -->
        <div
          class="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-dark-700"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-gray-900 dark:text-white">
              运行失败通知
            </span>
            <span
              v-if="unreadCount > 0"
              class="rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-600 dark:bg-rose-950/40 dark:text-rose-300"
            >
              {{ unreadCount }} 未读
            </span>
          </div>
          <button
            type="button"
            class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            :disabled="isFetching"
            @click="notificationsStore.fetchFeed()"
          >
            <BaseIcon
              name="refresh"
              class="h-3.5 w-3.5"
              :class="{ 'animate-spin': isFetching }"
            />
          </button>
        </div>

        <!-- 列表容器 -->
        <div
          class="flex-1 overflow-y-auto divide-y divide-gray-100 px-2 py-1.5 dark:divide-dark-700/60"
        >
          <div
            v-if="items.length === 0"
            class="flex flex-col items-center justify-center py-10 text-center text-gray-400 dark:text-dark-400"
          >
            <BaseIcon name="check" class="mb-2 h-8 w-8 text-emerald-500/70" />
            <p class="text-xs">暂无未处理的失败运行</p>
          </div>

          <div
            v-for="item in items"
            :key="item.event_id"
            data-testid="notification-item"
            class="group relative flex flex-col gap-1.5 rounded-lg p-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-dark-700/40"
            :class="{
              'bg-rose-50/30 dark:bg-rose-950/10': item.read_at === null,
            }"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-1.5">
                <span
                  class="h-2 w-2 shrink-0 rounded-full"
                  :class="
                    item.read_at === null
                      ? 'bg-rose-500'
                      : 'bg-gray-300 dark:bg-dark-500'
                  "
                />
                <span
                  class="text-xs font-semibold text-gray-900 dark:text-white"
                >
                  {{ resolveFailurePresentation(item).title }}
                </span>
              </div>
              <span class="text-[11px] text-gray-400 shrink-0">
                {{ formatNotificationTime(item.occurred_at) }}
              </span>
            </div>

            <p class="text-xs text-gray-500 line-clamp-2 dark:text-gray-400">
              {{ resolveFailurePresentation(item).detail }}
            </p>

            <div class="mt-1 flex items-center justify-between gap-2">
              <span class="text-[11px] text-gray-400">
                建议：{{ resolveFailurePresentation(item).suggestedAction }}
              </span>
              <div class="flex items-center gap-2">
                <button
                  v-if="item.read_at === null"
                  type="button"
                  data-testid="mark-read-button"
                  class="text-[11px] text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  @click="(e) => handleMarkRead(e, item)"
                >
                  标为已读
                </button>
                <BaseButton
                  size="xs"
                  variant="secondary"
                  data-testid="view-thread-button"
                  @click="handleViewSession(item)"
                >
                  查看会话
                </BaseButton>
              </div>
            </div>
          </div>

          <!-- 加载更多 -->
          <div v-if="hasMore" class="p-2 text-center">
            <BaseButton
              size="xs"
              variant="ghost"
              class="w-full text-xs"
              :disabled="isFetching"
              @click="notificationsStore.loadMore()"
            >
              {{ isFetching ? "加载中..." : "加载更多历史通知" }}
            </BaseButton>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 运行中离开确认对话框 -->
    <BaseDialog
      :show="showConfirmLeaveDialog"
      title="正在运行提示"
      @close="handleCancelLeave"
    >
      <div class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-300">
          当前会话正在执行 Agent
          任务中。此时切换至其他会话将离开实时视图，执行将在后台继续进行。
        </p>
        <p class="text-xs text-gray-400">是否确认切换到目标历史会话？</p>
        <div class="flex justify-end gap-2 pt-2">
          <BaseButton variant="secondary" size="sm" @click="handleCancelLeave">
            留在当前会话
          </BaseButton>
          <BaseButton variant="danger" size="sm" @click="handleConfirmLeave">
            确认离开并查看
          </BaseButton>
        </div>
      </div>
    </BaseDialog>
  </div>
</template>
