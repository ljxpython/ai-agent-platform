import {
  computed,
  ref,
  shallowRef,
  watch,
  getCurrentScope,
  onScopeDispose,
  toValue,
  type Ref,
  type ComputedRef,
} from "vue";
import type { createSessionService } from "@/services/threads/session.service";
import type {
  StopPhase,
  StopRequest,
  StopReport,
  QueueCounts,
} from "../stop/types";
import { extractPlatformHttpError } from "@/utils/http-error";

export interface PersistedStopRecord {
  key: string;
  threadId: string;
  stopId?: string;
  requestedAt: number;
  status: "submitting" | "stopping" | "unknown";
}

export interface UseThreadStopControlOptions {
  projectId: Ref<string> | ComputedRef<string>;
  threadId: Ref<string | null> | ComputedRef<string | null>;
  userId?: Ref<string | undefined> | ComputedRef<string | undefined>;
  sessionEpoch?: Ref<number | string> | ComputedRef<number | string>;
  service: ReturnType<typeof createSessionService>;
  canWrite?: Ref<boolean> | ComputedRef<boolean>;
  onStopConfirmed?: (receipt: StopRequest) => void;
}

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_DURATION_MS = 45000;
const MAX_PERSISTENCE_AGE_MS = 3600000; // 1 小时

