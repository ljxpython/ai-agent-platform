<script setup lang="ts">
import { ref, computed, watch, onMounted, onDeactivated, onScopeDispose } from "vue";
import { useRouter } from "vue-router";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { extractPlatformHttpError } from "@/utils/http-error";
import {
  readMemory,
  saveMemoryFact,
  deleteMemoryFact,
  clearMemory,
  acceptMemoryCandidate,
  rejectMemoryCandidate,
  updateMemorySettings,
  restoreMemoryFacts,
  type FactCategory,
  type FactInput,
  type FactSourceKind,
  type MemoryFact,
  type MemoryView,
} from "@/services/dear-agent/memory.service";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import ConfirmDialog from "@/components/base/ConfirmDialog.vue";

const router = useRouter();
const { activeProject, activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();

// 记忆视图与竞态控制状态
const memoryView = ref<MemoryView | null>(null);
const loading = ref(false);
const actionLoading = ref(false);
const isExporting = ref(false);
const snapshotStale = ref(false);
const accessDenied = ref(false);

const errorMsg = ref("");
const errorRequestId = ref("");
const conflictWarning = ref("");
const conflictRefreshFailed = ref(false);
const successMsg = ref("");

const searchQuery = ref("");
const activeTab = ref<"facts" | "candidates">("facts");

// 项目切换 generation 与请求中止控制
const scopeGeneration = ref(0);
let activeGetAbortController: AbortController | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let pollCount = 0;
const MAX_POLL_ATTEMPTS = 70; // 3s * 70 = 210s 上限

// 新增 / 编辑事实弹窗状态
const isEditModalOpen = ref(false);
const editingFact = ref<MemoryFact | null>(null);
const formText = ref("");
const formCategory = ref<FactCategory>("preference");
const formExpiresAt = ref("");
const initialExpiresDate = ref("");

// 删除单条事实确认弹窗状态
const factToDelete = ref<MemoryFact | null>(null);

// 清空记忆确认弹窗状态
const isClearConfirmOpen = ref(false);

// 候选替换已有事实弹窗状态
const isReplaceModalOpen = ref(false);
const replacingCandidate = ref<MemoryFact | null>(null);
const selectedReplaceFactId = ref("");

// 追加导入弹窗状态
const isRestoreModalOpen = ref(false);
const restoreJsonText = ref("");
const restoreFileName = ref("");
const restoreFileBytesError = ref("");
const fileInputRef = ref<HTMLInputElement | null>(null);

// 权限与状态派生属性
const hasLocalWritePerm = computed(() =>
  Boolean(activeProjectId.value && can("project.runtime.execute", activeProjectId.value)),
);

const isDisabledStatus = computed(() => memoryView.value?.status === "disabled");
const isReadyStatus = computed(() => memoryView.value?.status === "ready");

const canRead = computed(() => {
  if (!activeProjectId.value || accessDenied.value || isDisabledStatus.value) return false;
  return memoryView.value?.capabilities?.can_read ?? true;
});

const canWrite = computed(() => {
  if (!activeProjectId.value || accessDenied.value || snapshotStale.value) return false;
  if (!isReadyStatus.value || !memoryView.value?.document) return false;
  return hasLocalWritePerm.value && Boolean(memoryView.value.capabilities?.can_write);
});

const factCharLimit = computed(() => memoryView.value?.limits?.fact_text_chars ?? 1000);
const factCountLimit = computed(() => memoryView.value?.limits?.facts ?? 100);
const restoreItemLimit = computed(() => memoryView.value?.limits?.restore_items ?? 100);
const requestBytesLimit = computed(() => memoryView.value?.limits?.request_bytes ?? 1500000);

// Unicode 码点长度计数（避免 Emoji UTF-16 length 算作 2）
const formCharCount = computed(() => Array.from(formText.value.trim()).length);

// 服务端全量计数（不随本地搜索改变）
const totalFactsCount = computed(
  () => memoryView.value?.counts?.facts ?? memoryView.value?.document?.facts.length ?? 0,
);
const totalCandidatesCount = computed(
  () => memoryView.value?.counts?.candidates ?? memoryView.value?.document?.candidates.length ?? 0,
);

// 本地统一搜索过滤（同时过滤 facts 与 candidates）
const normalizedSearch = computed(() => searchQuery.value.trim().toLowerCase());

const filteredFacts = computed(() => {
  const facts = memoryView.value?.document?.facts ?? [];
  const q = normalizedSearch.value;
  if (!q) return facts;
  return facts.filter(
    (f) =>
      f.text.toLowerCase().includes(q) ||
      f.category.toLowerCase().includes(q) ||
      (f.quote && f.quote.toLowerCase().includes(q)),
  );
});

const filteredCandidates = computed(() => {
  const candidates = memoryView.value?.document?.candidates ?? [];
  const q = normalizedSearch.value;
  if (!q) return candidates;
  return candidates.filter(
    (c) =>
      c.text.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      (c.quote && c.quote.toLowerCase().includes(q)),
  );
});

const canClearMemory = computed(() => {
  if (!canWrite.value || !memoryView.value?.document) return false;
  const doc = memoryView.value.document;
  return doc.facts.length > 0 || doc.candidates.length > 0 || doc.automatic_candidates;
});

// 本地时区日期工具函数
function getTodayLocalDateString(): string {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toLocalDateInputString(isoStr: string | null | undefined): string {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return "";
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localDateToEndOfDayIso(dateStr: string): string {
  const parts = dateStr.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
    return new Date(dateStr).toISOString();
  }
  const [year, month, day] = parts;
  return new Date(year, month - 1, day, 23, 59, 59, 999).toISOString();
}

function normalizeFingerprint(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

// 导入预览与严格前置校验
interface ImportPreviewResult {
  validItems: FactInput[];
  duplicateCount: number;
  errors: string[];
  capacityExceeded: boolean;
}

const importPreview = computed<ImportPreviewResult>(() => {
  const raw = restoreJsonText.value.trim();
  if (!raw) {
    return { validItems: [], duplicateCount: 0, errors: [], capacityExceeded: false };
  }
  if (restoreFileBytesError.value) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: [restoreFileBytesError.value],
      capacityExceeded: false,
    };
  }

  const byteLen = new TextEncoder().encode(raw).length;
  if (byteLen > requestBytesLimit.value) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: [`导入内容超过大小上限（${requestBytesLimit.value} 字节）`],
      capacityExceeded: false,
    };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e: any) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: [`JSON 解析失败：${e?.message || "语法错误"}`],
      capacityExceeded: false,
    };
  }

  if (!Array.isArray(parsed)) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: ["导入内容顶层必须是 JSON 数组格式"],
      capacityExceeded: false,
    };
  }

  if (parsed.length === 0) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: ["导入数组不能为空（至少包含 1 条事实）"],
      capacityExceeded: false,
    };
  }

  if (parsed.length > restoreItemLimit.value) {
    return {
      validItems: [],
      duplicateCount: 0,
      errors: [`单次最多追加导入 ${restoreItemLimit.value} 条记忆事实（当前 ${parsed.length} 条）`],
      capacityExceeded: false,
    };
  }

  const existingFingerprints = new Set(
    (memoryView.value?.document?.facts ?? []).map((f) => normalizeFingerprint(f.text)),
  );
  const seenInBatch = new Set<string>();
  const validItems: FactInput[] = [];
  const errors: string[] = [];
  let duplicateCount = 0;
  let newUniqueCount = 0;

  parsed.forEach((item, idx) => {
    const rowNum = idx + 1;
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      errors.push(`第 ${rowNum} 条：必须是 JSON 对象`);
      return;
    }
    const rec = item as Record<string, unknown>;
    if (typeof rec.text !== "string") {
      errors.push(`第 ${rowNum} 条：text 必须是字符串类型`);
      return;
    }
    const trimmedText = rec.text.trim();
    const charLen = Array.from(trimmedText).length;
    if (charLen === 0) {
      errors.push(`第 ${rowNum} 条：text 不能为空白`);
      return;
    }
    if (charLen > factCharLimit.value) {
      errors.push(`第 ${rowNum} 条：text 长度（${charLen}）超过 ${factCharLimit.value} 字符上限`);
      return;
    }

    let category: FactCategory = "preference";
    if (rec.category !== undefined && rec.category !== null) {
      if (rec.category !== "preference" && rec.category !== "fact") {
        errors.push(`第 ${rowNum} 条：非法分类 "${String(rec.category)}"（仅支持 preference 或 fact）`);
        return;
      }
      category = rec.category;
    }

    let expiresAt: string | null = null;
    if (rec.expires_at !== undefined && rec.expires_at !== null && rec.expires_at !== "") {
      if (typeof rec.expires_at !== "string") {
        errors.push(`第 ${rowNum} 条：expires_at 必须是带时区的 ISO 字符串或 null`);
        return;
      }
      const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(rec.expires_at.trim());
      const parsedTime = Date.parse(rec.expires_at);
      if (!hasTimezone || Number.isNaN(parsedTime)) {
        errors.push(`第 ${rowNum} 条：expires_at 必须是带时区的合法 ISO-8601 时间`);
        return;
      }
      if (parsedTime <= Date.now()) {
        errors.push(`第 ${rowNum} 条：expires_at 已过期，不能导入过期事实`);
        return;
      }
      expiresAt = rec.expires_at.trim();
    }

    const fp = normalizeFingerprint(trimmedText);
    if (existingFingerprints.has(fp) || seenInBatch.has(fp)) {
      duplicateCount += 1;
    } else {
      seenInBatch.add(fp);
      newUniqueCount += 1;
    }

    validItems.push({
      text: trimmedText,
      category,
      expires_at: expiresAt,
    });
  });

  const currentFactCount = memoryView.value?.document?.facts.length ?? 0;
  const capacityExceeded = currentFactCount + newUniqueCount > factCountLimit.value;
  if (capacityExceeded) {
    errors.push(
      `导入后预计有效事实数（${currentFactCount + newUniqueCount}）超出容量上限 ${factCountLimit.value}，请先清理现有事实`,
    );
  }

  return { validItems, duplicateCount, errors, capacityExceeded };
});

