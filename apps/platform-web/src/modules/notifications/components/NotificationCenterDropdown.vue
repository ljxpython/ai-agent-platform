<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import BaseDialog from "@/components/base/BaseDialog.vue";
import { useTopbarDropdown } from "@/composables/useTopbarDropdown";
import { useNotificationCenterStore } from "../stores/useNotificationCenterStore";
import type { NotificationItem, NotificationLevel } from "../types";
import {
  cleanNotificationTitle,
  getNotificationActionInfo,
  getNotificationLevelBadge,
  resolveNotificationActionUrl,
} from "../utils/notification-action";

const router = useRouter();
const store = useNotificationCenterStore();

const { close, dropdownRef, dropdownStyle, isOpen, open, rootRef, triggerRef } =
  useTopbarDropdown({
    alignment: "end",
    fallbackWidth: 440,
    minWidth: 380,
  });

const currentTab = ref<string>("all");
const selectedItem = ref<NotificationItem | null>(null);

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

function handleCardClick(item: NotificationItem) {
  if (item.status === "unread") {
    void store.markRead(item.id);
  }
  selectedItem.value = item;
}

function executeAction(item: NotificationItem, event?: Event) {
  if (event) {
    event.stopPropagation();
  }
  if (item.status === "unread") {
    void store.markRead(item.id);
  }
  const resolved = resolveNotificationActionUrl(item);
  if (!resolved) return;

  close();
  selectedItem.value = null;

  if (resolved.startsWith("http://") || resolved.startsWith("https://")) {
    window.open(resolved, "_blank");
  } else {
    void router.push(resolved);
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
              to="/workspace/settings/notifications?tab=channels"
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
            class="group relative flex flex-col gap-2 p-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-dark-800/60 cursor-pointer"
            :class="{
              'bg-blue-50/25 dark:bg-blue-950/15': item.status === 'unread',
            }"
            @click="handleCardClick(item)"
          >
            <!-- 头部：未读点 + 等级 Badge + 标题 + 时间 -->
            <div class="flex items-start justify-between gap-3">
              <div class="flex min-w-0 flex-1 items-center gap-1.5">
                <!-- 未读小蓝点 -->
                <span
                  v-if="item.status === 'unread'"
                  class="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600 dark:bg-blue-400"
                  title="未读消息"
                />
                <!-- 等级 Badge：坚决不折行 -->
                <span
                  class="inline-flex shrink-0 whitespace-nowrap items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide"
                  :class="getNotificationLevelBadge(item.level).class"
                >
                  {{ getNotificationLevelBadge(item.level).label }}
                </span>
                <!-- 干净无前缀标题 -->
                <span
                  class="truncate text-xs text-gray-900 dark:text-white"
                  :class="
                    item.status === 'unread' ? 'font-bold' : 'font-medium'
                  "
                  :title="item.title"
                >
                  {{ cleanNotificationTitle(item.title) }}
                </span>
              </div>
              <!-- 贴边时间 -->
              <span
                class="shrink-0 whitespace-nowrap text-[10px] text-gray-400 dark:text-dark-400 pt-0.5"
              >
                {{ formatRelativeTime(item.created_at) }}
              </span>
            </div>

            <!-- 正文描述 -->
            <p
              class="text-[11px] leading-relaxed text-gray-600 dark:text-dark-300 line-clamp-2"
              :class="item.status === 'unread' ? 'pl-3' : ''"
            >
              {{ item.content }}
            </p>

            <!-- 操作链接：根据状态动态呈现优雅文案与色彩 -->
            <div
              v-if="resolveNotificationActionUrl(item)"
              class="mt-0.5 flex items-center gap-1 text-[11px] font-medium transition-colors"
              :class="[
                getNotificationActionInfo(item).colorClass,
                item.status === 'unread' ? 'pl-3' : '',
              ]"
              @click.stop="executeAction(item, $event)"
            >
              <span>{{ getNotificationActionInfo(item).label }}</span>
              <span class="transition-transform group-hover:translate-x-0.5"
                >→</span
              >
            </div>
          </div>
        </div>

        <!-- 面板底部 -->
        <div
          class="border-t border-gray-100 bg-gray-50/50 p-2 text-center dark:border-dark-800 dark:bg-dark-900"
        >
          <RouterLink
            to="/workspace/settings/notifications?tab=history"
            class="text-[11px] text-gray-500 hover:text-blue-600 dark:text-dark-400 dark:hover:text-blue-400 transition-colors inline-flex items-center gap-1"
            @click="close"
          >
            <span>查看完整消息与告警历史</span>
            <span>→</span>
          </RouterLink>
        </div>
      </div>
    </Teleport>

    <!-- 详情弹窗 -->
    <BaseDialog
      :show="!!selectedItem"
      :title="cleanNotificationTitle(selectedItem?.title || '通知详情')"
      width="normal"
      @close="selectedItem = null"
    >
      <div v-if="selectedItem" class="space-y-4">
        <!-- 头部等级与时间 -->
        <div
          class="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-dark-800"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-flex shrink-0 whitespace-nowrap items-center rounded-md border px-2 py-0.5 text-xs font-semibold"
              :class="getNotificationLevelBadge(selectedItem.level).class"
            >
              {{ getNotificationLevelBadge(selectedItem.level).label }}
            </span>
            <span class="text-xs text-gray-500 dark:text-dark-400 capitalize">
              {{ selectedItem.category }}
            </span>
          </div>
          <span class="text-xs text-gray-400 dark:text-dark-500 font-mono">
            {{ formatRelativeTime(selectedItem.created_at) }}
          </span>
        </div>

        <!-- 消息正文 -->
        <div
          class="rounded-xl bg-gray-50/70 p-3.5 text-xs leading-relaxed text-gray-800 dark:bg-dark-800/60 dark:text-dark-200 break-words whitespace-pre-wrap"
        >
          {{ selectedItem.content }}
        </div>

        <!-- 告警与诊断元数据 (如有) -->
        <div
          v-if="
            selectedItem.extra_metadata &&
            Object.keys(selectedItem.extra_metadata).length > 0
          "
          class="space-y-1.5"
        >
          <h4
            class="text-[11px] font-semibold text-gray-500 dark:text-dark-400 uppercase tracking-wider"
          >
            排障上下文与元数据
          </h4>
          <div
            class="max-h-48 overflow-y-auto rounded-lg bg-gray-100/90 p-2.5 font-mono text-[11px] text-gray-700 dark:bg-dark-900/90 dark:text-dark-300"
          >
            <pre class="whitespace-pre-wrap break-all">{{
              JSON.stringify(selectedItem.extra_metadata, null, 2)
            }}</pre>
          </div>
        </div>

        <!-- 弹窗底部操作按钮 -->
        <div
          class="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-dark-800"
        >
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:text-dark-400 dark:hover:bg-dark-800 transition-colors"
            @click="selectedItem = null"
          >
            关闭
          </button>

          <button
            v-if="resolveNotificationActionUrl(selectedItem)"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors"
            :class="
              selectedItem.level === 'critical' ||
              selectedItem.level === 'error'
                ? 'bg-rose-600 hover:bg-rose-700'
                : 'bg-blue-600 hover:bg-blue-700'
            "
            @click="executeAction(selectedItem)"
          >
            <span>{{ getNotificationActionInfo(selectedItem).label }}</span>
            <span>→</span>
          </button>
        </div>
      </div>
    </BaseDialog>
  </div>
</template>
