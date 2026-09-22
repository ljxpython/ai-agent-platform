<script setup lang="ts">
import { ref, computed, watch, onMounted, onScopeDispose } from "vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useDearGovernanceContext } from "../composables/useDearGovernanceContext";
import {
  readMemory,
  saveMemoryFact,
  deleteMemoryFact,
  clearMemory,
  acceptMemoryCandidate,
  rejectMemoryCandidate,
  updateMemorySettings,
  restoreMemoryFacts,
  type FactItem,
  type MemoryDocument,
} from "@/services/dear-agent/memory.service";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";

const {
  activeProject,
  activeProjectId,
  threads,
  activeThreadId,
  hasThreads,
  loading: contextLoading,
  isCreatingThread,
  switchThread,
  createInitialThread,
} = useDearGovernanceContext();

const { can } = useAuthorization();
const canWrite = computed(() => can("project.runtime.execute", activeProjectId.value));

// 记忆数据与状态
const memoryDoc = ref<MemoryDocument | null>(null);
const loading = ref(false);
const actionLoading = ref(false);
const errorMsg = ref("");
const successMsg = ref("");
const searchQuery = ref("");
const activeTab = ref<"facts" | "candidates">("facts");

// 弹窗状态
const isEditModalOpen = ref(false);
const editingFact = ref<FactItem | null>(null);
const formText = ref("");
const formCategory = ref<"preference" | "fact">("preference");
const formExpiresAt = ref("");

const isRestoreModalOpen = ref(false);
const restoreJsonText = ref("");
const restoreParseError = ref("");

const isClearConfirmOpen = ref(false);

// 过滤后的 facts
const filteredFacts = computed(() => {
  if (!memoryDoc.value) return [];
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return memoryDoc.value.facts;
  return memoryDoc.value.facts.filter((f) =>
    f.text.toLowerCase().includes(q) || f.category.toLowerCase().includes(q)
  );
});

// 加载记忆文档
async function fetchMemory() {
  if (!activeProjectId.value || !activeThreadId.value) {
    memoryDoc.value = null;
    return;
  }
  loading.value = true;
  errorMsg.value = "";
  try {
    const doc = await readMemory(
      activeProjectId.value,
      activeThreadId.value,
      searchQuery.value
    );
    memoryDoc.value = doc;
  } catch (err: any) {
    const code = err.response?.data?.code || err.code;
    if (code === "dear_governance_disabled") {
      errorMsg.value = "治理存储未开启（RUNTIME_DEAR_GOVERNANCE_ENABLED=1）";
    } else if (code === "dear_governance_scope_denied") {
      errorMsg.value = "无权访问此会话的治理数据";
    } else {
      errorMsg.value = err.message || "读取记忆数据失败";
    }
  } finally {
    loading.value = false;
  }
}

