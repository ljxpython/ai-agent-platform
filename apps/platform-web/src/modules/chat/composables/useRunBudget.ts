import {
  computed,
  getCurrentScope,
  onScopeDispose,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from "vue";
import { useChannel, type AnyStream } from "@langchain/vue";
import type { BudgetNotice, BudgetSafetyError } from "../budget/types";
import {
  deriveBudgetViewModel,
  safeExtractBudgetNotice,
  safeExtractBudgetSafetyError,
  type BudgetViewModel,
} from "../budget/view-model";

export interface UseRunBudgetOptions {
  runId: MaybeRefOrGetter<string | null>;
  namespace?: MaybeRefOrGetter<readonly string[] | undefined>;
  nativeError?: MaybeRefOrGetter<unknown>;
  nativeStatus?: MaybeRefOrGetter<string | undefined>;
  lastMessage?: MaybeRefOrGetter<unknown>;
  isRunning?: MaybeRefOrGetter<boolean>;
}

export function isNamespaceMatch(
  eventNamespace: unknown,
  targetNamespace: readonly string[] | undefined,
): boolean {
  if (!targetNamespace || targetNamespace.length === 0) {
    // Root listener: accept empty or non-array root namespace events
    return !Array.isArray(eventNamespace) || eventNamespace.length === 0;
  }
  if (!Array.isArray(eventNamespace)) return false;
  if (eventNamespace.length !== targetNamespace.length) return false;
  return eventNamespace.every((seg, i) => seg === targetNamespace[i]);
}

interface CachedNoticeEntry {
  notice: BudgetNotice;
  namespace?: readonly string[];
}

/**
 * Bounded LRU Cache (max 200 items) to prevent memory growth across serial runs
 */
export class BoundedNoticeCache {
  private map = new Map<string, CachedNoticeEntry>();
  private readonly max: number;

  constructor(max = 200) {
    this.max = max;
  }

  set(id: string, entry: CachedNoticeEntry) {
    if (this.map.has(id)) {
      this.map.delete(id);
    } else if (this.map.size >= this.max) {
      const oldestKey = this.map.keys().next().value;
      if (oldestKey !== undefined) {
        this.map.delete(oldestKey);
      }
    }
    this.map.set(id, entry);
  }

  entries(): CachedNoticeEntry[] {
    return Array.from(this.map.values());
  }

  clear() {
    this.map.clear();
  }

  get size(): number {
    return this.map.size;
  }
}

export function useRunBudget(
  stream: AnyStream | undefined | null,
  options: UseRunBudgetOptions,
) {
  // Subscribe to raw custom stream channel without static target to ensure full reactive namespace routing
  const rawEvents = stream
    ? useChannel(stream, ["custom"])
    : shallowRef<any[]>([]);

  const cache = new BoundedNoticeCache(200);
  const cacheVersion = shallowRef(0);
  let lastEventsRef: unknown = null;
  let processedCount = 0;

  // Incremental processing: parse only newly arrived events into LRU cache to avoid O(N) Zod overhead
  const processNewEvents = () => {
    const events = rawEvents.value;
    if (!events || events.length === 0) {
      if (processedCount > 0) {
        cache.clear();
        processedCount = 0;
        lastEventsRef = events;
        cacheVersion.value++;
      }
      return;
    }

    // Reset if events buffer was truncated or swapped to a different array reference
    if (events !== lastEventsRef || events.length < processedCount) {
      cache.clear();
      processedCount = 0;
      lastEventsRef = events;
    }

    let hasNew = false;
    while (processedCount < events.length) {
      const ev = events[processedCount];
      processedCount++;

      const notice = safeExtractBudgetNotice(ev);
      if (notice) {
        const evNs = (ev as any)?.params?.namespace;
        cache.set(notice.notice_id, {
          notice,
          namespace: Array.isArray(evNs) ? evNs : undefined,
        });
        hasNew = true;
      }
    }

    if (hasNew) {
      cacheVersion.value++;
    }
  };

  // Run on initial evaluation and whenever rawEvents changes
  watch(
    () => rawEvents.value,
    () => {
      processNewEvents();
    },
    { immediate: true, deep: false },
  );

  // Derive matching notices synchronously for the active runId and namespace
  const currentNotices = computed<BudgetNotice[]>(() => {
    // Read cacheVersion to track updates
    void cacheVersion.value;
    // Also process in case computed evaluated before watch trigger
    processNewEvents();

    const activeRunId = toValue(options.runId);
    const currentNs = toValue(options.namespace);
    if (!activeRunId) {
      return [];
    }

    const matching: BudgetNotice[] = [];
    const entries = cache.entries();

    for (const entry of entries) {
      if (
        entry.notice.run_id === activeRunId &&
        isNamespaceMatch(entry.namespace, currentNs)
      ) {
        matching.push(entry.notice);
      }
    }
    return matching;
  });

  // Check end marker from last AIMessage in history
  const endMarkerNotice = computed<BudgetNotice | null>(() => {
    const activeRunId = toValue(options.runId);
    const status = toValue(options.nativeStatus);

    // If currently running or pending, do NOT fall back to historical end marker to prevent flickering
    if (status === "running" || status === "pending") {
      return null;
    }

    const msg = toValue(options.lastMessage);
    if (!msg || typeof msg !== "object") return null;

    const kwargs = (msg as any).additional_kwargs;
    if (kwargs?.runtime_budget_notice) {
      const notice = safeExtractBudgetNotice(kwargs.runtime_budget_notice);
      if (notice && (!activeRunId || notice.run_id === activeRunId)) {
        return notice;
      }
    }
    return null;
  });

  // Most authoritative active notice for the current run
  const activeNotice = computed<BudgetNotice | null>(() => {
    // 1. Reached in live notices takes highest priority
    const reached = currentNotices.value.find(
      (n) => n.code === "model_call_limit_reached",
    );
    if (reached) return reached;

    // 2. End marker from AIMessage
    if (endMarkerNotice.value) {
      return endMarkerNotice.value;
    }

    // 3. Approaching or wrapup notice (take latest)
    if (currentNotices.value.length > 0) {
      return currentNotices.value[currentNotices.value.length - 1];
    }

    return null;
  });

  const safetyError = computed<BudgetSafetyError | null>(() => {
    const err = toValue(options.nativeError);
    const fromNative = safeExtractBudgetSafetyError(err);
    if (fromNative) return fromNative;

    // Double safeguard: directly inspect underlying stream error if present
    if (stream && "error" in (stream as any) && (stream as any).error?.value) {
      const fromStream = safeExtractBudgetSafetyError(
        (stream as any).error.value,
      );
      if (fromStream) return fromStream;
    }
    return null;
  });

  const budget = computed<BudgetViewModel | null>(() => {
    const status = toValue(options.nativeStatus);
    const isRunning = Boolean(
      toValue(options.isRunning) ||
      status === "running" ||
      status === "pending",
    );
    const effectiveSafetyError = isRunning ? null : safetyError.value;
    return deriveBudgetViewModel(
      activeNotice.value,
      effectiveSafetyError,
      status,
    );
  });

  const isThreadExhausted = computed<boolean>(() => {
    return (
      budget.value?.scope === "thread" &&
      budget.value?.actionType === "new_thread"
    );
  });

  if (getCurrentScope()) {
    onScopeDispose(() => {
      cache.clear();
    });
  }

  return {
    rawEvents,
    activeNotice,
    safetyError,
    budget,
    isThreadExhausted,
  };
}
