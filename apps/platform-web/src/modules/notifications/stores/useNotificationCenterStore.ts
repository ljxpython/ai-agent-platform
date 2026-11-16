import { defineStore } from "pinia";
import { ref } from "vue";
import {
  createChannel as apiCreateChannel,
  deleteChannel as apiDeleteChannel,
  fetchChannels as apiFetchChannels,
  fetchNotifications as apiFetchNotifications,
  fetchUnreadCount as apiFetchUnreadCount,
  markAllNotificationsRead as apiMarkAllNotificationsRead,
  markNotificationRead as apiMarkNotificationRead,
  testChannel as apiTestChannel,
  updateChannel as apiUpdateChannel,
} from "../api";
import type {
  CreateChannelRequest,
  NotificationChannelItem,
  NotificationItem,
  NotificationLevel,
  TestChannelResponse,
  UpdateChannelRequest,
} from "../types";

export const useNotificationCenterStore = defineStore(
  "notificationCenter",
  () => {
    const items = ref<NotificationItem[]>([]);
    const unreadCount = ref<number>(0);
    const total = ref<number>(0);
    const isFetching = ref<boolean>(false);
    const channels = ref<NotificationChannelItem[]>([]);
    const isTesting = ref<boolean>(false);

    let pollTimer: ReturnType<typeof setInterval> | null = null;

    async function fetchCount(): Promise<void> {
      try {
        const count = await apiFetchUnreadCount();
        unreadCount.value = count;
      } catch {
        // 静默降级
      }
    }

    async function fetchFeed(params?: {
      level?: NotificationLevel;
      project_id?: string;
    }): Promise<void> {
      isFetching.value = true;
      try {
        const page = await apiFetchNotifications({
          limit: 30,
          offset: 0,
          level: params?.level,
          project_id: params?.project_id,
        });
        items.value = page.items;
        total.value = page.total;
        unreadCount.value = page.unread_count;
      } catch (err) {
        console.warn("加载站内信失败", err);
      } finally {
        isFetching.value = false;
      }
    }

    async function markRead(id: string): Promise<void> {
      // 乐观更新
      const target = items.value.find((i) => i.id === id);
      if (target && target.status === "unread") {
        target.status = "read";
        unreadCount.value = Math.max(0, unreadCount.value - 1);
      }
      try {
        await apiMarkNotificationRead(id);
      } catch (err) {
        console.error("标记已读失败", err);
      }
    }

    async function markAllRead(): Promise<void> {
      // 乐观更新
      items.value.forEach((i) => {
        i.status = "read";
      });
      unreadCount.value = 0;
      try {
        await apiMarkAllNotificationsRead();
      } catch (err) {
        console.error("全部标记已读失败", err);
      }
    }

    function startPolling(intervalMs = 15000): void {
      stopPolling();
      void fetchCount();
      pollTimer = setInterval(() => {
        void fetchCount();
      }, intervalMs);
    }

    function stopPolling(): void {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    // --- 渠道管理 ---

    async function loadChannels(project_id?: string): Promise<void> {
      try {
        channels.value = await apiFetchChannels({ project_id });
      } catch (err) {
        console.warn("获取渠道列表失败", err);
      }
    }

    async function addChannel(
      data: CreateChannelRequest,
    ): Promise<NotificationChannelItem> {
      const created = await apiCreateChannel(data);
      channels.value.unshift(created);
      return created;
    }

    async function editChannel(
      id: string,
      data: UpdateChannelRequest,
    ): Promise<NotificationChannelItem> {
      const updated = await apiUpdateChannel(id, data);
      const idx = channels.value.findIndex((c) => c.id === id);
      if (idx !== -1) {
        channels.value[idx] = updated;
      }
      return updated;
    }

    async function removeChannel(id: string): Promise<void> {
      await apiDeleteChannel(id);
      channels.value = channels.value.filter((c) => c.id !== id);
    }

    async function runTestChannel(id: string): Promise<TestChannelResponse> {
      isTesting.value = true;
      try {
        return await apiTestChannel(id);
      } finally {
        isTesting.value = false;
      }
    }

    return {
      items,
      unreadCount,
      total,
      isFetching,
      channels,
      isTesting,
      fetchCount,
      fetchFeed,
      markRead,
      markAllRead,
      startPolling,
      stopPolling,
      loadChannels,
      addChannel,
      editChannel,
      removeChannel,
      runTestChannel,
    };
  },
);
