import { getCurrentScope, onScopeDispose, ref, type Ref } from "vue";
import {
  controlRun,
  createExpertThread,
  getExpertThreadState,
  getRunDetail,
  listExpertThreads,
  respondExpertInterrupt,
  streamExpertTurn,
  uploadExpertMaterial,
  type CaseUpsertPayload,
  type ExpertInterruptRequest,
  type ExpertThreadItem,
} from "@/services/evaluation/studio";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";

export interface ExpertMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  candidates?: CaseUpsertPayload[];
}

export interface ExpertChatHooks {
  onCasesMutated?: () => void;
  onTrialRunUpdated?: () => void;
}

function parseCandidateCases(markdown: string): CaseUpsertPayload[] {
  const blocks = [...markdown.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi)];
  const parsed: CaseUpsertPayload[] = [];
  for (const m of blocks) {
    try {
      const raw = JSON.parse(m[1].trim());
      const items = Array.isArray(raw) ? raw : [raw];
      for (const item of items) {
        if (!item || typeof item !== "object" || !item.case_key) continue;
        parsed.push({
          case_key: String(item.case_key),
          split: item.split === "holdout" ? "holdout" : "dev",
          turns: Array.isArray(item.turns)
            ? item.turns
            : item.question
              ? [{ role: "user", content: String(item.question) }]
              : [],
          simulation: item.simulation ?? null,
          expectations:
            item.expectations && typeof item.expectations === "object"
              ? item.expectations
              : item.ground_truth
                ? { expected_answer: String(item.ground_truth) }
                : {},
          metrics: Array.isArray(item.metrics) ? item.metrics : ["completion"],
        });
      }
    } catch {
      // Ignore non-JSON fenced code blocks.
    }
  }
  return parsed;
}

