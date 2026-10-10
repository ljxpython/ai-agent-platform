import {
  getCurrentScope,
  onScopeDispose,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from "vue";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import { extractPlatformHttpError } from "@/utils/http-error";
import { extractPureMessageText } from "../suggestions/cleaner";

export interface UseAutomaticThreadTitleOptions {
  projectId: MaybeRefOrGetter<string | undefined>;
  threadId: MaybeRefOrGetter<string | undefined>;
  runStatus: MaybeRefOrGetter<string | undefined>;
  runId: MaybeRefOrGetter<string | undefined>;
  accessThread: MaybeRefOrGetter<ChatThread | undefined>;
  messages: MaybeRefOrGetter<readonly unknown[]>;
  visible?: MaybeRefOrGetter<boolean | undefined>;
  canWrite?: MaybeRefOrGetter<boolean>;
  isBusy?: MaybeRefOrGetter<boolean>;
  turnState?: MaybeRefOrGetter<string | undefined>;
  onTitleUpdated: (title: string) => void;
}

export function useAutomaticThreadTitle(
  options: UseAutomaticThreadTitleOptions,
) {
  let activeController: AbortController | null = null;
  let lastRequestedKey: string | null = null;
  let pendingCatchUp = false;

  async function checkAndTrigger(): Promise<void> {
    const projectId = toValue(options.projectId);
    const threadId = toValue(options.threadId);
    const runId = toValue(options.runId);
    const runStatus = toValue(options.runStatus);
    const isBusy = Boolean(toValue(options.isBusy));
    const canWrite = toValue(options.canWrite) !== false;
    const isVisible = toValue(options.visible) !== false;
    const turnState = toValue(options.turnState);
    const thread = toValue(options.accessThread);

    const metadata = thread?.metadata as Record<string, unknown> | undefined;

    if (!projectId || !threadId || !runId || !canWrite || isBusy) return;
    if (runStatus !== "success") return;
    if (
      turnState &&
      [
        "timeout",
        "error",
        "stopping",
        "stop_unconfirmed",
        "stopped",
        "awaiting_review",
      ].includes(turnState)
    ) {
      return;
    }

    // 门禁1：只有服务端显式标记为 pending 状态（seed 未消费且具备资格）时才允许自动升级
    if (metadata?.auto_title_pending !== true) return;

    // 门禁2：校验最终助手消息正文已就绪且无未决工具调用
    const msgs = toValue(options.messages);
    if (!Array.isArray(msgs) || msgs.length === 0) return;
    const lastMsg = msgs[msgs.length - 1] as
      | Record<string, unknown>
      | undefined;
    if (!lastMsg) return;

    const rawType =
      (typeof lastMsg._getType === "function"
        ? lastMsg._getType()
        : undefined) ??
      lastMsg.type ??
      lastMsg.role;
    if (rawType !== "ai" && rawType !== "assistant") return;

    const toolCalls = Array.isArray(lastMsg.tool_calls)
      ? lastMsg.tool_calls
      : [];
    if (toolCalls.length > 0) return;

    const text =
      extractPureMessageText(lastMsg.content) ||
      (typeof lastMsg.text === "string" ? lastMsg.text : "");
    if (!text.trim()) return;

    const requestKey = `${projectId}:${threadId}:${runId}`;
    if (requestKey === lastRequestedKey) return;

    if (!isVisible) {
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
    const service = createSessionService(
      createLanggraphAuthorizedFetch(),
      projectId,
    );

    try {
      const res = await service.summarizeTitle(
        threadId,
        { mode: "auto", run_id: runId },
        controller.signal,
      );
      if (controller.signal.aborted) return;

      if (res.outcome === "applied" && res.title?.trim()) {
        options.onTitleUpdated(res.title.trim());
      } else if (
        res.outcome === "skipped" &&
        res.reason === "conflict" &&
        res.title?.trim()
      ) {
        // CAS 冲突时后端返回的是用户当前已保存的新标题，同步更新避免显示旧规则标题
        options.onTitleUpdated(res.title.trim());
      }
    } catch (cause) {
      if (controller.signal.aborted) return;
      const { status, code } = extractPlatformHttpError(cause);

      // 503 title_write_unconfirmed 或网络未知结果时，执行单次有界 GET 对账
      if (
        status === 503 ||
        code === "title_write_unconfirmed" ||
        status === 0
      ) {
        try {
          const latest = await service.get(threadId);
          const latestTitle = (
            latest.metadata as Record<string, unknown> | undefined
          )?.title;
          if (typeof latestTitle === "string" && latestTitle.trim()) {
            options.onTitleUpdated(latestTitle.trim());
          }
        } catch {
          // 静默保底
        }
      }
    } finally {
      if (activeController === controller) {
        activeController = null;
      }
    }
  }

  watch(
    [
      () => toValue(options.runStatus),
      () => toValue(options.runId),
      () => toValue(options.isBusy),
      () => toValue(options.messages)?.length,
    ],
    () => {
      void checkAndTrigger();
    },
    { flush: "post", immediate: true },
  );

  watch(
    () => toValue(options.visible) !== false,
    (nowVisible) => {
      if (nowVisible && pendingCatchUp) {
        void checkAndTrigger();
      }
    },
    { flush: "post" },
  );

  watch(
    [() => toValue(options.threadId), () => toValue(options.projectId)],
    () => {
      lastRequestedKey = null;
      pendingCatchUp = false;
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
    },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
    });
  }

  return { trigger: checkAndTrigger };
}
