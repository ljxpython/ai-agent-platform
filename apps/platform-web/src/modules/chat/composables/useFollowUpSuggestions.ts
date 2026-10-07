import { computed, ref, toValue, watch, type MaybeRefOrGetter } from "vue";
import {
  loadSuggestionsConfig,
  generateThreadSuggestions,
} from "../suggestions/api";
import {
  extractRecentSuggestionMessages,
  extractPureMessageText,
} from "../suggestions/cleaner";

export interface UseFollowUpSuggestionsOptions {
  projectId: MaybeRefOrGetter<string | undefined>;
  threadId: MaybeRefOrGetter<string | undefined>;
  agentId?: MaybeRefOrGetter<string | undefined>;
  modelId?: MaybeRefOrGetter<string | undefined>;
  messages: MaybeRefOrGetter<readonly unknown[]>;
  isRunning: MaybeRefOrGetter<boolean>;
  hasPendingInterrupts?: MaybeRefOrGetter<boolean>;
  visible?: MaybeRefOrGetter<boolean>;
  disabled?: MaybeRefOrGetter<boolean>;
  turnState?: MaybeRefOrGetter<string | undefined>;
  runStatus?: MaybeRefOrGetter<string | undefined>;
}

function quickHash(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) + hash + str.charCodeAt(i);
    hash |= 0;
  }
  return (hash >>> 0).toString(36);
}

export function useFollowUpSuggestions(options: UseFollowUpSuggestionsOptions) {
  const suggestions = ref<string[]>([]);
  const loading = ref(false);
  const dismissed = ref(false);

  let activeController: AbortController | null = null;
  let lastRequestedKey: string | null = null;
  let stoppedByUser = false;
  let pendingCatchUp = false;

  const currentProjectId = computed(() => toValue(options.projectId) || "");
  const currentThreadId = computed(() => toValue(options.threadId) || "");
  const currentAgentId = computed(() => toValue(options.agentId) || "");
  const currentModelId = computed(() => toValue(options.modelId) || "");
  const isRunningVal = computed(() => Boolean(toValue(options.isRunning)));
  const hasInterruptsVal = computed(() =>
    Boolean(toValue(options.hasPendingInterrupts)),
  );
  const isVisibleVal = computed(() => toValue(options.visible) !== false);
  const isDisabledVal = computed(() => Boolean(toValue(options.disabled)));

  function clear(): void {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
    suggestions.value = [];
    loading.value = false;
    dismissed.value = false;
  }

  function dismiss(): void {
    dismissed.value = true;
  }

  function markStoppedByUser(): void {
    stoppedByUser = true;
    clear();
  }

  async function triggerForCompletedTurn(): Promise<void> {
    if (
      isDisabledVal.value ||
      isRunningVal.value ||
      hasInterruptsVal.value ||
      !currentThreadId.value ||
      !currentProjectId.value
    ) {
      return;
    }

    if (stoppedByUser) {
      stoppedByUser = false;
      return;
    }

    const currentTurnState = toValue(options.turnState);
    if (
      currentTurnState &&
      [
        "timeout",
        "error",
        "stopping",
        "stop_unconfirmed",
        "stopped",
        "awaiting_review",
      ].includes(currentTurnState)
    ) {
      return;
    }

    const currentRunStatus = toValue(options.runStatus);
    if (currentRunStatus && currentRunStatus !== "success") {
      return;
    }

    const msgs = toValue(options.messages);
    if (!Array.isArray(msgs) || msgs.length === 0) {
      return;
    }

    // 找到最后一条消息
    const lastMsg = msgs[msgs.length - 1] as
      | Record<string, unknown>
      | undefined;
    if (!lastMsg) {
      return;
    }

    const rawType =
      (typeof lastMsg._getType === "function"
        ? lastMsg._getType()
        : undefined) ??
      lastMsg.type ??
      lastMsg.role;

    // 只有最后一条是 assistant/ai 时才触发
    if (rawType !== "ai" && rawType !== "assistant") {
      return;
    }

    const lastText =
      extractPureMessageText(lastMsg.content) ||
      (typeof lastMsg.text === "string" ? lastMsg.text : "");
    if (!lastText.trim()) {
      return;
    }

    const msgId = String(lastMsg.id || "");
    const contentKey = quickHash(lastText);
    const requestKey = `${currentThreadId.value}:${msgId}:${contentKey}`;

    if (requestKey === lastRequestedKey) {
      return;
    }

    // 如果处于后台 KeepAlive 隐藏态，标记待补偿并暂缓发请求
    if (!isVisibleVal.value) {
      pendingCatchUp = true;
      return;
    }

    pendingCatchUp = false;
    lastRequestedKey = requestKey;

    if (activeController) {
      activeController.abort();
      activeController = null;
    }

    const controller = new AbortController();
    activeController = controller;
    loading.value = true;
    dismissed.value = false;
    suggestions.value = [];

    try {
      // 1. 检查配置是否开启
      const config = await loadSuggestionsConfig(
        currentProjectId.value,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (!config.enabled) {
        loading.value = false;
        return;
      }

      // 2. 清洗提取最近至多 6 条有效纯文本
      const cleanedMessages = extractRecentSuggestionMessages(msgs);
      if (controller.signal.aborted || cleanedMessages.length === 0) {
        loading.value = false;
        return;
      }

      // 3. 调用建议生成接口
      const result = await generateThreadSuggestions(
        currentProjectId.value,
        currentThreadId.value,
        {
          messages: cleanedMessages,
          n: config.max_suggestions,
          model_id: currentModelId.value || undefined,
        },
        controller.signal,
      );

      if (controller.signal.aborted) return;

      // 4. 竞态校验：仅在 key 匹配时写回
      if (lastRequestedKey === requestKey) {
        suggestions.value = result;
      }
    } catch {
      // best-effort 契约：静默吞吐
      if (!controller.signal.aborted) {
        suggestions.value = [];
      }
    } finally {
      if (activeController === controller) {
        activeController = null;
        loading.value = false;
      }
    }
  }

  // 监听运行状态：由 running -> not running 时尝试触发
  watch(
    isRunningVal,
    (nowRunning, wasRunning) => {
      if (wasRunning && !nowRunning) {
        void triggerForCompletedTurn();
      } else if (nowRunning) {
        // 新一轮启动时清除旧建议
        clear();
      }
    },
    { flush: "post" },
  );

  // 监听 KeepAlive 可见性：切回前台时若有未完成的建议，执行补偿
  watch(
    isVisibleVal,
    (nowVisible) => {
      if (nowVisible && pendingCatchUp && !isRunningVal.value) {
        void triggerForCompletedTurn();
      }
    },
    { flush: "post" },
  );

  // 监听 threadId 或 agentId 变更：立即打断并重置
  watch([currentThreadId, currentAgentId], () => {
    lastRequestedKey = null;
    pendingCatchUp = false;
    stoppedByUser = false;
    clear();
  });

  return {
    suggestions: computed(() => (dismissed.value ? [] : suggestions.value)),
    loading: computed(() => loading.value),
    dismissed: computed(() => dismissed.value),
    clear,
    dismiss,
    trigger: triggerForCompletedTurn,
    markStoppedByUser,
  };
}