export function useEvalExpertChat(
  projectId: Ref<string>,
  kind: Ref<"eval_copilot" | "eval_diagnosis">,
  defaultModelId: Ref<string>,
  hooks: ExpertChatHooks = {},
) {
  const threadId = ref<string | null>(null);
  const threads = ref<ExpertThreadItem[]>([]);
  const loadingThreads = ref(false);
  const messages = ref<ExpertMessage[]>([]);
  const pendingFiles = ref<File[]>([]);
  const uploadedMaterials = ref<Array<{ fileName: string; path: string }>>([]);
  const pendingInterrupts = ref<ExpertInterruptRequest[]>([]);
  const activeTrialRunId = ref<string | null>(null);
  const trialRunStatus = ref("");
  const trialRunSummary = ref("");
  const streaming = ref(false);
  const error = ref("");
  let trialTimer: ReturnType<typeof setInterval> | null = null;

  function stopTrialPolling() {
    if (trialTimer) {
      clearInterval(trialTimer);
      trialTimer = null;
    }
  }

  if (getCurrentScope()) {
    onScopeDispose(() => stopTrialPolling());
  }

  async function refreshTrialRun() {
    if (!projectId.value || !activeTrialRunId.value) return;
    try {
      const detail = await getRunDetail(
        projectId.value,
        activeTrialRunId.value,
      );
      trialRunStatus.value = detail.run.status;
      const doneCount = detail.cases.filter((c) =>
        ["completed", "failed", "error", "cancelled"].includes(c.status),
      ).length;
      trialRunSummary.value = `${doneCount}/${detail.cases.length} 题`;
      if (
        ["completed", "failed", "error", "cancelled"].includes(
          detail.run.status,
        )
      ) {
        stopTrialPolling();
        hooks.onTrialRunUpdated?.();
      }
    } catch {
      // Ignore transient polling failures.
    }
  }

  function startTrialPolling(runId: string) {
    activeTrialRunId.value = runId;
    trialRunStatus.value = "queued";
    trialRunSummary.value = "排队中";
    stopTrialPolling();
    void refreshTrialRun();
    trialTimer = setInterval(() => {
      void refreshTrialRun();
    }, 2500);
    hooks.onTrialRunUpdated?.();
  }

  async function abortActiveTrialRun() {
    if (!projectId.value || !activeTrialRunId.value) return;
    try {
      const updated = await controlRun(
        projectId.value,
        activeTrialRunId.value,
        "cancel",
      );
      trialRunStatus.value = updated.status;
      stopTrialPolling();
      hooks.onTrialRunUpdated?.();
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "终止试跑失败。",
        "评测控制",
      );
    }
  }

  function _storageKey(refId?: string) {
    return `eval_expert_last_thread:${projectId.value}:${kind.value}:${refId || "all"}`;
  }

  function _saveLastThread(id: string | null, refId?: string) {
    try {
      const key = _storageKey(refId);
      if (id) window.localStorage.setItem(key, id);
      else window.localStorage.removeItem(key);
    } catch {
      // Ignore storage errors in restricted environments.
    }
  }

  function _readLastThread(refId?: string): string | null {
    try {
      return window.localStorage.getItem(_storageKey(refId));
    } catch {
      return null;
    }
  }

  async function loadThreads(refId?: string) {
    if (!projectId.value) return;
    loadingThreads.value = true;
    try {
      threads.value = await listExpertThreads(
        projectId.value,
        kind.value,
        refId,
      );
    } catch {
      threads.value = [];
    } finally {
      loadingThreads.value = false;
    }
  }

  async function selectThread(targetId: string, refId?: string) {
    if (!projectId.value || !targetId || streaming.value) return;
    stopTrialPolling();
    error.value = "";
    pendingFiles.value = [];
    uploadedMaterials.value = [];
    pendingInterrupts.value = [];
    activeTrialRunId.value = null;
    trialRunStatus.value = "";
    trialRunSummary.value = "";
    threadId.value = targetId;
    _saveLastThread(targetId, refId);
    try {
      const state = await getExpertThreadState(projectId.value, targetId);
      messages.value = state.messages.map((m) => ({
        ...m,
        ...(m.role === "assistant" && kind.value === "eval_copilot"
          ? { candidates: parseCandidateCases(m.content) }
          : {}),
      }));
      pendingInterrupts.value = state.interrupts;
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "加载历史会话记录失败。",
        kind.value === "eval_copilot" ? "AI 出题专家" : "AI 诊断专家",
      );
    }
  }

  async function initForContext(refId?: string) {
    await loadThreads(refId);
    if (!threadId.value) {
      const lastId = _readLastThread(refId);
      if (lastId && threads.value.some((t) => t.thread_id === lastId)) {
        await selectThread(lastId, refId);
      }
    }
  }

  function reset(refId?: string, opts?: { preserveLastThread?: boolean }) {
    stopTrialPolling();
    threadId.value = null;
    if (!opts?.preserveLastThread) {
      _saveLastThread(null, refId);
    }
    messages.value = [];
    pendingFiles.value = [];
    uploadedMaterials.value = [];
    pendingInterrupts.value = [];
    activeTrialRunId.value = null;
    trialRunStatus.value = "";
    trialRunSummary.value = "";
    error.value = "";
    streaming.value = false;
  }

  function addPendingFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    const existingNames = new Set(pendingFiles.value.map((f) => f.name));
    const merged = [...pendingFiles.value];
    for (const f of list) {
      if (!existingNames.has(f.name)) {
        merged.push(f);
        existingNames.add(f.name);
      }
    }
    pendingFiles.value = merged;
  }

  function removePendingFile(fileName: string) {
    pendingFiles.value = pendingFiles.value.filter((f) => f.name !== fileName);
  }

  function _streamCallbacks(assistantMsg: ExpertMessage) {
    return {
      onChunk: (fullText: string) => {
        assistantMsg.content = fullText;
        messages.value = [...messages.value];
      },
      onError: (msg: string) => {
        error.value = msg;
      },
      onInterrupt: (ints: ExpertInterruptRequest[]) => {
        pendingInterrupts.value = ints;
      },
      onCasesMutated: () => {
        hooks.onCasesMutated?.();
      },
      onTrialRun: (runId: string) => {
        startTrialPolling(runId);
      },
      onTrialRunUpdated: () => {
        void refreshTrialRun();
        hooks.onTrialRunUpdated?.();
      },
    };
  }

  async function _syncPendingInterrupts() {
    if (!projectId.value || !threadId.value) return;
    try {
      const state = await getExpertThreadState(projectId.value, threadId.value);
      if (state.interrupts.length > 0) {
        pendingInterrupts.value = state.interrupts;
      }
    } catch {
      // Ignore fallback sync error if thread state endpoint is temporarily unavailable.
    }
  }

  async function send(content: string, refId?: string) {
    const trimmed = content.trim();
    if (!trimmed || !projectId.value || streaming.value) return;
    if (pendingInterrupts.value.length > 0) {
      error.value =
        "当前有待处理的人工授权确认，请先点击「允许执行」或「拒绝」。";
      return;
    }

    error.value = "";
    pendingInterrupts.value = [];
    streaming.value = true;
    const filesToSend = [...pendingFiles.value];
    pendingFiles.value = [];

    const userMsg: ExpertMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      attachments: filesToSend.map((f) => f.name),
    };
    const assistantMsg: ExpertMessage = {
      id: `a-${Date.now() + 1}`,
      role: "assistant",
      content: "",
    };
    messages.value = [...messages.value, userMsg, assistantMsg];

    try {
      if (!threadId.value) {
        const autoTitle =
          trimmed.replace(/\s+/g, " ").slice(0, 32) ||
          `${kind.value} ${refId || ""}`.trim();
        const created = await createExpertThread(
          projectId.value,
          kind.value,
          autoTitle,
          refId,
        );
        threadId.value = created.thread_id;
        _saveLastThread(created.thread_id, refId);
        void loadThreads(refId);
      }

      const newlyUploaded: Array<{ fileName: string; path: string }> = [];
      for (const file of filesToSend) {
        const res = await uploadExpertMaterial(
          projectId.value,
          threadId.value,
          file,
        );
        const path = String(
          res.path || res.file_path || `/workspace/uploads/${file.name}`,
        );
        newlyUploaded.push({ fileName: file.name, path });
      }
      if (newlyUploaded.length > 0) {
        uploadedMaterials.value = [
          ...uploadedMaterials.value,
          ...newlyUploaded,
        ];
      }

      const sections: string[] = [];
      if (refId) sections.push(`[上下文关联ID: ${refId}]`);
      if (newlyUploaded.length > 0) {
        const lines = newlyUploaded.map(
          (item) => `- ${item.fileName} -> ${item.path}`,
        );
        sections.push(
          `[已挂载本轮参考资料，可调用 read_material_file 读取原文]\n${lines.join("\n")}`,
        );
      }
      sections.push(trimmed);

      const finalText = await streamExpertTurn(
        projectId.value,
        threadId.value,
        {
          graph_id: kind.value,
          content: sections.join("\n"),
          model_id: defaultModelId.value || null,
          ref_id: refId || null,
        },
        _streamCallbacks(assistantMsg),
      );
      assistantMsg.content = finalText || assistantMsg.content;
      if (kind.value === "eval_copilot" && assistantMsg.content) {
        assistantMsg.candidates = parseCandidateCases(assistantMsg.content);
      }
      if (pendingInterrupts.value.length === 0) {
        await _syncPendingInterrupts();
      }
      messages.value = [...messages.value];
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "评测专家对话执行失败。",
        kind.value === "eval_copilot" ? "AI 出题专家" : "AI 诊断专家",
      );
      await _syncPendingInterrupts();
    } finally {
      streaming.value = false;
    }
  }

  async function respondInterrupt(decision: "approve" | "reject") {
    if (
      !projectId.value ||
      !threadId.value ||
      !pendingInterrupts.value.length ||
      streaming.value
    ) {
      return;
    }
    const currentInts = [...pendingInterrupts.value];
    pendingInterrupts.value = [];
    error.value = "";
    streaming.value = true;

    const resumePayload: Record<string, unknown> = {};
    for (const item of currentInts) {
      const actions = Array.isArray(item.raw.action_requests)
        ? (item.raw.action_requests as unknown[])
        : [{}];
      resumePayload[item.id] = {
        decisions: actions.map(() => ({ type: decision })),
      };
    }

    const lastMsg = messages.value[messages.value.length - 1];
    const targetMsg: ExpertMessage =
      lastMsg && lastMsg.role === "assistant"
        ? lastMsg
        : {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: "",
          };
    if (targetMsg !== lastMsg) {
      messages.value = [...messages.value, targetMsg];
    }

    try {
      const finalText = await respondExpertInterrupt(
        projectId.value,
        threadId.value,
        {
          graph_id: kind.value,
          command: { resume: resumePayload },
        },
        _streamCallbacks(targetMsg),
      );
      targetMsg.content = finalText || targetMsg.content;
      if (kind.value === "eval_copilot" && targetMsg.content) {
        targetMsg.candidates = parseCandidateCases(targetMsg.content);
      }
      if (pendingInterrupts.value.length === 0) {
        await _syncPendingInterrupts();
      }
      messages.value = [...messages.value];
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "提交人工授权决策失败。",
        "AI 出题专家",
      );
      await _syncPendingInterrupts();
    } finally {
      streaming.value = false;
    }
  }

  return {
    threadId,
    threads,
    loadingThreads,
    messages,
    pendingFiles,
    uploadedMaterials,
    pendingInterrupts,
    activeTrialRunId,
    trialRunStatus,
    trialRunSummary,
    streaming,
    error,
    loadThreads,
    selectThread,
    initForContext,
    reset,
    addPendingFiles,
    removePendingFile,
    send,
    respondInterrupt,
    abortActiveTrialRun,
  };
}