// 轮询控制函数
function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  pollCount = 0;
}

function syncPollingState(view: MemoryView | null) {
  if (view?.status === "ready" && view.extraction?.status === "running") {
    if (pollTimer === null) {
      pollCount = 0;
      pollTimer = setInterval(() => {
        pollCount += 1;
        if (pollCount > MAX_POLL_ATTEMPTS) {
          stopPolling();
          return;
        }
        void silentFetchMemory();
      }, 3000);
    }
  } else {
    stopPolling();
  }
}

// 静默后台轮询（不闪屏、不冲掉弹窗草稿和 409 冲突提示）
async function silentFetchMemory() {
  const projId = activeProjectId.value;
  if (!projId || actionLoading.value || loading.value) return;
  const gen = scopeGeneration.value;

  try {
    const view = await readMemory(projId);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value || actionLoading.value) {
      return;
    }
    memoryView.value = view;
    snapshotStale.value = false;
    syncPollingState(view);
  } catch {
    // 静默轮询遇到瞬态网络波动不覆盖主界面错误与草稿
  }
}

// 显式加载记忆视图
async function fetchMemory(options: { preserveConflict?: boolean } = {}) {
  const projId = activeProjectId.value;
  if (!projId) {
    memoryView.value = null;
    return;
  }

  if (activeGetAbortController) {
    activeGetAbortController.abort();
  }
  const controller = new AbortController();
  activeGetAbortController = controller;
  const gen = scopeGeneration.value;

  loading.value = true;
  errorMsg.value = "";
  errorRequestId.value = "";
  if (!options.preserveConflict) {
    conflictWarning.value = "";
    conflictRefreshFailed.value = false;
  }

  try {
    const view = await readMemory(projId, controller.signal);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) {
      return;
    }
    memoryView.value = view;
    snapshotStale.value = false;
    accessDenied.value = false;
    if (options.preserveConflict) {
      conflictRefreshFailed.value = false;
    }
    syncPollingState(view);
  } catch (err: any) {
    if (err?.name === "CanceledError" || err?.name === "AbortError" || controller.signal.aborted) {
      return;
    }
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) {
      return;
    }
    const parsed = extractPlatformHttpError(err, "读取个人记忆数据失败");
    errorRequestId.value = parsed.requestId || "";

    if (parsed.status === 403 || parsed.code === "dear_memory_scope_denied" || parsed.code === "forbidden") {
      accessDenied.value = true;
      memoryView.value = null;
      closeAllModals();
      errorMsg.value = "无权访问当前项目的个人记忆数据";
    } else {
      if (memoryView.value) {
        snapshotStale.value = true;
      }
      if (options.preserveConflict) {
        conflictRefreshFailed.value = true;
      }
      if (parsed.code === "memory_storage_unavailable") {
        errorMsg.value = "记忆存储服务暂不可用（503），请稍后点击重试";
      } else {
        errorMsg.value = parsed.message || "读取个人记忆数据失败";
      }
    }
  } finally {
    if (gen === scopeGeneration.value && activeGetAbortController === controller) {
      loading.value = false;
      activeGetAbortController = null;
    }
  }
}

function closeAllModals() {
  isEditModalOpen.value = false;
  editingFact.value = null;
  factToDelete.value = null;
  isClearConfirmOpen.value = false;
  isReplaceModalOpen.value = false;
  replacingCandidate.value = null;
  isRestoreModalOpen.value = false;
}

