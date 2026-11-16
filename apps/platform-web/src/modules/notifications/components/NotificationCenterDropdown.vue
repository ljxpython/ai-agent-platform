<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useTopbarDropdown } from "@/composables/useTopbarDropdown";
import { useNotificationCenterStore } from "../stores/useNotificationCenterStore";
import type { NotificationItem, NotificationLevel } from "../types";

const router = useRouter();
const store = useNotificationCenterStore();

const { close, dropdownRef, dropdownStyle, isOpen, open, rootRef, triggerRef } =
  useTopbarDropdown({
    alignment: "end",
    fallbackWidth: 420,
    minWidth: 360,
  });

const currentTab = ref<string>("all");

const filteredItems = computed(() => {
  if (currentTab.value === "all") return store.items;
  return store.items.filter((item) => item.level === currentTab.value);
});

function toggle() {
  if (isOpen.value) {
    close();
  } else {
    open();
    void store.fetchFeed();
  }
}

function handleTabChange(tab: string) {
  currentTab.value = tab;
  void store.fetchFeed({
    level: tab === "all" ? undefined : (tab as NotificationLevel),
  });
}

function formatRelativeTime(dateStr: string): string {
  try {
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    return `${Math.floor(diff / 86400)} 天前`;
  } catch {
    return dateStr;
  }
}

function getLevelBadge(level: NotificationLevel) {
  switch (level) {
    case "critical":
      return {
        label: "严重",
        class: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
      };
    case "error":
      return {
        label: "错误",
        class:
          "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
      };
    case "warning":
      return {
        label: "警告",
        class:
          "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
      };
    default:
      return {
        label: "信息",
        class:
          "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
      };
  }
}

async function handleItemClick(item: NotificationItem) {
  if (item.status === "unread") {
    await store.markRead(item.id);
  }
  if (item.action_url) {
    close();
    if (
      item.action_url.startsWith("http://") ||
      item.action_url.startsWith("https://")
    ) {
      window.open(item.action_url, "_blank");
    } else {
      await router.push(item.action_url);
    }
  }
}

onMounted(() => {
  store.startPolling(15000);
});

onUnmounted(() => {
  store.stopPolling();
});
</script>

<template>
  <div ref="rootRef" class="relative inline-block text-left">
    <!-- 顶部铃铛触发器 -->
    <button
      ref="triggerRef"
      type="button"
      class="pw-topbar-action relative flex items-center justify-center rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white"
      :class="{
        'bg-gray-100 dark:bg-dark-800 text-gray-900 dark:text-white': isOpen,
      }"
      aria-label="查看通知与告警"
      @click="toggle"
    >
      <svg
        class="h-5 w-5"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.7"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
        />
      </svg>

      <!-- 未读红点徽标 -->
      <span
        v-if="store.unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white shadow-sm ring-2 ring-white dark:ring-dark-900 animate-in fade-in"
      >
        {{ store.unreadCount > 99 ? "99+" : store.unreadCount }}
      </span>
    </button>

    <!-- 下拉面板 -->
    <Teleport to="body">
      <div
        v-if="isOpen"
        ref="dropdownRef"
        class="pw-topbar-dropdown fixed z-50 flex max-h-[85vh] flex-col rounded-2xl border border-gray-200 bg-white/95 shadow-2xl backdrop-blur-xl dark:border-dark-700 dark:bg-dark-900/95"
        :style="dropdownStyle"
      >
        <!-- 面板头部 -->
        <div
          class="flex items-center justify-between border-b border-gray-100 px-4 py-3 dark:border-dark-800"
        >
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-gray-900 dark:text-white"
              >通知与告警中心</span
            >
            <span
              v-if="store.unreadCount > 0"
              class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-600 dark:bg-red-950/40 dark:text-red-400"
            >
              {{ store.unreadCount }} 条未读
            </span>
          </div>
          <div class="flex items-center gap-2 text-xs">
            <button
              v-if="store.unreadCount > 0"
              type="button"
              class="text-blue-600 transition-colors hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
              @click="store.markAllRead"
            >
              全部已读
            </button>
            <RouterLink
              to="/settings/notifications"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 p-1"
              title="配置通知与飞书机器人"
              @click="close"
            >
              ⚙️
            </RouterLink>
          </div>
        </div>

        <!-- 过滤 Tab -->
        <div
          class="flex border-b border-gray-100 px-4 text-xs font-medium dark:border-dark-800"
        >
          <button
            v-for="tab in [
              { key: 'all', label: '全部' },
              { key: 'critical', label: '🚨 严重' },
              { key: 'warning', label: '⚠️ 警告' },
              { key: 'info', label: 'ℹ️ 信息' },
            ]"
            :key="tab.key"
            type="button"
            class="border-b-2 py-2 px-2.5 transition-colors"
            :class="
              currentTab === tab.key
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-semibold'
                : 'border-transparent text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-dark-200'
            "
            @click="handleTabChange(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- 列表容器 -->
        <div
          class="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-dark-800"
        >
          <div
            v-if="store.isFetching && store.items.length === 0"
            class="p-8 text-center text-xs text-gray-400"
          >
            正在拉取最新告警...
          </div>

          <div
            v-else-if="filteredItems.length === 0"
            class="flex flex-col items-center justify-center p-12 text-center"
          >
            <span class="text-3xl mb-2">🎉</span>
            <p class="text-xs text-gray-500 dark:text-dark-400 font-medium">
              无待处理的告警与通知
            </p>
            <p class="text-[11px] text-gray-400 dark:text-dark-500 mt-1">
              系统一切运行良好，持续守护中
            </p>
          </div>

          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="group relative flex flex-col gap-1.5 p-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-dark-800/60 cursor-pointer"
            :class="{
              'bg-blue-50/30 dark:bg-blue-950/10': item.status === 'unread',
            }"
            @click="handleItemClick(item)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-2">
                <span
                  class="inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold"
                  :class="getLevelBadge(item.level).class"
                >
                  {{ getLevelBadge(item.level).label }}
                </span>
                <span
                  class="text-xs font-semibold text-gray-900 dark:text-white line-clamp-1"
                  :class="{ 'font-bold': item.status === 'unread' }"
                >
                  {{ item.title }}
                </span>
              </div>
              <span
                class="shrink-0 text-[10px] text-gray-400 dark:text-dark-500"
              >
                {{ formatRelativeTime(item.created_at) }}
              </span>
            </div>

            <p
              class="text-[11px] text-gray-600 dark:text-dark-300 line-clamp-2 leading-relaxed"
            >
              {{ item.content }}
            </p>

            <div
              v-if="item.action_url"
              class="mt-1 flex items-center gap-1 text-[11px] font-medium text-blue-600 dark:text-blue-400"
            >
              <span>立即前往排障排错</span>
              <span>→</span>
            </div>
          </div>
        </div>

        <!-- 面板底部 -->
        <div
          class="border-t border-gray-100 bg-gray-50/50 p-2 text-center dark:border-dark-800 dark:bg-dark-900"
        >
          <RouterLink
            to="/settings/notifications"
            class="text-[11px] text-gray-500 hover:text-blue-600 dark:text-dark-400 dark:hover:text-blue-400 transition-colors"
            @click="close"
          >
            管理通知与飞书推送渠道 →
          </RouterLink>
        </div>
      </div>
    </Teleport>
  </div>
</template>
