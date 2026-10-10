import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";
import type { RunNotification } from "@/modules/chat/completion/types";
import {
  getRunNotifications,
  readRunNotification,
} from "@/services/run-notifications/run-notifications.service";

export interface UseRunNotificationsStoreOptions {
  projectId?: string;
}

const DEFAULT_POLL_INTERVAL_MS = 15000;
const MAX_BACKOFF_INTERVAL_MS = 60000;

export const useRunNotificationsStore = defineStore("run-notifications", () => {
  // 状态定义
  const items = ref<RunNotification[]>([]);
  const unreadCount = ref<number>(0);
  const availability = ref<"available" | "disabled" | "unavailable">(
    "available",
  );
  const nextCursor = ref<string | null>(null);
  const scanLimitReached = ref<boolean>(false);
  const isFetching = ref<boolean>(false);
  const isPolling = ref<boolean>(false);
  const isChatExecuting = ref<boolean>(false);
  const activeProjectId = ref<string>("");
  const lastError = shallowRef<Error | null>(null);

  // 在线已通知去重集合（内存持久）
  const notifiedRunIds = ref<Set<string>>(new Set());

  // 内部调度控制
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let activeAbortController: AbortController | null = null;
  let consecutive503Count = 0;
  let isVisibilityListenerAttached = false;

  const hasMore = computed(() => nextCursor.value !== null);

  function clearTimer() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function abortPending() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  }

  /**
   * 安排下一次轮询（递归 setTimeout，彻底防堆叠）
   */
  function scheduleNextPoll(delayMs = DEFAULT_POLL_INTERVAL_MS) {
    clearTimer();
    if (!isPolling.value) return;

    // 如果页面处于后台，暂停定时轮询调度
    if (
      typeof document !== "undefined" &&
      document.visibilityState === "hidden"
    ) {
      return;
    }

    pollTimer = setTimeout(() => {
      if (isPolling.value) {
        void fetchFeed({ isPoll: true });
      }
    }, delayMs);
  }

  /**
   * 计算指数退避延迟
   */
  function calculateBackoffDelay(): number {
    const delay = DEFAULT_POLL_INTERVAL_MS * Math.pow(2, consecutive503Count);
    return Math.min(delay, MAX_BACKOFF_INTERVAL_MS);
  }

  /**
   * 拉取通知 Feed
   * @param options.isPoll 是否为定时轮询触发
   * @param options.cursor 分页游标（仅在加载更多历史时传入）
   * @param options.append 是否追加到当前列表
   */
  async function fetchFeed(
    options: {
      isPoll?: boolean;
      cursor?: string | null;
      append?: boolean;
    } = {},
  ): Promise<void> {
    // 单飞互斥锁：如果已有请求在执行，放弃本次重叠请求
    if (isFetching.value) {
      return;
    }

    const pId = activeProjectId.value || undefined;
    const isAppend = Boolean(options.append && options.cursor);

    isFetching.value = true;
    abortPending();

    const controller = new AbortController();
    activeAbortController = controller;

    try {
      const response = await getRunNotifications({
        projectId: pId,
        limit: 20,
        cursor: options.cursor ?? null,
        unreadOnly: !isAppend, // 轮询第一页拉未读，历史分页按快照全量浏览
        signal: controller.signal,
      });

      if (controller.signal.aborted) return;

      availability.value = response.availability;
      scanLimitReached.value = response.scan_limit_reached;

      if (response.availability === "disabled") {
        items.value = [];
        unreadCount.value = 0;
        nextCursor.value = null;
        isPolling.value = false;
        clearTimer();
        return;
      }

      // 仅在展示 error / timeout 状态的通知
      const validNotifications = response.items.filter(
        (item) => item.status === "error" || item.status === "timeout",
      );

      if (isAppend) {
        // 追加历史分页（按 event_id 去重）
        const existingIds = new Set(items.value.map((i) => i.event_id));
        const newItems = validNotifications.filter(
          (i) => !existingIds.has(i.event_id),
        );
        items.value = [...items.value, ...newItems];
        nextCursor.value = response.next_cursor;
      } else {
        // 刷新第一页顶部快照
        items.value = validNotifications;
        nextCursor.value = response.next_cursor;
        // 计算当前未读数量（未读且未标记 read_at）
        unreadCount.value = validNotifications.filter(
          (i) => i.read_at === null,
        ).length;
      }

      // 成功响应重置退避计数
      consecutive503Count = 0;
      lastError.value = null;

      // 若处于轮询模式，安排下一轮 15s 轮询
      if (isPolling.value) {
        scheduleNextPoll(DEFAULT_POLL_INTERVAL_MS);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;

      const error = err as Error & { status?: number; code?: string };
      lastError.value = error;

      // 503 或网络异常：执行有界指数退避
      if (error.status === 503 || !error.status) {
        consecutive503Count++;
        const backoffDelay = calculateBackoffDelay();
        if (isPolling.value) {
          scheduleNextPoll(backoffDelay);
        }
      } else if (error.status === 401) {
        // 401 未登录：停止轮询清空数据
        stopPolling();
        items.value = [];
        unreadCount.value = 0;
      } else if (error.status === 403) {
        // 403 无权限：标为暂不可用
        availability.value = "unavailable";
      }
    } finally {
      if (activeAbortController === controller) {
        activeAbortController = null;
      }
      isFetching.value = false;
    }
  }

  /**
   * 页面可见性变化监听
   */
  function onVisibilityChange() {
    if (typeof document === "undefined") return;

    if (document.visibilityState === "visible") {
      // 唤醒前台：如果轮询处于开启状态，立即补拉并重置 15s 调度
      if (isPolling.value) {
        clearTimer();
        void fetchFeed({ isPoll: true });
      }
    } else {
      // 切到后台：暂停待命定时器
      clearTimer();
    }
  }

  /**
   * 启动通知轮询
   */
  function startPolling(projectId?: string) {
    if (projectId !== undefined) {
      // 若切换了项目，重置状态
      if (activeProjectId.value !== projectId) {
        activeProjectId.value = projectId;
        items.value = [];
        unreadCount.value = 0;
        nextCursor.value = null;
        consecutive503Count = 0;
      }
    }

    isPolling.value = true;

    // 注册 visibilitychange 监听
    if (
      !isVisibilityListenerAttached &&
      typeof document !== "undefined" &&
      typeof document.addEventListener === "function"
    ) {
      document.addEventListener("visibilitychange", onVisibilityChange);
      isVisibilityListenerAttached = true;
    }

    // 立即触发首次拉取
    void fetchFeed({ isPoll: true });
  }

  /**
   * 停止通知轮询并清理
   */
  function stopPolling() {
    isPolling.value = false;
    clearTimer();
    abortPending();

    if (
      isVisibilityListenerAttached &&
      typeof document !== "undefined" &&
      typeof document.removeEventListener === "function"
    ) {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      isVisibilityListenerAttached = false;
    }
  }

  /**
   * 乐观更新已读并调用后端接口
   */
  async function markAsRead(eventId: string): Promise<boolean> {
    const target = items.value.find((item) => item.event_id === eventId);
    if (!target || target.read_at !== null) {
      return false;
    }

    // 1. 乐观更新
    const previousReadAt = target.read_at;
    const previousUnreadCount = unreadCount.value;

    target.read_at = new Date().toISOString();
    unreadCount.value = Math.max(0, unreadCount.value - 1);

    try {
      await readRunNotification(eventId, {
        projectId: activeProjectId.value || undefined,
      });
      return true;
    } catch (err: unknown) {
      // 2. 失败回滚
      target.read_at = previousReadAt;
      unreadCount.value = previousUnreadCount;
      throw err;
    }
  }

  /**
   * 加载更多历史分页
   */
  async function loadMore(): Promise<void> {
    if (!nextCursor.value || isFetching.value) return;
    await fetchFeed({
      cursor: nextCursor.value,
      append: true,
    });
  }

  /**
   * 判定是否应抑制在线 Toast 弹窗（借鉴 open-swe）
   */
  function shouldSuppressToast(
    threadId: string,
    runId: string,
    activeThreadId: string | null | undefined,
    isSdkErrorDisplayed: boolean,
  ): boolean {
    const isVisible =
      typeof document !== "undefined" && document.visibilityState === "visible";
    const isViewingCurrentThread =
      Boolean(activeThreadId) && activeThreadId === threadId;

    // 双重前台抑制：页面前台可见 + 正在查看当前 Thread + SDK 已展示错误
    if (isVisible && isViewingCurrentThread && isSdkErrorDisplayed) {
      return true;
    }

    // 如果已通告过该 Run，也抑制重复弹窗
    if (notifiedRunIds.value.has(runId)) {
      return true;
    }

    return false;
  }

  function recordRunNotified(runId: string) {
    notifiedRunIds.value.add(runId);
  }

  return {
    // 状态
    items,
    unreadCount,
    availability,
    nextCursor,
    scanLimitReached,
    isFetching,
    isPolling,
    isChatExecuting,
    activeProjectId,
    lastError,
    hasMore,
    notifiedRunIds,

    // 动作
    startPolling,
    stopPolling,
    fetchFeed,
    markAsRead,
    loadMore,
    shouldSuppressToast,
    recordRunNotified,
  };
});