export function useThreadStopControl(options: UseThreadStopControlOptions) {
  const phase = ref<StopPhase | "idle" | "submitting">("idle");
  const latestReceipt = shallowRef<StopRequest | null>(null);
  const stopError = ref<string>("");
  const currentStopId = ref<string | null>(null);
  const activeKey = ref<string | null>(null);

  let currentEpoch = 0;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  let pollStartTime = 0;
  let isPollingInFlight = false;
  let isDisposed = false;

  const submitting = computed(() => phase.value === "submitting");
  const isStopping = computed(
    () =>
      phase.value === "submitting" ||
      phase.value === "stopping" ||
      phase.value === "accepted",
  );
  const isConfirmed = computed(
    () => phase.value === "stopped" || phase.value === "no_active_run",
  );
  const isConfirmationUnavailable = computed(
    () => phase.value === "confirmation_unavailable",
  );
  const targetCount = computed(() => latestReceipt.value?.target_count ?? null);
  const report = computed<StopReport | null>(
    () => latestReceipt.value?.report ?? null,
  );
  const queueCounts = computed<QueueCounts | null>(
    () => latestReceipt.value?.queue ?? null,
  );

  function getStorageKey(tid: string): string {
    const uid = toValue(options.userId) ?? "anonymous";
    const epoch = toValue(options.sessionEpoch) ?? 0;
    const pid = toValue(options.projectId);
    return `pw:thread:stop:${uid}:${epoch}:${pid}:${tid}`;
  }

  function loadPersistedRecord(tid: string): PersistedStopRecord | null {
    if (typeof localStorage === "undefined") return null;
    try {
      const raw = localStorage.getItem(getStorageKey(tid));
      if (!raw) return null;
      const parsed = JSON.parse(raw) as PersistedStopRecord;
      if (
        !parsed.key ||
        parsed.threadId !== tid ||
        Date.now() - parsed.requestedAt > MAX_PERSISTENCE_AGE_MS
      ) {
        clearPersistedRecord(tid);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }

  function savePersistedRecord(record: PersistedStopRecord): void {
    if (typeof localStorage === "undefined") return;
    try {
      localStorage.setItem(
        getStorageKey(record.threadId),
        JSON.stringify(record),
      );
    } catch {
      /* ignore storage failure */
    }
  }

  function clearPersistedRecord(tid: string): void {
    if (typeof localStorage === "undefined") return;
    try {
      localStorage.removeItem(getStorageKey(tid));
    } catch {
      /* ignore storage failure */
    }
  }

  function clearTimer(): void {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
    isPollingInFlight = false;
  }

  function handleTerminalReceipt(
    receipt: StopRequest,
    generation: number,
  ): void {
    if (generation !== currentEpoch || isDisposed) return;
    latestReceipt.value = receipt;
    phase.value = receipt.phase;
    currentStopId.value = receipt.stop_id;
    const tid = toValue(options.threadId);
    if (tid) clearPersistedRecord(tid);
    clearTimer();

    if (receipt.phase === "stopped" || receipt.phase === "no_active_run") {
      options.onStopConfirmed?.(receipt);
    } else if (receipt.phase === "rejected") {
      stopError.value = receipt.reason_code ?? "停止请求已被拒绝";
    }
  }

  async function pollStep(stopId: string, generation: number): Promise<void> {
    if (
      generation !== currentEpoch ||
      isDisposed ||
      !toValue(options.threadId)
    ) {
      clearTimer();
      return;
    }

    if (Date.now() - pollStartTime > MAX_POLL_DURATION_MS) {
      clearTimer();
      phase.value = "confirmation_unavailable";
      stopError.value = "停止确认超时，请手动核实";
      return;
    }

    if (isPollingInFlight) return;
    isPollingInFlight = true;

    try {
      const tid = toValue(options.threadId)!;
      const res = await options.service.getStopRequest(tid, stopId);
      if (generation !== currentEpoch || isDisposed) return;

      latestReceipt.value = res;
      if (
        res.phase === "stopped" ||
        res.phase === "no_active_run" ||
        res.phase === "rejected"
      ) {
        handleTerminalReceipt(res, generation);
        return;
      }

      if (res.phase === "confirmation_unavailable") {
        clearTimer();
        phase.value = "confirmation_unavailable";
        if (res.reason_code) {
          stopError.value =
            res.reason_code === "resource_cleanup_unconfirmed"
              ? "运行已停止，部分资源清理尚未确认"
              : res.reason_code;
        }
        return;
      }

      phase.value = "stopping";
    } catch (cause) {
      if (generation !== currentEpoch || isDisposed) return;
      const err = extractPlatformHttpError(cause);
      if (err.status === 404 || err.status === 403) {
        clearTimer();
        phase.value = "rejected";
        stopError.value = err.message || "无法继续核实停止状态";
        const tid = toValue(options.threadId);
        if (tid) clearPersistedRecord(tid);
        return;
      }
      /* 网络临时错误保持轮询，直到 45s 超时 */
    } finally {
      isPollingInFlight = false;
      if (
        generation === currentEpoch &&
        !isDisposed &&
        (phase.value === "stopping" || phase.value === "accepted")
      ) {
        if (
          !pollTimer &&
          (typeof document === "undefined" || !document.hidden)
        ) {
          pollTimer = setTimeout(() => {
            pollTimer = null;
            void pollStep(stopId, generation);
          }, POLL_INTERVAL_MS);
        }
      }
    }
  }

  function startPolling(stopId: string, generation: number): void {
    clearTimer();
    pollStartTime = Date.now();
    pollTimer = setTimeout(() => {
      pollTimer = null;
      void pollStep(stopId, generation);
    }, POLL_INTERVAL_MS);
  }

  async function stop(): Promise<StopRequest | null> {
    const tid = toValue(options.threadId);
    if (!tid || isDisposed) return null;
    if (isStopping.value) return latestReceipt.value;

    const generation = ++currentEpoch;
    clearTimer();

    const existingRecord = loadPersistedRecord(tid);
    const key =
      existingRecord?.status === "unknown" && existingRecord.key
        ? existingRecord.key
        : `stop:${crypto.randomUUID()}`;

    activeKey.value = key;
    phase.value = "submitting";
    stopError.value = "";

    savePersistedRecord({
      key,
      threadId: tid,
      requestedAt: Date.now(),
      status: "submitting",
    });

    try {
      const res = await options.service.stopThread(tid, key);
      if (generation !== currentEpoch || isDisposed) return null;

      latestReceipt.value = res;
      currentStopId.value = res.stop_id;

      savePersistedRecord({
        key,
        threadId: tid,
        stopId: res.stop_id,
        requestedAt: Date.now(),
        status:
          res.phase === "accepted" || res.phase === "stopping"
            ? "stopping"
            : "submitting",
      });

      if (
        res.phase === "stopped" ||
        res.phase === "no_active_run" ||
        res.phase === "rejected"
      ) {
        handleTerminalReceipt(res, generation);
        return res;
      }

      if (res.phase === "confirmation_unavailable") {
        phase.value = "confirmation_unavailable";
        if (res.reason_code) {
          stopError.value =
            res.reason_code === "resource_cleanup_unconfirmed"
              ? "运行已停止，部分资源清理尚未确认"
              : res.reason_code;
        }
        return res;
      }

      phase.value = "stopping";
      startPolling(res.stop_id, generation);
      return res;
    } catch (cause) {
      if (generation !== currentEpoch || isDisposed) return null;
      const err = extractPlatformHttpError(cause);

      if (
        !err.status ||
        err.status === 504 ||
        err.status === 408 ||
        err.status >= 500
      ) {
        /* 网络超时或未知错误：保留原 key，标记待核实 */
        phase.value = "confirmation_unavailable";
        stopError.value = "停止请求结果待确认，请稍后重试";
        savePersistedRecord({
          key,
          threadId: tid,
          requestedAt: Date.now(),
          status: "unknown",
        });
      } else {
        /* 4xx 明确拒绝 */
        phase.value = "rejected";
        stopError.value = err.message || "停止请求失败";
        clearPersistedRecord(tid);
      }
      return null;
    }
  }

  async function retry(): Promise<void> {
    const tid = toValue(options.threadId);
    if (!tid) return;
    const record = loadPersistedRecord(tid);
    if (record?.stopId) {
      const generation = ++currentEpoch;
      currentStopId.value = record.stopId;
      phase.value = "stopping";
      startPolling(record.stopId, generation);
    } else {
      await stop();
    }
  }

  async function verifyLatest(manual = true): Promise<StopRequest | null> {
    const tid = toValue(options.threadId);
    if (!tid || isDisposed) return null;

    const generation = currentEpoch;
    try {
      if (
        currentStopId.value &&
        typeof options.service.getStopRequest === "function"
      ) {
        const res = await options.service.getStopRequest(
          tid,
          currentStopId.value,
        );
        if (generation !== currentEpoch || isDisposed) return null;
        latestReceipt.value = res;
        phase.value = res.phase;
        if (res.phase === "stopped" || res.phase === "no_active_run") {
          clearPersistedRecord(tid);
          clearTimer();
          options.onStopConfirmed?.(res);
        }
        return res;
      }

      if (typeof options.service.listStopRequests === "function") {
        const list = await options.service.listStopRequests(tid, { limit: 1 });
        if (generation !== currentEpoch || isDisposed) return null;
        if (list.items.length > 0) {
          const item = list.items[0];
          latestReceipt.value = item;
          currentStopId.value = item.stop_id;
          phase.value = item.phase;
          return item;
        }
      }
    } catch (cause) {
      if (manual && generation === currentEpoch && !isDisposed) {
        const err = extractPlatformHttpError(cause);
        stopError.value = err.message || "核实停止状态失败";
      }
    }
    return null;
  }

  function clearFeedback(): void {
    if (isStopping.value) return;
    phase.value = "idle";
    stopError.value = "";
  }

  function onVisibilityChange(): void {
    if (typeof document === "undefined") return;
    if (document.hidden) {
      clearTimer();
    } else {
      const stopId = currentStopId.value;
      if (
        stopId &&
        (phase.value === "stopping" || phase.value === "accepted")
      ) {
        startPolling(stopId, currentEpoch);
      }
    }
  }

  // 监听 Thread 切换，执行 Scope 与 Generation 隔离
  watch(
    () => toValue(options.threadId),
    (newThreadId) => {
      const generation = ++currentEpoch;
      clearTimer();
      stopError.value = "";
      currentStopId.value = null;
      activeKey.value = null;
      latestReceipt.value = null;

      if (!newThreadId) {
        phase.value = "idle";
        return;
      }

      // 检查是否有本地未决动作
      const pendingRecord = loadPersistedRecord(newThreadId);
      if (pendingRecord) {
        activeKey.value = pendingRecord.key;
        if (pendingRecord.stopId) {
          currentStopId.value = pendingRecord.stopId;
          phase.value = "stopping";
          startPolling(pendingRecord.stopId, generation);
        } else if (pendingRecord.status === "unknown") {
          phase.value = "confirmation_unavailable";
          stopError.value = "停止请求结果待确认，请稍后重试";
        } else {
          phase.value = "stopping";
        }
      } else {
        phase.value = "idle";
        // 静默获取最新历史报告供查阅，不激活 stopping 态
        if (typeof options.service.listStopRequests === "function") {
          void options.service
            .listStopRequests(newThreadId, { limit: 1 })
            .then((list) => {
              if (generation !== currentEpoch || isDisposed) return;
              if (list.items.length > 0) {
                latestReceipt.value = list.items[0];
                currentStopId.value = list.items[0].stop_id;
              }
            })
            .catch(() => {
              /* 忽略历史静默拉取失败 */
            });
        }
      }
    },
    { immediate: true },
  );

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onVisibilityChange);
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      isDisposed = true;
      clearTimer();
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      }
    });
  }

  return {
    phase,
    submitting,
    isStopping,
    isConfirmed,
    isConfirmationUnavailable,
    latestReceipt,
    currentStopId,
    activeKey,
    stopError,
    targetCount,
    report,
    queueCounts,
    stop,
    retry,
    verifyLatest,
    clearFeedback,
  };
}