// 统一写操作错误处理
function handleActionError(err: unknown) {
  const parsed = extractPlatformHttpError(err, "操作结果尚未确认，请刷新核对");
  errorRequestId.value = parsed.requestId || "";

  if (parsed.status === 403 || parsed.code === "dear_memory_scope_denied" || parsed.code === "forbidden") {
    accessDenied.value = true;
    memoryView.value = null;
    closeAllModals();
    errorMsg.value = "您已失去当前项目的记忆写入权限（403）";
    return;
  }

  if (parsed.code === "memory_revision_conflict") {
    conflictWarning.value =
      "⚠️ 数据已被其他操作更新（版本冲突）。已为您拉取最新记忆版本，您的编辑草稿仍保留在表单中，请核对后再次点击提交。";
    void fetchMemory({ preserveConflict: true });
    return;
  }

  if (parsed.code === "dear_governance_disabled") {
    errorMsg.value = "当前环境已关闭长期记忆能力，正在同步最新状态";
    void fetchMemory();
    return;
  }

  if (parsed.code === "memory_capacity_exceeded") {
    errorMsg.value = `记忆库已达容量上限（单项目最多 ${factCountLimit.value} 条事实 / ${factCountLimit.value} 条候选），请先删除旧条目`;
    return;
  }

  if (parsed.code === "memory_duplicate_fact") {
    errorMsg.value = "已存在相同内容的生效事实，请直接编辑已有条目";
    return;
  }

  if (parsed.code === "memory_expired") {
    errorMsg.value = "该候选记忆已过期，无法采纳，已为您刷新列表";
    void fetchMemory();
    return;
  }

  if (parsed.code === "memory_not_found" || parsed.status === 404) {
    errorMsg.value = "目标事实或候选已不存在，正在刷新列表（您的未提交草稿已保留）";
    void fetchMemory();
    return;
  }

  if (parsed.code === "memory_maintenance_required") {
    errorMsg.value = "自动提取元数据配额已满，请先清理待审核候选或执行清空重置";
    void fetchMemory();
    return;
  }

  if (parsed.code === "validation_failed" && parsed.details?.length) {
    const locStr = parsed.details
      .map((d) => (d.loc ? d.loc.join(".") : "字段"))
      .join(", ");
    errorMsg.value = `输入参数校验未通过（位置：${locStr}）`;
    return;
  }

  if (
    parsed.status === null ||
    parsed.status === 502 ||
    parsed.status === 503 ||
    parsed.status === 504 ||
    parsed.code === "memory_storage_unavailable" ||
    parsed.code === "langgraph_upstream_timeout"
  ) {
    errorMsg.value = "操作结果尚未确认，请刷新核对";
    return;
  }

  errorMsg.value = parsed.message || "操作失败";
}

function applyMutationResponse(view: MemoryView, msg: string) {
  memoryView.value = view;
  snapshotStale.value = false;
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  syncPollingState(view);
  showSuccess(msg);
}

function showSuccess(msg: string) {
  successMsg.value = msg;
  setTimeout(() => {
    if (successMsg.value === msg) {
      successMsg.value = "";
    }
  }, 4000);
}

// 自动候选开关切换
async function toggleAutomaticCandidates() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (!projId || !doc || !canWrite.value || actionLoading.value) return;

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const nextVal = !doc.automatic_candidates;
    const view = await updateMemorySettings(projId, doc.revision, nextVal);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    applyMutationResponse(view, nextVal ? "自动候选推断已开启" : "自动候选推断已关闭");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 打开新增事实弹窗
function openAddFactModal() {
  editingFact.value = null;
  formText.value = "";
  formCategory.value = "preference";
  formExpiresAt.value = "";
  initialExpiresDate.value = "";
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  isEditModalOpen.value = true;
}

// 打开编辑事实弹窗
function openEditFactModal(fact: MemoryFact) {
  editingFact.value = fact;
  formText.value = fact.text;
  formCategory.value = fact.category;
  const localDate = toLocalDateInputString(fact.expires_at);
  formExpiresAt.value = localDate;
  initialExpiresDate.value = localDate;
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  isEditModalOpen.value = true;
}

function closeEditModal() {
  isEditModalOpen.value = false;
  editingFact.value = null;
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
}

// 提交事实保存（新增或编辑）
async function handleSaveFact() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (!projId || !doc || !canWrite.value || actionLoading.value || conflictRefreshFailed.value) return;

  const text = formText.value.trim();
  if (!text) {
    errorMsg.value = "记忆事实内容不能为空";
    return;
  }
  if (formCharCount.value > factCharLimit.value) {
    errorMsg.value = `记忆内容不能超过 ${factCharLimit.value} 个 Unicode 字符`;
    return;
  }

  let resolvedExpiresAt: string | null = null;
  if (editingFact.value && formExpiresAt.value === initialExpiresDate.value) {
    // 编辑已有到期时间且用户未修改时，原样保留原 ISO 字符串
    resolvedExpiresAt = editingFact.value.expires_at ?? null;
  } else if (formExpiresAt.value) {
    resolvedExpiresAt = localDateToEndOfDayIso(formExpiresAt.value);
    if (Date.parse(resolvedExpiresAt) <= Date.now()) {
      errorMsg.value = "到期日期必须晚于当前时间";
      return;
    }
  }

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await saveMemoryFact(
      projId,
      doc.revision,
      {
        text,
        category: formCategory.value,
        expires_at: resolvedExpiresAt,
      },
      editingFact.value?.id,
    );
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    isEditModalOpen.value = false;
    const wasEditing = Boolean(editingFact.value);
    editingFact.value = null;
    applyMutationResponse(view, wasEditing ? "事实更新成功" : "新增事实成功");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 删除事实（打开 ConfirmDialog）
function requestDeleteFact(fact: MemoryFact) {
  factToDelete.value = fact;
}

async function confirmDeleteFact() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  const target = factToDelete.value;
  if (!projId || !doc || !target || !canWrite.value || actionLoading.value) return;

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await deleteMemoryFact(projId, doc.revision, target.id);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    factToDelete.value = null;
    applyMutationResponse(view, "事实删除成功");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    factToDelete.value = null;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 清空记忆