// 自动候选开关切换
async function toggleAutomaticCandidates() {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const nextVal = !memoryDoc.value.automatic_candidates;
    const doc = await updateMemorySettings(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      nextVal
    );
    memoryDoc.value = doc;
    showSuccess(nextVal ? "自动候选推断已开启" : "自动候选推断已关闭");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 打开新增事实弹窗
function openAddFactModal() {
  editingFact.value = null;
  formText.value = "";
  formCategory.value = "preference";
  formExpiresAt.value = "";
  isEditModalOpen.value = true;
}

// 打开编辑事实弹窗
function openEditFactModal(fact: FactItem) {
  editingFact.value = fact;
  formText.value = fact.text;
  formCategory.value = fact.category;
  formExpiresAt.value = fact.expires_at ? fact.expires_at.slice(0, 10) : "";
  isEditModalOpen.value = true;
}

// 提交事实保存
async function handleSaveFact() {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  const text = formText.value.trim();
  if (!text) {
    errorMsg.value = "记忆事实内容不能为空";
    return;
  }
  if (text.length > 1000) {
    errorMsg.value = "记忆内容不能超过 1000 个字符";
    return;
  }

  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const expiresAt = formExpiresAt.value ? new Date(formExpiresAt.value).toISOString() : null;
    const doc = await saveMemoryFact(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      {
        text,
        category: formCategory.value,
        expires_at: expiresAt,
      },
      editingFact.value?.id
    );
    memoryDoc.value = doc;
    isEditModalOpen.value = false;
    showSuccess(editingFact.value ? "事实更新成功" : "新增事实成功");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 删除事实
async function handleDeleteFact(factId: string) {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  if (!confirm("确定要删除这条记忆事实吗？")) return;

  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const doc = await deleteMemoryFact(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      factId
    );
    memoryDoc.value = doc;
    showSuccess("事实删除成功");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 清空记忆
async function handleClearMemory() {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const doc = await clearMemory(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision
    );
    memoryDoc.value = doc;
    isClearConfirmOpen.value = false;
    showSuccess("记忆事实已全部清空");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 采纳候选
async function handleAcceptCandidate(factId: string) {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const doc = await acceptMemoryCandidate(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      factId
    );
    memoryDoc.value = doc;
    showSuccess("候选记忆已采纳为正式事实");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 拒绝候选
async function handleRejectCandidate(factId: string) {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const doc = await rejectMemoryCandidate(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      factId
    );
    memoryDoc.value = doc;
    showSuccess("已拒绝并移除该候选推断");
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 追加恢复事实
async function handleRestoreFacts() {
  if (!activeProjectId.value || !activeThreadId.value || !memoryDoc.value || actionLoading.value) return;
  restoreParseError.value = "";
  let parsed: any[];
  try {
    parsed = JSON.parse(restoreJsonText.value);
    if (!Array.isArray(parsed)) {
      restoreParseError.value = "导入内容必须是 JSON 数组格式";
      return;
    }
  } catch (e: any) {
    restoreParseError.value = "JSON 解析失败：" + e.message;
    return;
  }

  if (parsed.length === 0) {
    restoreParseError.value = "导入数组不能为空";
    return;
  }
  if (parsed.length > 100) {
    restoreParseError.value = "单次最多追加恢复 100 条记忆事实";
    return;
  }

  actionLoading.value = true;
  errorMsg.value = "";
  try {
    const factsToRestore = parsed.map((item) => ({
      text: String(item.text || "").trim(),
      category: item.category === "fact" ? ("fact" as const) : ("preference" as const),
      expires_at: item.expires_at || null,
    }));
    const doc = await restoreMemoryFacts(
      activeProjectId.value,
      activeThreadId.value,
      memoryDoc.value.revision,
      factsToRestore
    );
    memoryDoc.value = doc;
    isRestoreModalOpen.value = false;
    restoreJsonText.value = "";
    showSuccess(`已成功追加恢复 ${factsToRestore.length} 条事实`);
  } catch (err: any) {
    handleActionError(err);
  } finally {
    actionLoading.value = false;
  }
}

// 统一错误处理与 CAS 并发冲突
function handleActionError(err: any) {
  const code = err.response?.data?.code || err.code;
  if (code === "memory_revision_conflict") {
    errorMsg.value = "⚠️ 数据已被其他操作更新（版本冲突）。已自动刷新至最新内容，您的编辑草稿已保留在表单中，请重新核对后提交。";
    fetchMemory(); // 自动拉取最新 revision
  } else if (code === "memory_capacity_exceeded") {
    errorMsg.value = "记忆库已达容量上限（单作用域最多 100 条事实 / 100 条候选）";
  } else if (code === "memory_expired") {
    errorMsg.value = "该候选事实已过期，无法采纳";
  } else {
    errorMsg.value = err.response?.data?.message || err.message || "操作失败";
  }
}

function showSuccess(msg: string) {
  successMsg.value = msg;
  setTimeout(() => {
    if (successMsg.value === msg) {
      successMsg.value = "";
    }
  }, 3500);
}

// 监听绑定的 threadId 变化
watch(activeThreadId, (newId) => {
  if (newId) {
    fetchMemory();
  }
});

// 监听项目切换，重置记忆状态
watch(activeProjectId, () => {
  memoryDoc.value = null;
  searchQuery.value = "";
  errorMsg.value = "";
  successMsg.value = "";
});

// 键盘无障碍支持（ESC 关闭弹窗）
function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") {
    isEditModalOpen.value = false;
    isRestoreModalOpen.value = false;
    isClearConfirmOpen.value = false;
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("keydown", handleKeydown);
  onScopeDispose(() => {
    window.removeEventListener("keydown", handleKeydown);
  });
}

onMounted(() => {
  if (activeThreadId.value) {
    fetchMemory();
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
              <BaseIcon name="shield" size="sm" />
            </span>
            <h1 class="text-xl font-bold text-zinc-900 dark:text-zinc-100">
              长期记忆与偏好治理
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            Dear Agent 在项目 {{ activeProject?.name }} 中沉淀的事实知识与执行偏好（基于 PostgreSQL 规范存储）
          </p>
        </div>

        <!-- 会话切换与创建上下文 -->
        <div class="flex flex-wrap items-center gap-3">
          <div v-if="hasThreads" class="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <span class="text-[11px] font-medium text-zinc-500">关联会话:</span>
            <select
              :value="activeThreadId"
              @change="switchThread(($event.target as HTMLSelectElement).value)"
              class="max-w-[180px] truncate bg-transparent text-xs font-medium text-zinc-900 focus:outline-none dark:text-zinc-100"
            >
              <option v-for="t in threads" :key="t.thread_id" :value="t.thread_id">
                {{ t.metadata?.title || t.thread_id.slice(0, 8) }}
              </option>
            </select>
          </div>

          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loading"
            @click="fetchMemory"
            title="刷新记忆"
          >
            <template #icon>
              <BaseIcon name="refresh" size="xs" />
            </template>
            刷新
          </BaseButton>

          <BaseButton
            variant="primary"
            size="sm"
            :disabled="!hasThreads || !canWrite"
            :title="!canWrite ? '缺少项目写权限' : undefined"
            @click="openAddFactModal"
          >
            <template #icon>
              <BaseIcon name="plus" size="xs" />
            </template>
            新增事实
          </BaseButton>
        </div>
      </div>

      <!-- 只读权限提示横幅 -->
      <div v-if="!canWrite" class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        <BaseIcon name="shield" size="xs" class="text-amber-600 dark:text-amber-400" />
        <span>当前项目处于只读模式（缺少 project.runtime.write 权限），记忆新增、编辑、删除与清空操作已锁定。</span>
      </div>

      <!-- 成功提示 -->
      <div v-if="successMsg" class="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
        <BaseIcon name="check" size="xs" class="text-emerald-600 dark:text-emerald-400" />
        <span>{{ successMsg }}</span>
      </div>

      <!-- 错误警告 -->
      <div v-if="errorMsg" class="flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
        <BaseIcon name="alert" size="xs" class="text-rose-600 dark:text-rose-400" />
        <span class="flex-1">{{ errorMsg }}</span>
        <button @click="errorMsg = ''" class="text-rose-500 hover:text-rose-700">✕</button>
      </div>

      <!-- 无会话时的降级友好空态 -->
      <div
        v-if="!contextLoading && !hasThreads"
        class="rounded-2xl border border-dashed border-zinc-300 bg-white/50 p-12 text-center dark:border-zinc-700 dark:bg-zinc-900/50"
      >
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950 dark:text-primary-400">
          <BaseIcon name="sparkle" size="md" />
        </div>
        <h3 class="mt-4 text-base font-semibold text-zinc-900 dark:text-zinc-100">
          当前项目尚未开启 Dear Agent 会话
        </h3>
        <p class="mx-auto mt-2 max-w-md text-xs text-zinc-500 dark:text-zinc-400">
          记忆治理依托 Dear Agent 运行时沙箱会话进行权限校验与存储绑定。您可以一键创建首个研究会话，立即启用长期记忆能力。
        </p>
        <div class="mt-6">
          <BaseButton
            variant="primary"
            size="md"
            :loading="isCreatingThread"
            @click="createInitialThread"
          >
            <template #icon>
              <BaseIcon name="plus" size="sm" />
            </template>
            立即创建会话并开启记忆
          </BaseButton>
        </div>
      </div>

      <!-- 核心治理面板（有会话时展示） -->
      <div v-else class="space-y-6">
        <!-- 统计与自动候选控制栏 -->
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div class="text-xs font-medium text-zinc-500">生效事实总数</div>
            <div class="mt-1.5 flex items-baseline gap-2">
              <span class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                {{ memoryDoc?.facts.length ?? 0 }}
              </span>
              <span class="text-xs text-zinc-400">/ 100 上限</span>
            </div>
          </div>

          <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div class="text-xs font-medium text-zinc-500">待审核候选</div>
            <div class="mt-1.5 flex items-baseline gap-2">
              <span class="text-2xl font-bold text-amber-600 dark:text-amber-400">
                {{ memoryDoc?.candidates.length ?? 0 }}
              </span>
              <span class="text-xs text-zinc-400">条待人工确认</span>
            </div>
          </div>

          <div class="flex items-center justify-between rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div>
              <div class="flex items-center gap-1 text-xs font-medium text-zinc-900 dark:text-zinc-100">
                <span>自动推断候选</span>
                <span class="cursor-help text-zinc-400" title="开启后，模型在执行时可推断偏好并放入候选库；必须人工确认后方可生效。默认关闭。">ℹ️</span>
              </div>
              <div class="mt-0.5 text-[11px] text-zinc-500">
                {{ memoryDoc?.automatic_candidates ? "已开启模型推断" : "仅接受人工录入" }}
              </div>
            </div>
            <button
              type="button"
              :disabled="actionLoading || !memoryDoc || !canWrite"
              @click="toggleAutomaticCandidates"
              :class="[
                'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none',
                memoryDoc?.automatic_candidates ? 'bg-primary-600' : 'bg-zinc-200 dark:bg-zinc-700'
              ]"
            >
              <span
                :class="[
                  'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                  memoryDoc?.automatic_candidates ? 'translate-x-5' : 'translate-x-0'
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
              @click="activeTab = 'facts'"
              :class="[
                'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
                activeTab === 'facts'
                  ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                  : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
              ]"
            >
              <BaseIcon name="folder" size="xs" />
              <span>生效事实</span>
              <span class="rounded-full bg-zinc-200 px-1.5 py-0.2 text-[10px] dark:bg-zinc-700">
                {{ memoryDoc?.facts.length ?? 0 }}
              </span>
            </button>

            <button
              type="button"
              @click="activeTab = 'candidates'"
              :class="[
                'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
                activeTab === 'candidates'
                  ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                  : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
              ]"
            >
              <BaseIcon name="sparkle" size="xs" />
              <span>推断候选</span>
              <span
                v-if="memoryDoc?.candidates.length"
                class="rounded-full bg-amber-100 px-1.5 py-0.2 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400"
              >
                {{ memoryDoc.candidates.length }}
              </span>
            </button>
          </div>

          <!-- 右侧检索与操作工具 -->
          <div class="flex items-center gap-2">
            <div class="relative w-48 sm:w-64">
              <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-zinc-400">
                <BaseIcon name="search" size="xs" />
              </span>
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜索记忆事实..."
                @keyup.enter="fetchMemory"
                class="w-full rounded-lg border border-zinc-200 bg-white py-1.5 pl-8 pr-3 text-xs text-zinc-900 placeholder-zinc-400 shadow-sm focus:border-primary-500 focus:outline-none dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
              />
            </div>

            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="!canWrite"
              @click="isRestoreModalOpen = true"
              title="批量追加恢复 JSON 事实"
            >
              <template #icon>
                <BaseIcon name="download" size="xs" />
              </template>
              追加恢复
            </BaseButton>

            <BaseButton
              variant="danger"
              size="sm"
              :disabled="!memoryDoc?.facts.length || !canWrite"
              @click="isClearConfirmOpen = true"
              title="清空当前范围全部记忆"
            >
              <template #icon>
                <BaseIcon name="trash" size="xs" />
              </template>
              清空事实
            </BaseButton>
          </div>
        </div>

        <!-- Tab 1: 生效事实列表 -->
        <div v-if="activeTab === 'facts'" class="space-y-3">
          <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
            正在载入记忆库...
          </div>

          <div v-else-if="filteredFacts.length === 0" class="rounded-xl border border-dashed border-zinc-200 p-8 text-center dark:border-zinc-800">
            <div class="text-xs text-zinc-500">
              {{ searchQuery ? "未找到匹配的记忆事实" : "暂无已生效的记忆事实，您可以点击右上角“新增事实”手动录入" }}
            </div>
          </div>

          <div
            v-else
            v-for="fact in filteredFacts"
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
                      : 'bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400'
                  ]"
                >
                  {{ fact.category === 'preference' ? '偏好规则' : '知识事实' }}
                </span>

                <span class="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-zinc-800">
                  来源: {{ fact.origin === 'user' ? '用户录入' : fact.origin === 'confirmed' ? '审核采纳' : '推断' }}
                </span>

                <span class="text-[10px] text-zinc-400">rev.{{ fact.revision }}</span>

                <span v-if="fact.expires_at" class="text-[10px] text-amber-600 dark:text-amber-400">
                  到期: {{ fact.expires_at.slice(0, 10) }}
                </span>
              </div>

              <p class="text-sm font-medium leading-relaxed text-zinc-900 dark:text-zinc-100">
                {{ fact.text }}
              </p>

              <div class="text-[11px] text-zinc-400">
                更新于 {{ new Date(fact.updated_at).toLocaleString() }}
              </div>
            </div>

            <!-- 操作按钮 -->
            <div v-if="canWrite" class="flex items-center gap-1 self-end sm:self-center">
              <button
                type="button"
                @click="openEditFactModal(fact)"
                class="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                title="编辑事实"
              >
                <BaseIcon name="pencil" size="xs" />
              </button>
              <button
                type="button"
                @click="handleDeleteFact(fact.id)"
                class="rounded-lg p-1.5 text-zinc-500 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40 dark:hover:text-rose-400"
                title="删除事实"
              >
                <BaseIcon name="trash" size="xs" />
              </button>
            </div>
          </div>
        </div>

        <!-- Tab 2: 推断候选列表 -->
        <div v-else class="space-y-3">
          <div class="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
            <div class="flex items-center gap-1.5 font-medium">
              <BaseIcon name="shield" size="xs" />
              <span>候选审查机制</span>
            </div>
            <p class="mt-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-400">
              候选记忆由模型在会话执行中推断生成，<strong>尚未生效</strong>。采纳后将转为正式事实；拒绝将记录指纹，避免重复推断。
            </p>
          </div>

          <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
            正在载入候选数据...
          </div>

          <div v-else-if="!memoryDoc?.candidates.length" class="rounded-xl border border-dashed border-zinc-200 p-8 text-center dark:border-zinc-800">
            <div class="text-xs text-zinc-500">暂无待审核的推断候选</div>
          </div>

          <div
            v-else
            v-for="cand in memoryDoc.candidates"
            :key="cand.id"
            class="flex flex-col justify-between gap-3 rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm sm:flex-row sm:items-center dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
                  推断候选
                </span>
                <span class="text-[10px] text-zinc-400">
                  {{ new Date(cand.created_at).toLocaleString() }}
                </span>
              </div>
              <p class="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {{ cand.text }}
              </p>
            </div>

            <div class="flex items-center gap-2 self-end sm:self-center">
              <BaseButton
                variant="secondary"
                size="xs"
                :disabled="actionLoading || !canWrite"
                @click="handleRejectCandidate(cand.id)"
              >
                拒绝丢弃
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
    </div>

    <!-- 新增/编辑事实弹窗 -->
    <div
      v-if="isEditModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div class="flex items-center justify-between border-b border-zinc-200 pb-3 dark:border-zinc-800">
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            {{ editingFact ? "编辑记忆事实" : "新增记忆事实" }}
          </h3>
          <button @click="isEditModalOpen = false" class="text-zinc-400 hover:text-zinc-600">✕</button>
        </div>

        <div class="mt-4 space-y-4">
          <div>
            <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">分类</label>
            <div class="mt-1.5 flex gap-4">
              <label class="flex items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
                <input type="radio" v-model="formCategory" value="preference" />
                <span>偏好规则 (Preference)</span>
              </label>
              <label class="flex items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
                <input type="radio" v-model="formCategory" value="fact" />
                <span>知识事实 (Fact)</span>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
              记忆内容 (≤ 1000 字符)
            </label>
            <textarea
              v-model="formText"
              rows="4"
              class="mt-1.5 w-full rounded-xl border border-zinc-300 bg-white p-3 text-xs text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              placeholder="例如：生成代码时必须附带详细单测用例并遵守 KISS 原则..."
            ></textarea>
            <div class="mt-1 text-right text-[10px] text-zinc-400">
              {{ formText.length }} / 1000
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
              到期时间 (可选)
            </label>
            <input
              type="date"
              v-model="formExpiresAt"
              class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
          </div>
        </div>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="secondary" size="sm" @click="isEditModalOpen = false">
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="actionLoading"
            @click="handleSaveFact"
          >
            保存提交
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- 追加恢复弹窗 -->
    <div
      v-if="isRestoreModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div class="flex items-center justify-between border-b border-zinc-200 pb-3 dark:border-zinc-800">
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            批量追加恢复记忆事实 (JSON)
          </h3>
          <button @click="isRestoreModalOpen = false" class="text-zinc-400 hover:text-zinc-600">✕</button>
        </div>

        <div class="mt-4 space-y-3">
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            请粘贴 JSON 格式的事实数组（最多 100 条）。本操作为<strong>追加导入</strong>，不会覆盖已有记忆。
          </p>

          <textarea
            v-model="restoreJsonText"
            rows="6"
            class="w-full rounded-xl border border-zinc-300 bg-white p-3 font-mono text-[11px] text-zinc-900 focus:border-primary-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            placeholder='[&#10;  {"text": "偏好简洁的代码实现", "category": "preference"}&#10;]'
          ></textarea>

          <div v-if="restoreParseError" class="text-xs text-rose-600">
            {{ restoreParseError }}
          </div>
        </div>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="secondary" size="sm" @click="isRestoreModalOpen = false">
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :loading="actionLoading"
            @click="handleRestoreFacts"
          >
            确认追加导入
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- 清空记忆确认弹窗 -->
    <div
      v-if="isClearConfirmOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div class="flex items-center gap-3 text-rose-600">
          <BaseIcon name="trash" size="md" />
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            清空记忆库确认
          </h3>
        </div>

        <p class="mt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
          ⚠️ 确定要清空当前项目范围内的全部记忆事实吗？此操作不可逆，将自增 epoch 防止历史未决推断复活。
        </p>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="secondary" size="sm" @click="isClearConfirmOpen = false">
            取消
          </BaseButton>
          <BaseButton
            variant="danger"
            size="sm"
            :loading="actionLoading"
            @click="handleClearMemory"
          >
            确认彻底清空
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>