async function handleClearMemory() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (!projId || !doc || !canWrite.value || actionLoading.value) return;

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await clearMemory(projId, doc.revision);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    isClearConfirmOpen.value = false;
    const removedCount = view.mutation?.removed ?? 0;
    applyMutationResponse(
      view,
      `已清空当前项目的个人记忆（移除 ${removedCount} 条生效事实）并关闭自动候选`,
    );
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    isClearConfirmOpen.value = false;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 直接采纳候选
async function handleAcceptCandidate(factId: string) {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (!projId || !doc || !canWrite.value || actionLoading.value) return;

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await acceptMemoryCandidate(projId, doc.revision, factId);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    applyMutationResponse(view, "候选记忆已采纳为正式事实");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 打开“替换已有事实”弹窗
function openReplaceFactModal(candidate: MemoryFact) {
  const facts = memoryView.value?.document?.facts ?? [];
  if (!facts.length) return;
  replacingCandidate.value = candidate;
  selectedReplaceFactId.value = facts[0].id;
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  isReplaceModalOpen.value = true;
}

// 确认采纳候选并替换所选已有事实
async function handleConfirmReplaceFact() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  const cand = replacingCandidate.value;
  if (
    !projId ||
    !doc ||
    !cand ||
    !selectedReplaceFactId.value ||
    !canWrite.value ||
    actionLoading.value ||
    conflictRefreshFailed.value
  ) {
    return;
  }

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await acceptMemoryCandidate(
      projId,
      doc.revision,
      cand.id,
      selectedReplaceFactId.value,
    );
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    isReplaceModalOpen.value = false;
    replacingCandidate.value = null;
    applyMutationResponse(view, "已采纳候选并替换原事实");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 拒绝候选
async function handleRejectCandidate(factId: string) {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (!projId || !doc || !canWrite.value || actionLoading.value) return;

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await rejectMemoryCandidate(projId, doc.revision, factId);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    applyMutationResponse(view, "已拒绝并移除该候选推断");
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// Fresh GET 导出完整有效事实 JSON
async function handleExportMemory() {
  const projId = activeProjectId.value;
  if (!projId || !canRead.value || isExporting.value) return;

  const gen = scopeGeneration.value;
  isExporting.value = true;
  errorMsg.value = "";
  try {
    const freshView = await readMemory(projId);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    memoryView.value = freshView;
    snapshotStale.value = false;

    const factsToExport = (freshView.document?.facts ?? []).map((f) => ({
      text: f.text,
      category: f.category,
      expires_at: f.expires_at ?? null,
    }));

    const dateTag = getTodayLocalDateString().replace(/-/g, "");
    const fileName = `dear-memory-${dateTag}.json`;
    const blob = new Blob([JSON.stringify(factsToExport, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showSuccess(`已导出 ${factsToExport.length} 条有效事实`);
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      isExporting.value = false;
    }
  }
}

// 打开追加导入弹窗
function openRestoreModal() {
  restoreJsonText.value = "";
  restoreFileName.value = "";
  restoreFileBytesError.value = "";
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  isRestoreModalOpen.value = true;
}

// 选择本地 JSON 文件导入
async function handleImportFileSelection(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  restoreFileName.value = file.name;
  if (file.size > requestBytesLimit.value) {
    restoreFileBytesError.value = `文件 "${file.name}" 大小（${file.size} 字节）超出上限 ${requestBytesLimit.value} 字节`;
    restoreJsonText.value = "";
    return;
  }
  restoreFileBytesError.value = "";
  try {
    restoreJsonText.value = await file.text();
  } catch {
    restoreFileBytesError.value = `读取文件 "${file.name}" 失败`;
  }
}

// 提交批量追加恢复事实
async function handleRestoreFacts() {
  const projId = activeProjectId.value;
  const doc = memoryView.value?.document;
  if (
    !projId ||
    !doc ||
    !canWrite.value ||
    actionLoading.value ||
    conflictRefreshFailed.value
  ) {
    return;
  }

  const preview = importPreview.value;
  if (preview.errors.length > 0 || preview.validItems.length === 0) {
    return;
  }

  const gen = scopeGeneration.value;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const view = await restoreMemoryFacts(projId, doc.revision, preview.validItems);
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    isRestoreModalOpen.value = false;
    restoreJsonText.value = "";
    restoreFileName.value = "";
    const added = view.mutation?.added ?? 0;
    const skipped = view.mutation?.skipped ?? 0;
    applyMutationResponse(view, `追加导入完成：新增 ${added} 条事实，跳过 ${skipped} 条重复项`);
  } catch (err) {
    if (gen !== scopeGeneration.value || projId !== activeProjectId.value) return;
    handleActionError(err);
  } finally {
    if (gen === scopeGeneration.value) {
      actionLoading.value = false;
    }
  }
}

// 命名路由跳转到来源 Dear 会话
function openSourceThread(threadId: string | null | undefined) {
  if (!threadId || !activeProjectId.value) return;
  void router.push({
    name: "workspace-dear-agent",
    params: {
      projectId: activeProjectId.value,
      threadId,
    },
  });
}

// 辅助文案映射
function formatSourceKind(kind: FactSourceKind | undefined): string {
  switch (kind) {
    case "management":
      return "手动记录";
    case "user_message":
      return "对话提取";
    case "tool":
      return "会话工具记录";
    case "legacy":
    default:
      return "历史记录";
  }
}

function formatPauseReason(reason: string | null | undefined): string {
  switch (reason) {
    case "candidate_limit":
      return "待审核候选数量已达 100 条上限，请先采纳、拒绝或清理现有候选以恢复自动提取。";
    case "source_limit":
      return "已记录的提取来源历史达到维护上限，人工管理事实不受影响；如需重置配额可执行清空记忆。";
    case "tombstone_limit":
      return "已删除/拒绝指纹记录达到维护上限，人工管理事实不受影响；如需重置配额可执行清空记忆。";
    default:
      return `自动候选因维护原因（${reason}）暂时挂起，人工增删改仍可正常使用。`;
  }
}

// 监听项目切换，立即增加 generation、中止在途请求并拉取新项目数据
watch(activeProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId === oldProjectId) return;
  scopeGeneration.value += 1;
  stopPolling();
  if (activeGetAbortController) {
    activeGetAbortController.abort();
    activeGetAbortController = null;
  }
  loading.value = false;
  actionLoading.value = false;
  memoryView.value = null;
  snapshotStale.value = false;
  accessDenied.value = false;
  searchQuery.value = "";
  errorMsg.value = "";
  errorRequestId.value = "";
  conflictWarning.value = "";
  conflictRefreshFailed.value = false;
  successMsg.value = "";
  closeAllModals();

  if (newProjectId) {
    void fetchMemory();
  }
});

onMounted(() => {
  if (activeProjectId.value) {
    void fetchMemory();
  }
});

onDeactivated(() => {
  stopPolling();
  if (activeGetAbortController) {
    activeGetAbortController.abort();
    activeGetAbortController = null;
  }
});

onScopeDispose(() => {
  stopPolling();
  if (activeGetAbortController) {
    activeGetAbortController.abort();
    activeGetAbortController = null;
  }
});
</script>

<template>
  <div class="h-full overflow-y-auto p-6 md:p-8">
    <div class="mx-auto max-w-6xl space-y-6">
      <!-- 页面头部 -->
      <div class="flex flex-col gap-4 border-b border-zinc-200/80 pb-5 md:flex-row md:items-center md:justify-between dark:border-zinc-800">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary-50 text-primary-600 shadow-sm dark:bg-primary-950/50 dark:text-primary-400">
              <BaseIcon
                name="shield"
                size="sm"
              />
            </span>
            <h1 class="text-xl font-bold text-zinc-900 dark:text-zinc-100">
              我的记忆（长期记忆与偏好治理）
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            仅用于你在项目「{{ activeProject?.name || activeProjectId || "未选择项目" }}」中的 Dear Agent 会话（同项目跨会话共享，不跨用户、不跨项目）
          </p>
        </div>

        <!-- 顶部全局操作按钮组 -->
        <div class="flex flex-wrap items-center gap-2.5">
          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loading"
            :disabled="!activeProjectId"
            title="刷新记忆视图"
            @click="fetchMemory()"
          >
            <template #icon>
              <BaseIcon
                name="refresh"
                size="xs"
              />
            </template>
            刷新
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="sm"
            :loading="isExporting"
            :disabled="!canRead || !isReadyStatus"
            title="导出当前全部有效记忆事实为 JSON"
            @click="handleExportMemory"
          >
            <template #icon>
              <BaseIcon
                name="download"
                size="xs"
              />
            </template>
            导出 JSON
          </BaseButton>

          <BaseButton
            variant="secondary"
            size="sm"
            :disabled="!canWrite"
            title="从 JSON 文件或文本批量追加导入记忆事实"
            @click="openRestoreModal"
          >
            <template #icon>
              <BaseIcon
                name="folder"
                size="xs"
              />
            </template>
            追加导入
          </BaseButton>

          <BaseButton
            variant="primary"
            size="sm"
            :disabled="!canWrite"
            :title="!canWrite ? '当前只读或不可写' : '手动新增一条长期记忆事实'"
            @click="openAddFactModal"
          >
            <template #icon>
              <BaseIcon
                name="plus"
                size="xs"
              />
            </template>
            新增事实
          </BaseButton>
        </div>
      </div>

      <!-- 无当前项目提示 -->
      <div
        v-if="!activeProjectId"
        class="rounded-2xl border border-dashed border-zinc-300 bg-white/60 p-12 text-center dark:border-zinc-700 dark:bg-zinc-900/50"
      >
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          请先在工作区选择归属项目后再管理个人记忆。
        </p>
      </div>

      <template v-else>
        <!-- 409 版本冲突持久提示横幅 -->
        <div
          v-if="conflictWarning"
          class="flex items-start justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs font-medium text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
        >
          <div class="flex items-start gap-2">
            <BaseIcon
              name="alert"
              size="xs"
              class="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400"
            />
            <div>
              <p>{{ conflictWarning }}</p>
              <p
                v-if="conflictRefreshFailed"
                class="mt-1 text-rose-600 dark:text-rose-400"
              >
                最新数据同步失败，请先点击右侧「重试同步」成功后再提交保存。
              </p>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <BaseButton
              v-if="conflictRefreshFailed"
              variant="secondary"
              size="xs"
              @click="fetchMemory({ preserveConflict: true })"
            >
              重试同步
            </BaseButton>
            <button
              type="button"
              class="text-amber-600 hover:text-amber-800"
              @click="conflictWarning = ''"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- 过期快照警告 -->
        <div
          v-if="snapshotStale"
          class="flex items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50/90 px-4 py-3 text-xs font-medium text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
        >
          <span>⚠️ 最近一次刷新失败，当前展示为历史快照，写入操作已暂时锁定。</span>
          <BaseButton
            variant="secondary"
            size="xs"
            @click="fetchMemory()"
          >
            重试刷新
          </BaseButton>
        </div>

        <!-- 只读权限提示横幅 -->
        <div
          v-if="isReadyStatus && !canWrite && !snapshotStale"
          class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
        >
          <BaseIcon
            name="shield"
            size="xs"
            class="text-amber-600 dark:text-amber-400"
          />
          <span>
            当前项目处于只读模式（缺少 project.runtime.execute 权限或服务端只读限制），记忆新增、编辑、删除与清空操作已锁定，您仍可浏览和导出。
          </span>
        </div>

        <!-- 成功提示 -->
        <div
          v-if="successMsg"
          class="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
        >
          <BaseIcon
            name="check"
            size="xs"
            class="text-emerald-600 dark:text-emerald-400"
          />
          <span>{{ successMsg }}</span>
        </div>

        <!-- 错误警告（含 request_id 与重试按钮） -->
        <div
          v-if="errorMsg"
          class="flex items-center justify-between gap-3 rounded-xl bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
        >
          <div class="flex items-center gap-2">
            <BaseIcon
              name="alert"
              size="xs"
              class="shrink-0 text-rose-600 dark:text-rose-400"
            />
            <span>
              {{ errorMsg }}
              <span
                v-if="errorRequestId"
                class="ml-1.5 font-mono text-[11px] opacity-80"
              >
                (request_id: {{ errorRequestId }})
              </span>
            </span>
          </div>
          <div class="flex items-center gap-2">
            <BaseButton
              variant="secondary"
              size="xs"
              @click="fetchMemory()"
            >
              重试
            </BaseButton>
            <button
              type="button"
              class="text-rose-500 hover:text-rose-700"
              @click="errorMsg = ''"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- 初次加载骨架态（不显示“0 条已生效”） -->
        <div
          v-if="loading && !memoryView"
          class="rounded-2xl border border-zinc-200/80 bg-white p-12 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div class="text-sm font-medium text-zinc-600 dark:text-zinc-300">
            正在加载当前项目的个人记忆视图...
          </div>
        </div>

        <!-- status = disabled 独立状态视图 -->
        <div
          v-else-if="isDisabledStatus"
          class="rounded-2xl border border-dashed border-zinc-300 bg-white/70 p-12 text-center dark:border-zinc-700 dark:bg-zinc-900/50"
        >
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            <BaseIcon
              name="shield"
              size="md"
            />
          </div>
          <h3 class="mt-4 text-base font-semibold text-zinc-900 dark:text-zinc-100">
            当前环境未启用长期记忆治理
          </h3>
          <p class="mx-auto mt-2 max-w-md text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
            服务端当前未开启个人长期记忆存储能力（RUNTIME_DEAR_GOVERNANCE_ENABLED）。请联系平台管理员在运行环境中启用后使用。
          </p>
        </div>

        <!-- 核心治理面板（status = ready） -->
        <div
          v-else-if="isReadyStatus && memoryView?.document"
          class="space-y-6"
        >
          <!-- 配额维护暂停提示（pause_reason 非空时） -->
          <div
            v-if="memoryView.extraction?.pause_reason"
            class="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50/80 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
          >
            <BaseIcon
              name="alert"
              size="xs"
              class="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400"
            />
            <div>
              <span class="font-semibold">自动候选提取已因配额维护暂停：</span>
              <span>{{ formatPauseReason(memoryView.extraction.pause_reason) }}</span>
            </div>
          </div>

          <!-- 提取状态提示条（running / no_candidates / failed / interrupted） -->
          <div
            v-if="memoryView.extraction && memoryView.extraction.status !== 'never'"
            class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-200/80 bg-zinc-50/80 px-4 py-2.5 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-300"
          >
            <div class="flex items-center gap-2">
              <span
                v-if="memoryView.extraction.status === 'running'"
                class="inline-block h-2 w-2 animate-pulse rounded-full bg-primary-500"
              />
              <span
                v-if="memoryView.extraction.status === 'running'"
                class="font-medium text-primary-700 dark:text-primary-300"
              >
                正在整理候选记忆（已有事实仍可正常管理，后台每 3 秒静默同步）…
              </span>
              <span v-else-if="memoryView.extraction.status === 'no_candidates'">
                最近一次对话整理完成：本次没有值得长期保存的候选内容。
              </span>
              <span v-else-if="memoryView.extraction.status === 'succeeded'">
                最近一次对话整理完成：生成了 {{ memoryView.extraction.candidate_count }} 条候选记忆。
              </span>
              <span
                v-else-if="memoryView.extraction.status === 'failed' || memoryView.extraction.status === 'interrupted'"
                class="text-amber-700 dark:text-amber-400"
              >
                最近一次候选整理未完成（状态：{{ memoryView.extraction.status }}
                <template v-if="memoryView.extraction.error_code">
                  / {{ memoryView.extraction.error_code }}
                </template>
                ），现有已生效事实不受影响。
              </span>
              <span v-else>
                最近一次提取状态：{{ memoryView.extraction.status }}
              </span>
            </div>

            <div class="flex items-center gap-3">
              <button
                v-if="memoryView.extraction.source_thread_id"
                type="button"
                class="font-medium text-primary-600 hover:underline dark:text-primary-400"
                @click="openSourceThread(memoryView.extraction.source_thread_id)"
              >
                查看最近来源会话
              </button>
              <button
                type="button"
                class="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                @click="fetchMemory()"
              >
                手动刷新
              </button>
            </div>
          </div>

          <!-- 统计与自动候选控制栏 -->
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div class="text-xs font-medium text-zinc-500">
                生效事实总数
              </div>
              <div class="mt-1.5 flex items-baseline gap-2">
                <span class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  {{ totalFactsCount }}
                </span>
                <span class="text-xs text-zinc-400">/ {{ factCountLimit }} 上限</span>
              </div>
            </div>

            <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div class="text-xs font-medium text-zinc-500">
                待审核候选
              </div>
              <div class="mt-1.5 flex items-baseline gap-2">
                <span class="text-2xl font-bold text-amber-600 dark:text-amber-400">
                  {{ totalCandidatesCount }}
                </span>
                <span class="text-xs text-zinc-400">条待人工确认</span>
              </div>
            </div>

            <div class="flex items-center justify-between rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div>
                <div class="flex items-center gap-1 text-xs font-medium text-zinc-900 dark:text-zinc-100">
                  <span>自动推断候选</span>
                  <span
                    class="cursor-help text-zinc-400"
                    title="开启后，模型在私有会话执行时可推断偏好并放入候选库；必须人工采纳后方可生效。共享会话始终禁用。"
                  >
                    ℹ️
                  </span>
                </div>
                <div class="mt-0.5 text-[11px] text-zinc-500">
                  {{ memoryView.document.automatic_candidates ? "已开启模型候选推断" : "仅接受人工录入" }}
                </div>
              </div>
              <button
                type="button"
                role="switch"
                :aria-checked="memoryView.document.automatic_candidates"
                aria-label="自动推断候选开关"
                :disabled="actionLoading || !canWrite"
                :class="[
                  'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
                  memoryView.document.automatic_candidates ? 'bg-primary-600' : 'bg-zinc-200 dark:bg-zinc-700',
                ]"
                @click="toggleAutomaticCandidates"
              >
                <span
                  :class="[
                    'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                    memoryView.document.automatic_candidates ? 'translate-x-5' : 'translate-x-0',
                  ]"
                />
              </button>
            </div>
          </div>

          <!-- 标签页与工具栏 -->
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-1 rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800/80">
              <button
                type="button"
                :class="[
                  'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
                  activeTab === 'facts'
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                    : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200',
                ]"
                @click="activeTab = 'facts'"
              >
                <BaseIcon
                  name="folder"
                  size="xs"
                />
                <span>已生效事实</span>
                <span class="rounded-full bg-zinc-200 px-1.5 py-0.5 text-[10px] dark:bg-zinc-700">
                  {{ totalFactsCount }}
                </span>
              </button>

              <button
                type="button"
                :class="[
                  'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
                  activeTab === 'candidates'
                    ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                    : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200',
                ]"
                @click="activeTab = 'candidates'"
              >
                <BaseIcon
                  name="sparkle"
                  size="xs"
                />
                <span>待确认候选</span>
                <span
                  class="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400"
                >
                  {{ totalCandidatesCount }}
                </span>
              </button>
            </div>

            <!-- 右侧统一检索与清空操作 -->
            <div class="flex items-center gap-2">
              <div class="relative w-48 sm:w-64">
                <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-zinc-400">
                  <BaseIcon
                    name="search"
                    size="xs"
                  />
                </span>
                <input
                  v-model="searchQuery"
                  type="text"
                  placeholder="搜索事实、候选或原文..."
                  class="w-full rounded-lg border border-zinc-200 bg-white py-1.5 pl-8 pr-7 text-xs text-zinc-900 placeholder-zinc-400 shadow-sm focus:border-primary-500 focus:outline-none dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
                >
                <button
                  v-if="searchQuery"
                  type="button"
                  title="清空搜索"
                  class="absolute inset-y-0 right-0 flex items-center pr-2 text-xs text-zinc-400 hover:text-zinc-600"
                  @click="searchQuery = ''"
                >
                  ✕
                </button>
              </div>

              <BaseButton
                variant="danger"
                size="sm"
                :disabled="!canClearMemory"
                title="清空当前项目中的个人全部事实与候选"
                @click="isClearConfirmOpen = true"
              >
                <template #icon>
                  <BaseIcon
                    name="trash"
                    size="xs"
                  />
                </template>
                清空记忆
              </BaseButton>
            </div>
          </div>

          <!-- Tab 1: 已生效事实列表 -->
          <div
            v-if="activeTab === 'facts'"
            class="space-y-3"
          >
            <div
              v-if="filteredFacts.length === 0"
              class="rounded-xl border border-dashed border-zinc-200 p-8 text-center dark:border-zinc-800"
            >
              <div class="text-xs text-zinc-500">
                {{
                  normalizedSearch
                    ? "没有匹配的记忆事实"
                    : "尚无已生效的记忆事实，您可以点击右上角「新增事实」直接记录，或开启自动推断候选"
                }}
              </div>
            </div>

            <div
              v-for="fact in filteredFacts"
              v-else
              :key="fact.id"
              class="group flex flex-col justify-between gap-3 rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm transition hover:border-zinc-300 sm:flex-row sm:items-start dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
            >
              <div class="space-y-1.5">
                <div class="flex flex-wrap items-center gap-2">
                  <span
                    :class="[
                      'rounded-full px-2 py-0.5 text-[10px] font-medium',
                      fact.category === 'preference'
                        ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400'
                        : 'bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400',
                    ]"
                  >
                    {{ fact.category === "preference" ? "偏好规则" : "知识事实" }}
                  </span>

                  <span class="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800">
                    来源: {{ formatSourceKind(fact.source_kind) }}
                  </span>

                  <button
                    v-if="fact.source_thread_id"
                    type="button"
                    class="text-[10px] font-medium text-primary-600 hover:underline dark:text-primary-400"
                    @click="openSourceThread(fact.source_thread_id)"
                  >
                    查看来源会话
                  </button>

                  <span
                    v-if="fact.expires_at"
                    class="text-[10px] text-amber-600 dark:text-amber-400"
                  >
                    到期: {{ toLocalDateInputString(fact.expires_at) }}
                  </span>
                </div>

                <p class="text-sm font-medium leading-relaxed text-zinc-900 dark:text-zinc-100">
                  {{ fact.text }}
                </p>

                <div
                  v-if="fact.quote"
                  class="rounded-lg bg-zinc-50 px-2.5 py-1.5 text-[11px] text-zinc-500 dark:bg-zinc-800/60 dark:text-zinc-400"
                >
                  原文引用：“{{ fact.quote }}”
                </div>

                <div class="text-[11px] text-zinc-400">
                  创建于 {{ new Date(fact.created_at).toLocaleString() }} · 更新于 {{ new Date(fact.updated_at).toLocaleString() }}
                </div>
              </div>

              <!-- 操作按钮 -->
              <div
                v-if="canWrite"
                class="flex items-center gap-1 self-end sm:self-center"
              >
                <button
                  type="button"
                  class="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                  title="编辑事实"
                  @click="openEditFactModal(fact)"
                >
                  <BaseIcon
                    name="pencil"
                    size="xs"
                  />
                </button>
                <button
                  type="button"
                  class="rounded-lg p-1.5 text-zinc-500 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40 dark:hover:text-rose-400"
                  title="删除事实"
                  @click="requestDeleteFact(fact)"
                >
                  <BaseIcon
                    name="trash"
                    size="xs"
                  />
                </button>
              </div>
            </div>
          </div>

          <!-- Tab 2: 待确认候选列表 -->
          <div
            v-else
            class="space-y-3"
          >
            <div class="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
              <div class="flex items-center gap-1.5 font-medium">
                <BaseIcon
                  name="shield"
                  size="xs"
                />
                <span>候选人工审核机制</span>
              </div>
              <p class="mt-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-400">
                候选记忆由模型根据您本人的对话消息提取生成，<strong>尚未进入对话注入</strong>。您可核对下方原文证据后选择「直接采纳」、「替换已有事实」或「拒绝丢弃」。
              </p>
            </div>

            <div
              v-if="filteredCandidates.length === 0"
              class="rounded-xl border border-dashed border-zinc-200 p-8 text-center dark:border-zinc-800"
            >
              <div class="text-xs text-zinc-500">
                {{ normalizedSearch ? "没有匹配的待确认候选" : "暂无待确认的候选记忆" }}
              </div>
            </div>

            <div
              v-for="cand in filteredCandidates"
              v-else
              :key="cand.id"
              class="flex flex-col justify-between gap-4 rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm sm:flex-row sm:items-start dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
                    待确认候选
                  </span>
                  <span
                    :class="[
                      'rounded-full px-2 py-0.5 text-[10px] font-medium',
                      cand.category === 'preference'
                        ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400'
                        : 'bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400',
                    ]"
                  >
                    {{ cand.category === "preference" ? "偏好规则" : "知识事实" }}
                  </span>
                  <span class="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800">
                    来源: {{ formatSourceKind(cand.source_kind) }}
                  </span>
                  <button
                    v-if="cand.source_thread_id"
                    type="button"
                    class="text-[10px] font-medium text-primary-600 hover:underline dark:text-primary-400"
                    @click="openSourceThread(cand.source_thread_id)"
                  >
                    查看来源会话
                  </button>
                  <span
                    v-if="cand.expires_at"
                    class="text-[10px] text-amber-600 dark:text-amber-400"
                  >
                    到期: {{ toLocalDateInputString(cand.expires_at) }}
                  </span>
                </div>

                <p class="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {{ cand.text }}
                </p>

                <!-- 原文引用证据（缺失时明确说明，不生成假证据） -->
                <div class="rounded-lg border border-zinc-200/60 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-800/50 dark:text-zinc-300">
                  <span class="font-medium text-zinc-500 dark:text-zinc-400">原文依据：</span>
                  <span v-if="cand.quote">“{{ cand.quote }}”</span>
                  <span
                    v-else
                    class="italic text-zinc-400"
                  >历史记录缺少原文</span>
                </div>

                <div class="text-[11px] text-zinc-400">
                  生成于 {{ new Date(cand.created_at).toLocaleString() }}
                </div>
              </div>

              <!-- 候选三动作：拒绝 / 替换已有事实 / 直接采纳 -->
              <div class="flex flex-wrap items-center gap-2 self-end sm: shrink-0 sm:self-center">
                <BaseButton
                  variant="secondary"
                  size="xs"
                  :disabled="actionLoading || !canWrite"
                  @click="handleRejectCandidate(cand.id)"
                >
                  拒绝丢弃
                </BaseButton>
                <BaseButton
                  v-if="(memoryView.document.facts.length ?? 0) > 0"
                  variant="secondary"
                  size="xs"
                  :disabled="actionLoading || !canWrite"
                  @click="openReplaceFactModal(cand)"
                >
                  替换已有事实…
                </BaseButton>
                <BaseButton
                  variant="primary"
                  size="xs"
                  :disabled="actionLoading || !canWrite"
                  @click="handleAcceptCandidate(cand.id)"
                >
                  采纳为事实
                </BaseButton>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 新增 / 编辑事实弹窗 (BaseDialog) -->
    <BaseDialog
      :show="isEditModalOpen"
      :title="editingFact ? '编辑记忆事实' : '新增记忆事实'"
      width="normal"
      @close="closeEditModal"
    >
      <div class="space-y-4">
        <div
          v-if="conflictWarning"
          class="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
        >
          {{ conflictWarning }}
        </div>

        <div>
          <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">分类</label>
          <div class="mt-1.5 flex gap-4">
            <label class="flex items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
              <input
                v-model="formCategory"
                type="radio"
                value="preference"
              >
              <span>偏好规则 (Preference)</span>
            </label>
            <label class="flex items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
              <input
                v-model="formCategory"
                type="radio"
                value="fact"
              >
              <span>知识事实 (Fact)</span>
            </label>
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
            记忆内容 (≤ {{ factCharLimit }} Unicode 字符)
          </label>
          <textarea
            v-model="formText"
            rows="4"
            class="mt-1.5 w-full rounded-xl border border-zinc-300 bg-white p-3 text-xs text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            placeholder="例如：生成代码时必须附带详细单测用例并遵守 KISS 原则..."
          />
          <div
            :class="[
              'mt-1 text-right text-[10px]',
              formCharCount > factCharLimit ? 'font-semibold text-rose-600' : 'text-zinc-400',
            ]"
          >
            {{ formCharCount }} / {{ factCharLimit }}
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
            到期日期 (可选，按本地时区当日 23:59:59 到期)
          </label>
          <input
            v-model="formExpiresAt"
            type="date"
            :min="getTodayLocalDateString()"
            class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          >
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <BaseButton
            variant="secondary"
            size="sm"
            @click="closeEditModal"
          >
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="actionLoading"
            :disabled="actionLoading || conflictRefreshFailed || formCharCount > factCharLimit"
            @click="handleSaveFact"
          >
            保存提交
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <!-- 采纳候选并替换已有事实弹窗 (BaseDialog) -->
    <BaseDialog
      :show="isReplaceModalOpen"
      title="采纳候选并替换已有事实"
      width="normal"
      @close="isReplaceModalOpen = false"
    >
      <div
        v-if="replacingCandidate"
        class="space-y-4"
      >
        <div class="rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-xs text-zinc-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-zinc-200">
          <div class="font-semibold text-amber-800 dark:text-amber-300">
            待采纳的新候选：
          </div>
          <p class="mt-1">
            {{ replacingCandidate.text }}
          </p>
        </div>

        <div>
          <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
            选择要被替换移除的现有事实：
          </label>
          <select
            v-model="selectedReplaceFactId"
            class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          >
            <option
              v-for="fact in memoryView?.document?.facts ?? []"
              :key="fact.id"
              :value="fact.id"
            >
              [{{ fact.category === "preference" ? "偏好" : "事实" }}] {{ fact.text.slice(0, 80) }}
            </option>
          </select>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <BaseButton
            variant="secondary"
            size="sm"
            @click="isReplaceModalOpen = false"
          >
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="actionLoading"
            :disabled="actionLoading || !selectedReplaceFactId"
            @click="handleConfirmReplaceFact"
          >
            确认替换并采纳
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <!-- 批量追加导入弹窗 (文件选择 + 文本预览双支持) -->
    <BaseDialog
      :show="isRestoreModalOpen"
      title="批量追加导入记忆事实 (JSON)"
      width="wide"
      @close="isRestoreModalOpen = false"
    >
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            支持选择便携导出的 <code>.json</code> 文件或直接粘贴 JSON 数组（单次 1..{{ restoreItemLimit }} 条）。<strong>追加导入，不会覆盖现有事实。</strong>
          </p>
          <div>
            <input
              ref="fileInputRef"
              type="file"
              accept=".json,application/json"
              class="hidden"
              @change="handleImportFileSelection"
            >
            <BaseButton
              variant="secondary"
              size="xs"
              @click="fileInputRef?.click()"
            >
              选择 JSON 文件…
            </BaseButton>
          </div>
        </div>

        <div
          v-if="restoreFileName"
          class="text-xs font-medium text-primary-600 dark:text-primary-400"
        >
          已加载文件：{{ restoreFileName }}
        </div>

        <textarea
          v-model="restoreJsonText"
          rows="6"
          class="w-full rounded-xl border border-zinc-300 bg-white p-3 font-mono text-[11px] text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          placeholder="[&#10;  {&quot;text&quot;: &quot;偏好简洁的代码实现&quot;, &quot;category&quot;: &quot;preference&quot;, &quot;expires_at&quot;: null}&#10;]"
        />

        <!-- 导入实时校验预览面板 -->
        <div
          v-if="restoreJsonText.trim() || restoreFileBytesError"
          class="rounded-xl border border-zinc-200 bg-zinc-50 p-3.5 text-xs space-y-2 dark:border-zinc-800 dark:bg-zinc-800/60"
        >
          <div class="flex flex-wrap items-center gap-4 font-medium">
            <span class="text-emerald-700 dark:text-emerald-400">
              有效条目：{{ importPreview.validItems.length }} 条
            </span>
            <span class="text-amber-700 dark:text-amber-400">
              预计重复跳过：{{ importPreview.duplicateCount }} 条
            </span>
            <span :class="importPreview.errors.length ? 'text-rose-600 dark:text-rose-400' : 'text-zinc-500'">
              校验错误：{{ importPreview.errors.length }} 项
            </span>
          </div>

          <ul
            v-if="importPreview.errors.length"
            class="max-h-32 overflow-y-auto list-disc pl-5 space-y-1 text-rose-600 dark:text-rose-400"
          >
            <li
              v-for="(errText, idx) in importPreview.errors"
              :key="idx"
            >
              {{ errText }}
            </li>
          </ul>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <BaseButton
            variant="secondary"
            size="sm"
            @click="isRestoreModalOpen = false"
          >
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="actionLoading"
            :disabled="
              actionLoading ||
                conflictRefreshFailed ||
                importPreview.validItems.length === 0 ||
                importPreview.errors.length > 0
            "
            @click="handleRestoreFacts"
          >
            确认追加导入
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <!-- 删除单条事实标准确认弹窗 (ConfirmDialog) -->
    <ConfirmDialog
      :show="Boolean(factToDelete)"
      title="删除记忆事实确认"
      :message="factToDelete ? `确定要删除这条记忆事实吗？\n「${factToDelete.text.slice(0, 120)}」` : ''"
      confirm-text="确认删除"
      cancel-text="取消"
      danger
      @confirm="confirmDeleteFact"
      @cancel="factToDelete = null"
    />

    <!-- 清空个人记忆标准确认弹窗 (ConfirmDialog) -->
    <ConfirmDialog
      :show="isClearConfirmOpen"
      title="清空个人记忆确认"
      message="将删除当前用户在当前项目中的全部事实和候选，同时关闭自动候选；历史聊天不会被删除。此操作不可逆，确定要继续吗？"
      confirm-text="确认彻底清空"
      cancel-text="取消"
      danger
      @confirm="handleClearMemory"
      @cancel="isClearConfirmOpen = false"
    />
  </div>
</template>
