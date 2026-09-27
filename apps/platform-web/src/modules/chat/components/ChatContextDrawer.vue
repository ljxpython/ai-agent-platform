<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import { useUiStore } from "@/stores/ui";
import { downloadBlob } from "@/utils/browser-download";
import { copyText } from "@/utils/clipboard";
import { toPrettyJson } from "@/utils/threads";
import { buildChatHistoryView } from "../history-view-model";
import ChatTodoStatusBadge, {
  type TodoBadgeStatus,
} from "./ChatTodoStatusBadge.vue";
type ChatInspectorFile = {
  path: string;
  content: string;
  lineCount: number;
  completeness: string;
};
type ChatPlanTodo = { id: string; content: string; status: TodoBadgeStatus };
type ChatPlanView = {
  planTodos: ChatPlanTodo[];
  ephemeralTodos: ChatPlanTodo[];
  activeTask: ChatPlanTodo | null;
  totalTasks: number;
  completedTasks: number;
  allTasksCompleted: boolean;
  hasFrozenPlan: boolean;
};
import type { ThreadHistoryEntry } from "@/types/management";

type InspectorTabKey = "overview" | "tasks" | "files" | "history";

const props = defineProps<{
  show: boolean;
  initialTab: InspectorTabKey;
  showHistory: boolean;
  showArtifacts: boolean;
  allowResetTarget: boolean;
  targetText: string;
  projectName: string;
  activeThreadId: string;
  lastRunId: string;
  selectedBranch: string;
  latestMessagePreview: string;
  historyItems: ThreadHistoryEntry[];
  isViewingBranch: boolean;
  planView: ChatPlanView;
  files: ChatInspectorFile[];
  values?: Record<string, unknown> | null;
  isRunning: boolean;
  hasInterrupt: boolean;
  sourceNote: string;
  contextNotice?: string;
  onUpdateState?: (values: Record<string, unknown>) => Promise<boolean>;
  historyLoading?: boolean;
  hasMoreHistory?: boolean;
  canExecute?: boolean;
  run?: unknown;
}>();

const emit = defineEmits<{
  close: [];
  "select-branch": [branchId: string];
  "reset-target": [];
  "load-history": [limit?: number];
  fork: [];
}>();

const uiStore = useUiStore();
const activeTab = ref<InspectorTabKey>("overview");
const selectedFilePath = ref("");
const isEditing = ref(false);
const editValue = ref("");
const isSaving = ref(false);

const availableTabs = computed(() => {
  const tabs: Array<{
    key: InspectorTabKey;
    label: string;
    count?: number;
    tone?: "info" | "warning" | "success";
  }> = [
    { key: "overview", label: "概览" },
    {
      key: "tasks",
      label: "ToDo",
      count: props.planView.totalTasks + props.planView.ephemeralTodos.length,
      tone: props.planView.activeTask
        ? "info"
        : props.planView.allTasksCompleted
          ? "success"
          : undefined,
    },
    { key: "files", label: "Files", count: props.files.length },
  ];

  if (props.showHistory) {
    tabs.push({
      key: "history",
      label: "历史",
      count: props.historyItems.length,
      tone: props.isViewingBranch ? "warning" : undefined,
    });
  }

  return tabs;
});

const selectedFile = computed(
  () =>
    props.files.find((item) => item.path === selectedFilePath.value) || null,
);
const hasTasks = computed(
  () =>
    props.planView.totalTasks > 0 || props.planView.ephemeralTodos.length > 0,
);
const editDisabled = computed(
  () => props.isRunning || props.hasInterrupt || isSaving.value,
);
const currentTaskLabel = computed(
  () => props.planView.activeTask?.content || "暂无",
);
const isLatestMessageExpanded = ref(false);
const hasLongLatestMessage = computed(() => {
  const msg = props.latestMessagePreview || "";
  return msg.length > 70 || msg.includes("\n");
});
const historyView = computed(() =>
  buildChatHistoryView({
    items: props.historyItems,
    selectedBranch: props.selectedBranch,
    isViewingBranch: props.isViewingBranch,
  }),
);

const showOnlyMilestones = ref(true);
const historyRoleFilter = ref<"all" | "user" | "agent" | "tool">("all");

const displayedHistoryItems = computed(() => {
  let list = historyView.value.items;
  if (showOnlyMilestones.value) {
    const milestones = list.filter((item) => item.isKeyMilestone);
    list = milestones.length > 0 ? milestones : list;
  }
  if (historyRoleFilter.value !== "all") {
    list = list.filter((item) => item.role === historyRoleFilter.value);
  }
  return list;
});

watch(
  () => [props.initialTab, props.showHistory, props.show] as const,
  ([nextTab, showHistory, isOpen]) => {
    if (!isOpen) {
      return;
    }

    if (nextTab === "history" && !showHistory) {
      activeTab.value = "overview";
      return;
    }

    activeTab.value = nextTab;
  },
  { immediate: true },
);

watch(
  () => props.files,
  (nextFiles) => {
    if (nextFiles.length === 0) {
      selectedFilePath.value = "";
      isEditing.value = false;
      editValue.value = "";
      return;
    }

    if (
      !selectedFilePath.value ||
      !nextFiles.some((item) => item.path === selectedFilePath.value)
    ) {
      selectedFilePath.value = nextFiles[0].path;
      isEditing.value = false;
      editValue.value = nextFiles[0].content;
    }
  },
  { immediate: true, deep: true },
);

watch(selectedFile, (file) => {
  if (!isEditing.value) {
    editValue.value = file?.content || "";
  }
});

const planProgressPercent = computed(() => {
  if (props.planView.totalTasks <= 0) {
    return 0;
  }
  return Math.min(
    100,
    Math.round(
      (props.planView.completedTasks / props.planView.totalTasks) * 100,
    ),
  );
});

const todoGroupMeta: Record<
  string,
  { label: string; dotClass: string; badgeClass: string }
> = {
  in_progress: {
    label: "进行中",
    dotClass: "bg-sky-500",
    badgeClass: "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
  },
  pending: {
    label: "待执行",
    dotClass: "bg-amber-400",
    badgeClass:
      "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
  },
  completed: {
    label: "已完成",
    dotClass: "bg-emerald-500",
    badgeClass:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  },
  other: {
    label: "其他状态",
    dotClass: "bg-rose-500",
    badgeClass:
      "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
  },
};

function formatTodoStep(id: string): string {
  if (!id) {
    return "#--";
  }
  if (/^\d+$/.test(id)) {
    const num = parseInt(id, 10) + 1;
    return `#${num < 10 ? "0" + num : num}`;
  }
  return `#${id}`;
}

function groupTodoList(todos: ChatPlanTodo[]) {
  return {
    in_progress: todos.filter((item) => item.status === "in_progress"),
    pending: todos.filter((item) => item.status === "pending"),
    completed: todos.filter((item) => item.status === "completed"),
    other: todos.filter(
      (item) =>
        item.status !== "in_progress" &&
        item.status !== "pending" &&
        item.status !== "completed",
    ),
  };
}

const todoGroups = computed(() => {
  const grouped = groupTodoList(props.planView.planTodos);
  const keys = ["in_progress", "pending", "completed", "other"] as const;
  return keys
    .map((key) => ({
      key,
      meta: todoGroupMeta[key],
      items: grouped[key] || [],
    }))
    .filter((group) => group.items.length > 0);
});

async function handleCopyText(text: string, title = "已复制内容") {
  if (!text) {
    return;
  }

  const copied = await copyText(text);
  uiStore.pushToast({
    type: copied ? "success" : "error",
    title: copied ? title : "复制失败",
    message: text,
  });
}

async function handleCopyFile() {
  if (!selectedFile.value) {
    return;
  }

  const copied = await copyText(selectedFile.value.content);
  uiStore.pushToast({
    type: copied ? "success" : "error",
    title: copied ? "已复制文件内容" : "复制失败",
    message: copied ? selectedFile.value.path : "浏览器拒绝了复制动作",
  });
}

function handleDownloadFile() {
  if (!selectedFile.value) {
    return;
  }

  downloadBlob(
    new Blob([selectedFile.value.content], {
      type: "text/plain;charset=utf-8",
    }),
    selectedFile.value.path,
  );
  uiStore.pushToast({
    type: "success",
    title: "已下载文件",
    message: selectedFile.value.path,
  });
}

function handleStartEdit() {
  if (!selectedFile.value) {
    return;
  }

  if (editDisabled.value) {
    uiStore.pushToast({
      type: "warning",
      title: "当前不可编辑",
      message: "运行中或等待中断决策时，文件内容不能直接改。",
    });
    return;
  }

  isEditing.value = true;
  editValue.value = selectedFile.value.content;
}

function handleCancelEdit() {
  isEditing.value = false;
  editValue.value = selectedFile.value?.content || "";
}

async function handleSaveEdit() {
  if (!selectedFile.value || !props.onUpdateState) {
    return;
  }

  const rawFiles = props.values?.files;
  if (!rawFiles || typeof rawFiles !== "object" || Array.isArray(rawFiles)) {
    uiStore.pushToast({
      type: "error",
      title: "保存失败",
      message: "当前线程里没有可编辑的文件状态。",
    });
    return;
  }

  const nextFiles = { ...(rawFiles as Record<string, unknown>) };
  const currentRaw = nextFiles[selectedFile.value.path];
  if (typeof currentRaw === "string" || currentRaw == null) {
    nextFiles[selectedFile.value.path] = editValue.value;
  } else if (typeof currentRaw === "object" && !Array.isArray(currentRaw)) {
    const currentRecord = currentRaw as Record<string, unknown>;
    nextFiles[selectedFile.value.path] =
      "content" in currentRecord
        ? {
            ...currentRecord,
            content: editValue.value,
          }
        : editValue.value;
  } else {
    nextFiles[selectedFile.value.path] = editValue.value;
  }

  isSaving.value = true;
  try {
    await props.onUpdateState({ files: nextFiles });
    isEditing.value = false;
    uiStore.pushToast({
      type: "success",
      title: "文件已保存",
      message: selectedFile.value.path,
    });
  } catch (error) {
    uiStore.pushToast({
      type: "error",
      title: "保存失败",
      message: error instanceof Error ? error.message : "线程状态更新失败",
    });
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <BaseDrawer
    :show="show"
    title="会话详情"
    class="z-[100]"
    side="right"
    width="full"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div
        class="inline-flex max-w-full flex-wrap items-center gap-1 rounded-2xl border border-gray-200/70 bg-gray-100/80 p-1 dark:border-dark-700/60 dark:bg-dark-900/80"
      >
        <button
          v-for="tab in availableTabs"
          :key="tab.key"
          type="button"
          class="relative flex items-center justify-center gap-2 rounded-xl px-3.5 py-1.5 text-xs transition-all duration-150"
          :class="
            activeTab === tab.key
              ? 'bg-white font-semibold text-gray-900 shadow-xs dark:bg-dark-800 dark:text-white'
              : 'font-medium text-gray-500 hover:text-gray-900 dark:text-dark-300 dark:hover:text-white'
          "
          :aria-label="tab.label"
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}</span>
          <span
            v-if="typeof tab.count === 'number'"
            class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none transition-colors"
            :class="
              activeTab === tab.key
                ? 'bg-primary-50 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300'
                : 'bg-gray-200/70 text-gray-600 dark:bg-dark-700 dark:text-dark-300'
            "
          >
            {{ tab.count }}
          </span>
          <span
            v-else-if="tab.tone"
            class="inline-flex h-2 w-2 rounded-full"
            :class="
              tab.tone === 'warning'
                ? 'bg-amber-500 ring-2 ring-amber-400/20'
                : tab.tone === 'success'
                  ? 'bg-emerald-500 ring-2 ring-emerald-400/20'
                  : 'bg-sky-500 ring-2 ring-sky-400/20'
            "
          />
        </button>
      </div>

      <div v-if="activeTab === 'overview'" class="space-y-5">
        <div class="grid gap-4 md:grid-cols-3">
          <div class="pw-panel-muted flex flex-col justify-between">
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>当前任务</span>
                <span class="text-xs">🎯</span>
              </div>
              <div
                class="mt-2 text-sm font-semibold text-gray-900 line-clamp-2 dark:text-white"
                :title="currentTaskLabel"
              >
                {{ currentTaskLabel }}
              </div>
            </div>
            <div class="mt-2 text-[11px] text-gray-400 dark:text-dark-400">
              当前线程正在执行的目标
            </div>
          </div>

          <div class="pw-panel-muted flex flex-col justify-between">
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>文件状态</span>
                <span class="text-xs">📁</span>
              </div>
              <div
                class="mt-2 text-base font-semibold text-gray-900 dark:text-white"
              >
                {{ props.files.length }}
                <span
                  class="text-xs font-normal text-gray-400 dark:text-dark-400"
                  >个关联文件</span
                >
              </div>
            </div>
            <div class="mt-2 text-[11px] text-gray-400 dark:text-dark-400">
              可在 Files 标签中实时预览或编辑
            </div>
          </div>

          <div class="pw-panel-muted flex flex-col justify-between">
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>历史快照</span>
                <span class="text-xs">⏱️</span>
              </div>
              <div
                class="mt-2 text-base font-semibold text-gray-900 dark:text-white"
              >
                {{
                  props.showHistory
                    ? `${props.historyItems.length} 条`
                    : "未启用"
                }}
              </div>
            </div>
            <div class="mt-2 text-[11px] text-gray-400 dark:text-dark-400">
              {{
                props.showHistory
                  ? "支持时光机分支回溯执行"
                  : "当前环境未开启历史功能"
              }}
            </div>
          </div>
        </div>

        <div
          v-if="props.isViewingBranch"
          class="pw-panel-info flex items-center justify-between gap-3 text-sm"
        >
          <div class="min-w-0">
            <div class="font-semibold text-gray-900 dark:text-white">
              当前正在查看历史分支
            </div>
            <div
              class="mt-1 break-all text-xs leading-6 text-gray-500 dark:text-dark-300"
            >
              {{ props.selectedBranch }}
            </div>
          </div>
          <BaseButton variant="ghost" @click="emit('select-branch', '')">
            返回最新
          </BaseButton>
        </div>

        <div class="pw-panel">
          <div class="flex items-center justify-between">
            <div
              class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400"
            >
              当前执行上下文
            </div>
            <span
              class="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-700 dark:bg-primary-950/60 dark:text-primary-300"
            >
              Runtime
            </span>
          </div>

          <div class="mt-3 grid gap-2.5 sm:grid-cols-6">
            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-2.5 sm:col-span-2 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                Target 目标
              </div>
              <div
                class="mt-1 break-all text-xs font-semibold text-gray-900 dark:text-white"
              >
                {{ props.targetText }}
              </div>
            </div>

            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-2.5 sm:col-span-2 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                所属项目
              </div>
              <div
                class="mt-1 truncate text-xs font-semibold text-gray-900 dark:text-white"
              >
                {{ props.projectName || "--" }}
              </div>
            </div>

            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-2.5 sm:col-span-2 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                Branch 分支
              </div>
              <div
                class="mt-1 break-all font-mono text-xs font-semibold text-gray-900 dark:text-white"
              >
                {{ props.selectedBranch || "latest" }}
              </div>
            </div>

            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-2.5 sm:col-span-3 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="flex items-center justify-between text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                <span>Thread ID</span>
                <button
                  v-if="props.activeThreadId"
                  type="button"
                  class="cursor-pointer text-[10px] text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                  @click="handleCopyText(props.activeThreadId, 'Thread ID')"
                >
                  复制
                </button>
              </div>
              <div
                class="mt-1 break-all font-mono text-xs font-semibold text-gray-900 dark:text-white"
              >
                {{ props.activeThreadId || "--" }}
              </div>
            </div>

            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-2.5 sm:col-span-3 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="flex items-center justify-between text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                <span>Run ID</span>
                <button
                  v-if="props.lastRunId"
                  type="button"
                  class="cursor-pointer text-[10px] text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                  @click="handleCopyText(props.lastRunId, 'Run ID')"
                >
                  复制
                </button>
              </div>
              <div
                class="mt-1 break-all font-mono text-xs font-semibold text-gray-900 dark:text-white"
              >
                {{ props.lastRunId || "--" }}
              </div>
            </div>

            <div
              class="rounded-xl border border-gray-100 bg-gray-50/70 p-3 sm:col-span-6 dark:border-dark-700/60 dark:bg-dark-800/40"
            >
              <div
                class="flex items-center justify-between text-[11px] font-medium text-gray-400 dark:text-dark-400"
              >
                <div class="flex items-center gap-1.5">
                  <span class="text-xs">💬</span>
                  <span class="font-semibold text-gray-700 dark:text-dark-200"
                    >最近消息</span
                  >
                </div>
                <div class="flex items-center gap-2">
                  <button
                    v-if="hasLongLatestMessage"
                    type="button"
                    class="cursor-pointer text-[10px] font-medium text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                    @click="isLatestMessageExpanded = !isLatestMessageExpanded"
                  >
                    {{ isLatestMessageExpanded ? "收起" : "展开全文" }}
                  </button>
                  <button
                    v-if="props.latestMessagePreview"
                    type="button"
                    class="cursor-pointer text-[10px] text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                    @click="
                      handleCopyText(props.latestMessagePreview, '最近消息')
                    "
                  >
                    复制
                  </button>
                </div>
              </div>
              <div
                class="mt-2 text-xs leading-relaxed text-gray-700 dark:text-dark-200 transition-all"
                :class="
                  isLatestMessageExpanded
                    ? 'max-h-72 overflow-y-auto whitespace-pre-wrap break-words pr-1 text-[12px]'
                    : 'line-clamp-2 break-words'
                "
              >
                {{ props.latestMessagePreview || "暂无" }}
              </div>
            </div>
          </div>
        </div>

        <details class="pw-panel group">
          <summary
            class="flex cursor-pointer list-none items-center justify-between text-xs font-medium text-gray-700 dark:text-dark-200"
          >
            <div class="flex items-center gap-2">
              <span class="inline-flex h-2 w-2 rounded-full bg-sky-500" />
              <span class="font-semibold">运行状态数据 (Run Payload)</span>
            </div>
            <span
              class="text-[10px] text-gray-400 transition-transform group-open:rotate-180"
              >▼</span
            >
          </summary>
          <div
            class="mt-3 overflow-hidden rounded-xl border border-gray-800 bg-gray-950 dark:bg-black/70"
          >
            <div
              class="flex items-center justify-between border-b border-gray-800 bg-gray-900/90 px-3 py-1.5 text-[10px] text-gray-400"
            >
              <div class="flex items-center gap-1.5">
                <span class="h-2 w-2 rounded-full bg-red-500/80" />
                <span class="h-2 w-2 rounded-full bg-amber-500/80" />
                <span class="h-2 w-2 rounded-full bg-emerald-500/80" />
                <span class="ml-1 font-mono">run.json</span>
              </div>
              <button
                type="button"
                class="cursor-pointer font-medium text-gray-300 transition-colors hover:text-white"
                @click="handleCopyText(toPrettyJson(run), '运行数据')"
              >
                复制 JSON
              </button>
            </div>
            <pre
              class="max-h-80 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-5 text-gray-200"
              >{{ toPrettyJson(run) }}</pre
            >
          </div>
        </details>
        <div
          v-if="props.sourceNote"
          class="pw-panel-info text-sm leading-7 text-sky-800 dark:text-sky-100"
        >
          <div
            class="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-500 dark:text-sky-300"
          >
            目标来源
          </div>
          <div class="mt-2 whitespace-pre-wrap break-words">
            {{ props.sourceNote }}
          </div>
        </div>

        <div
          v-if="props.contextNotice"
          class="pw-panel-success text-sm leading-7 text-emerald-800 dark:text-emerald-100"
        >
          <div
            class="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-600 dark:text-emerald-300"
          >
            上下文说明
          </div>
          <div class="mt-2 whitespace-pre-wrap break-words">
            {{ props.contextNotice }}
          </div>
        </div>

        <div
          v-if="props.showArtifacts"
          class="pw-panel-muted text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            Artifact 侧栏
          </div>
          <p class="mt-2">
            当前 thread 如果存在 `values.ui` 条目，会在主画布右侧直接展开
            artifact 侧栏。这里仅保留说明，不再重复渲染内容。
          </p>
        </div>

        <div v-if="props.allowResetTarget" class="pw-panel-muted">
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            默认聊天目标
          </div>
          <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
            这个动作只会清掉当前项目保存的默认聊天入口，不会删除任何
            thread、消息或后端运行数据。
          </p>
          <div class="mt-4 flex justify-end">
            <BaseButton variant="ghost" @click="emit('reset-target')">
              清空默认目标
            </BaseButton>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'tasks'" class="space-y-4">
        <div
          v-if="props.planView.hasFrozenPlan"
          class="pw-panel-info text-sm leading-7 text-sky-800 dark:text-sky-100"
        >
          主计划固定展示第一次 `write_todos` 生成的任务列表；后续实时 todos
          只更新主计划状态，新出现的任务会单列到临时执行项。
        </div>

        <div v-if="hasTasks" class="grid gap-4 md:grid-cols-3">
          <div class="pw-panel-muted flex flex-col justify-between">
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>当前任务</span>
                <span
                  v-if="props.planView.activeTask"
                  class="inline-flex items-center gap-1 rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-600 dark:bg-sky-950/50 dark:text-sky-300"
                >
                  <span
                    class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500"
                  />
                  执行中
                </span>
              </div>
              <div
                class="mt-2 text-sm font-semibold text-gray-900 line-clamp-2 dark:text-white"
                :title="props.planView.activeTask?.content || '暂无'"
              >
                {{ props.planView.activeTask?.content || "暂无进行中的任务" }}
              </div>
            </div>
            <div
              class="mt-2 text-[11px] font-mono text-gray-400 dark:text-dark-400"
            >
              {{
                props.planView.activeTask
                  ? formatTodoStep(props.planView.activeTask.id)
                  : "--"
              }}
            </div>
          </div>

          <div
            class="pw-panel-muted flex flex-col justify-between transition-colors"
            :class="
              props.planView.allTasksCompleted && props.planView.totalTasks > 0
                ? 'border-emerald-200/80 bg-emerald-50/20 dark:border-emerald-900/40 dark:bg-emerald-950/15'
                : ''
            "
          >
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>主计划进度</span>
                <span
                  v-if="
                    props.planView.allTasksCompleted &&
                    props.planView.totalTasks > 0
                  "
                  class="rounded-full bg-emerald-100/80 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                >
                  已全部达成 ✨
                </span>
                <span
                  v-else
                  class="text-[11px] font-semibold text-gray-700 dark:text-dark-200"
                >
                  {{ planProgressPercent }}%
                </span>
              </div>
              <div
                class="mt-2 text-base font-semibold text-gray-900 dark:text-white"
              >
                {{ props.planView.completedTasks }}
                <span
                  class="text-xs font-normal text-gray-400 dark:text-dark-400"
                >
                  / {{ props.planView.totalTasks }} 项
                </span>
              </div>
            </div>
            <div
              class="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-gray-200/70 dark:bg-dark-700"
            >
              <div
                class="h-full rounded-full transition-all duration-500 ease-out"
                :class="
                  props.planView.allTasksCompleted &&
                  props.planView.totalTasks > 0
                    ? 'bg-emerald-500'
                    : 'bg-primary-600 dark:bg-primary-500'
                "
                :style="{ width: `${planProgressPercent}%` }"
              />
            </div>
          </div>

          <div class="pw-panel-muted flex flex-col justify-between">
            <div>
              <div
                class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400"
              >
                <span>临时执行项</span>
                <span
                  v-if="props.planView.ephemeralTodos.length > 0"
                  class="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:bg-amber-950/50 dark:text-amber-300"
                >
                  ⚡ 动态补充
                </span>
              </div>
              <div
                class="mt-2 text-base font-semibold text-gray-900 dark:text-white"
              >
                {{ props.planView.ephemeralTodos.length }}
                <span
                  class="text-xs font-normal text-gray-400 dark:text-dark-400"
                  >项</span
                >
              </div>
            </div>
            <div class="mt-2 text-[11px] text-gray-400 dark:text-dark-400">
              {{
                props.planView.ephemeralTodos.length > 0
                  ? "随运行动态扩充的任务"
                  : "当前无动态追加项"
              }}
            </div>
          </div>
        </div>

        <div
          v-if="!hasTasks"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm leading-7 text-gray-400 dark:border-dark-700 dark:text-dark-400"
        >
          当前还没有生成任务项
        </div>

        <div
          v-for="group in todoGroups"
          v-else
          :key="group.key"
          class="space-y-2.5"
        >
          <div class="flex items-center justify-between pt-1">
            <div
              class="flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-dark-400"
            >
              <span
                class="inline-block h-2 w-2 rounded-full"
                :class="group.meta.dotClass"
              />
              <span class="font-semibold text-gray-800 dark:text-dark-100">
                {{ group.meta.label }}
              </span>
            </div>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="group.meta.badgeClass"
            >
              {{ group.items.length }}
            </span>
          </div>

          <div class="space-y-2">
            <div
              v-for="todo in group.items"
              :key="todo.id"
              class="pw-panel px-4 py-3 transition-all"
              :class="
                todo.status === 'in_progress'
                  ? 'border-l-4 border-l-primary-500 border-primary-200/80 bg-primary-50/15 shadow-xs dark:border-primary-900/50 dark:border-l-primary-500 dark:bg-primary-950/10'
                  : ''
              "
            >
              <div class="flex items-start gap-3">
                <ChatTodoStatusBadge :status="todo.status" class="mt-0.5" />
                <div class="min-w-0 flex-1">
                  <div
                    class="text-sm leading-relaxed"
                    :class="{
                      'font-semibold text-gray-900 dark:text-white':
                        todo.status === 'in_progress',
                      'text-gray-400 line-through dark:text-dark-400':
                        todo.status === 'completed',
                      'text-gray-700 dark:text-dark-200':
                        todo.status !== 'in_progress' &&
                        todo.status !== 'completed',
                    }"
                  >
                    {{ todo.content }}
                  </div>
                  <div class="mt-1 flex items-center gap-1.5">
                    <span
                      class="inline-flex items-center rounded border border-gray-200/60 bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono font-medium text-gray-500 dark:border-dark-700/60 dark:bg-dark-800 dark:text-dark-400"
                    >
                      {{ formatTodoStep(todo.id) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="props.planView.ephemeralTodos.length > 0"
          class="space-y-2.5 pt-1"
        >
          <div
            class="flex items-center justify-between text-xs font-medium text-gray-500 dark:text-dark-400"
          >
            <div class="flex items-center gap-1.5">
              <span class="inline-block h-2 w-2 rounded-full bg-amber-500" />
              <span class="font-semibold text-gray-800 dark:text-dark-100"
                >临时补充任务</span
              >
            </div>
            <span
              class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
            >
              {{ props.planView.ephemeralTodos.length }}
            </span>
          </div>
          <div class="space-y-2">
            <div
              v-for="todo in props.planView.ephemeralTodos"
              :key="todo.id"
              class="pw-panel border-amber-200/60 bg-amber-50/15 px-4 py-3 transition-colors dark:border-amber-900/30 dark:bg-amber-950/10"
            >
              <div class="flex items-start gap-3">
                <ChatTodoStatusBadge :status="todo.status" class="mt-0.5" />
                <div class="min-w-0 flex-1">
                  <div
                    class="text-sm font-medium leading-relaxed text-gray-900 dark:text-white"
                  >
                    {{ todo.content }}
                  </div>
                  <div class="mt-1 flex items-center gap-2">
                    <span
                      class="inline-flex items-center rounded border border-gray-200/60 bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono font-medium text-gray-500 dark:border-dark-700/60 dark:bg-dark-800 dark:text-dark-400"
                    >
                      {{ formatTodoStep(todo.id) }}
                    </span>
                    <span
                      class="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400"
                    >
                      ⚡ 动态补充
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'files'" class="space-y-4">
        <div
          v-if="props.files.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          当前线程还没有文件状态。
        </div>

        <div v-else class="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
          <div class="space-y-1.5">
            <button
              v-for="file in props.files"
              :key="file.path"
              type="button"
              class="block w-full rounded-xl border p-2.5 text-left transition-all"
              :class="
                selectedFilePath === file.path
                  ? 'border-primary-200 bg-primary-50/70 text-primary-700 shadow-xs dark:border-primary-900/40 dark:bg-primary-950/30 dark:text-primary-200'
                  : 'border-gray-200/70 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-200 dark:hover:bg-dark-800 dark:hover:text-white'
              "
              @click="selectedFilePath = file.path"
            >
              <div class="flex items-center gap-2">
                <span class="text-xs">📄</span>
                <div
                  class="min-w-0 flex-1 truncate font-mono text-xs font-semibold"
                >
                  {{ file.path }}
                </div>
              </div>
              <div
                class="mt-1 flex items-center justify-between text-[11px] opacity-70"
              >
                <span>{{ file.lineCount }} 行</span>
                <span
                  v-if="file.completeness"
                  class="rounded bg-gray-200/60 px-1 py-0.2 font-mono text-[10px] dark:bg-dark-700"
                >
                  {{ file.completeness }}
                </span>
              </div>
            </button>
          </div>

          <div
            v-if="selectedFile"
            class="overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-xs dark:border-dark-700/80 dark:bg-dark-900"
          >
            <div
              class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200/80 bg-gray-50/90 px-4 py-2.5 dark:border-dark-700/80 dark:bg-dark-800/80"
            >
              <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5">
                  <span class="h-2.5 w-2.5 rounded-full bg-red-400/80" />
                  <span class="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                  <span class="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                </div>
                <div
                  class="font-mono text-xs font-semibold text-gray-900 dark:text-white"
                >
                  {{ selectedFile.path }}
                </div>
                <span
                  class="rounded-full bg-gray-200/70 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-dark-700 dark:text-dark-300"
                >
                  {{ selectedFile.lineCount }} 行 ·
                  {{ selectedFile.completeness }}
                </span>
              </div>

              <div class="flex flex-wrap items-center gap-1.5">
                <BaseButton size="sm" variant="ghost" @click="handleCopyFile">
                  复制
                </BaseButton>
                <BaseButton
                  size="sm"
                  variant="ghost"
                  @click="handleDownloadFile"
                >
                  下载
                </BaseButton>
                <BaseButton
                  v-if="!isEditing && onUpdateState"
                  size="sm"
                  variant="ghost"
                  @click="handleStartEdit"
                >
                  编辑
                </BaseButton>
              </div>
            </div>

            <div class="p-0">
              <textarea
                v-if="isEditing"
                v-model="editValue"
                rows="18"
                class="pw-input min-h-[420px] w-full resize-y rounded-none border-none font-mono text-xs leading-6 focus:ring-0"
              />
              <pre
                v-else
                class="min-h-[420px] max-h-[600px] overflow-auto whitespace-pre-wrap break-words bg-gray-950 p-4 font-mono text-xs leading-6 text-gray-100 dark:bg-black/80"
                >{{ selectedFile.content }}</pre
              >
            </div>

            <div
              v-if="isEditing"
              class="flex flex-wrap justify-end gap-3 border-t border-gray-200/80 bg-gray-50/50 p-3 dark:border-dark-700/80 dark:bg-dark-800/40"
            >
              <BaseButton size="sm" variant="ghost" @click="handleCancelEdit">
                取消
              </BaseButton>
              <BaseButton
                size="sm"
                :disabled="editDisabled"
                @click="handleSaveEdit"
              >
                {{ isSaving ? "保存中..." : "保存" }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'history'" class="space-y-3">
        <div
          v-if="!props.showHistory"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          当前页面没有启用历史分支功能。
        </div>

        <template v-else>
          <div class="grid gap-4 md:grid-cols-3">
            <div class="pw-panel-muted">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                Checkpoints
              </div>
              <div
                class="mt-2 text-sm font-semibold text-gray-900 dark:text-white"
              >
                {{ historyView.totalEntries }}
              </div>
            </div>
            <div class="pw-panel-muted">
              <div class="text-xs text-gray-400 dark:text-dark-400">分叉组</div>
              <div
                class="mt-2 text-sm font-semibold text-gray-900 dark:text-white"
              >
                {{ historyView.branchGroupCount }}
              </div>
            </div>
            <div class="pw-panel-muted">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                当前快照
              </div>
              <div
                class="mt-2 break-all text-sm font-semibold text-gray-900 dark:text-white"
              >
                {{ historyView.activeCheckpointId || "latest" }}
              </div>
            </div>
          </div>

          <div
            class="pw-panel-info flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="min-w-0">
              <div class="font-semibold text-gray-900 dark:text-white">
                {{
                  props.isViewingBranch
                    ? "当前正在查看历史快照"
                    : "当前正在查看最新线程头"
                }}
              </div>
              <div
                class="mt-1 break-all text-xs leading-6 text-gray-500 dark:text-dark-300"
              >
                {{
                  props.isViewingBranch
                    ? props.selectedBranch
                    : historyView.activeCheckpointId || "latest"
                }}
              </div>
            </div>
            <div
              v-if="props.isViewingBranch"
              class="flex flex-wrap items-center gap-2 shrink-0"
            >
              <BaseButton :disabled="!canExecute" @click="emit('fork')">
                从此快照重新执行
              </BaseButton>
              <BaseButton variant="secondary" @click="emit('close')">
                关闭抽屉查看
              </BaseButton>
              <BaseButton variant="ghost" @click="emit('select-branch', '')">
                返回最新
              </BaseButton>
            </div>
          </div>

          <div class="space-y-2 pt-1">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div
                class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs dark:border-dark-700 dark:bg-dark-800"
              >
                <button
                  type="button"
                  class="rounded-md px-2.5 py-1 font-medium transition-all"
                  :class="
                    showOnlyMilestones
                      ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-900 dark:text-white'
                      : 'text-gray-500 hover:text-gray-700 dark:text-dark-300 dark:hover:text-white'
                  "
                  @click="showOnlyMilestones = true"
                >
                  🎯 关键节点 ({{ historyView.keyMilestoneCount }})
                </button>
                <button
                  type="button"
                  class="rounded-md px-2.5 py-1 font-medium transition-all"
                  :class="
                    !showOnlyMilestones
                      ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-900 dark:text-white'
                      : 'text-gray-500 hover:text-gray-700 dark:text-dark-300 dark:hover:text-white'
                  "
                  @click="showOnlyMilestones = false"
                >
                  全部 Steps ({{ historyView.totalEntries }})
                </button>
              </div>
              <span class="text-xs text-gray-400 dark:text-dark-400">
                {{
                  showOnlyMilestones
                    ? "已过滤纯内部系统检查点"
                    : "展示全部原始中间步骤"
                }}
              </span>
            </div>

            <div class="flex flex-wrap items-center gap-1.5 pt-1">
              <span class="text-xs text-gray-400 dark:text-dark-400 mr-1"
                >角色筛选:</span
              >
              <button
                type="button"
                class="rounded-md px-2 py-0.5 text-xs transition-colors"
                :class="
                  historyRoleFilter === 'all'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-950/60 dark:text-primary-200 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-800'
                "
                @click="historyRoleFilter = 'all'"
              >
                全部
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs transition-colors"
                :class="
                  historyRoleFilter === 'user'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-950/60 dark:text-primary-200 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-800'
                "
                @click="historyRoleFilter = 'user'"
              >
                <span>👤 用户提问</span>
                <span
                  class="rounded-full bg-gray-200/80 px-1 text-[10px] dark:bg-dark-700"
                  >{{ historyView.userCount }}</span
                >
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs transition-colors"
                :class="
                  historyRoleFilter === 'agent'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-950/60 dark:text-primary-200 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-800'
                "
                @click="historyRoleFilter = 'agent'"
              >
                <span>🤖 Agent 回复</span>
                <span
                  class="rounded-full bg-gray-200/80 px-1 text-[10px] dark:bg-dark-700"
                  >{{ historyView.agentCount }}</span
                >
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs transition-colors"
                :class="
                  historyRoleFilter === 'tool'
                    ? 'bg-primary-100 text-primary-800 dark:bg-primary-950/60 dark:text-primary-200 font-semibold shadow-xs'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-800'
                "
                @click="historyRoleFilter = 'tool'"
              >
                <span>🛠️ 工具调用</span>
                <span
                  class="rounded-full bg-gray-200/80 px-1 text-[10px] dark:bg-dark-700"
                  >{{ historyView.toolCount }}</span
                >
              </button>
            </div>
          </div>

          <div
            v-if="displayedHistoryItems.length === 0"
            class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
          >
            {{
              historyRoleFilter !== "all"
                ? "未找到符合当前筛选条件的检查点，请切换其他角色或点击「全部」。"
                : "当前 thread 还没有 checkpoint 历史，或者还没开始对话。"
            }}
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="item in displayedHistoryItems"
              :key="item.id"
              class="relative pl-8"
            >
              <span
                class="absolute left-3 top-7 h-full w-px bg-gray-200/80 dark:bg-dark-700"
              />
              <span
                class="absolute left-0.5 top-4 inline-flex h-5 w-5 items-center justify-center rounded-full border border-gray-200/80 bg-white text-[10px] shadow-2xs dark:border-dark-700 dark:bg-dark-900"
                :class="
                  item.isCurrent
                    ? 'border-primary-300 ring-2 ring-primary-500/30 dark:border-primary-700'
                    : ''
                "
              >
                {{
                  item.role === "user"
                    ? "👤"
                    : item.role === "agent"
                      ? "🤖"
                      : item.role === "tool"
                        ? "🛠️"
                        : "⏱️"
                }}
              </span>

              <details class="pw-panel p-4">
                <summary class="cursor-pointer list-none">
                  <div
                    class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div class="min-w-0 flex-1">
                      <div
                        class="truncate text-sm font-semibold text-gray-900 dark:text-white"
                      >
                        {{ item.preview }}
                      </div>
                      <div
                        class="mt-1 flex items-center gap-2 font-mono text-xs text-gray-400 dark:text-dark-400"
                      >
                        <span class="truncate">{{ item.id }}</span>
                        <button
                          type="button"
                          class="cursor-pointer text-[10px] text-primary-600 transition-colors hover:text-primary-700 dark:text-primary-400"
                          @click.stop="handleCopyText(item.id, 'Checkpoint ID')"
                        >
                          复制
                        </button>
                      </div>
                    </div>
                    <div
                      class="shrink-0 text-xs text-gray-400 dark:text-dark-400"
                    >
                      {{ item.time }}
                    </div>
                  </div>

                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      class="pw-pill-soft font-medium"
                      :class="
                        item.role === 'user'
                          ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/30 dark:text-primary-200'
                          : item.role === 'agent'
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-200'
                            : item.role === 'tool'
                              ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/30 dark:text-sky-200'
                              : 'pw-pill-soft-neutral'
                      "
                    >
                      {{ item.roleLabel }}
                    </span>
                    <span
                      v-if="item.isLatest"
                      class="pw-pill-soft pw-pill-soft-success"
                    >
                      latest
                    </span>
                    <span
                      v-if="item.isCurrent"
                      class="pw-pill-soft pw-pill-soft-primary"
                    >
                      当前快照
                    </span>
                    <span
                      v-if="item.isInSelectedPath && !item.isCurrent"
                      class="pw-pill-soft pw-pill-soft-info"
                    >
                      当前分支路径
                    </span>
                    <span
                      v-if="(item.siblingCount || 0) > 1"
                      class="pw-pill-soft pw-pill-soft-warning"
                    >
                      分叉组 {{ item.siblingCount }}
                    </span>
                    <span
                      v-if="(item.childCount || 0) > 0"
                      class="pw-pill-soft border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/40 dark:bg-violet-950/20 dark:text-violet-200"
                    >
                      后续分支 {{ item.childCount }}
                    </span>
                    <span class="pw-pill-soft pw-pill-soft-neutral">
                      {{ item.step || "--" }}
                    </span>
                    <span
                      v-if="item.source"
                      class="pw-pill-soft pw-pill-soft-neutral"
                    >
                      {{ item.source }}
                    </span>
                    <span class="pw-pill-soft pw-pill-soft-neutral">
                      messages {{ item.messageCount || 0 }}
                    </span>
                    <span
                      v-if="(item.taskCount || 0) > 0"
                      class="pw-pill-soft pw-pill-soft-neutral"
                    >
                      tasks {{ item.taskCount || 0 }}
                    </span>
                    <span
                      v-if="item.hasInterrupts"
                      class="pw-pill-soft pw-pill-soft-danger"
                    >
                      interrupts
                    </span>
                  </div>
                </summary>

                <div
                  class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div
                    class="text-xs leading-6 text-gray-500 dark:text-dark-300"
                  >
                    <span v-if="item.parentId">
                      parent: {{ item.parentId }}
                    </span>
                    <span v-else>根 checkpoint</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <template v-if="item.isCurrent && props.isViewingBranch">
                      <BaseButton
                        size="sm"
                        :disabled="!canExecute"
                        @click="emit('fork')"
                      >
                        从此快照重新执行
                      </BaseButton>
                      <BaseButton
                        variant="secondary"
                        size="sm"
                        @click="emit('close')"
                      >
                        关闭抽屉查看
                      </BaseButton>
                    </template>
                    <BaseButton
                      v-else
                      variant="ghost"
                      :disabled="item.isCurrent"
                      @click="emit('select-branch', item.id)"
                    >
                      {{ item.selectLabel || "查看此快照" }}
                    </BaseButton>
                  </div>
                </div>

                <div
                  class="mt-3 overflow-hidden rounded-xl border border-gray-800 bg-gray-950 dark:bg-black/70"
                >
                  <div
                    class="flex items-center justify-between border-b border-gray-800 bg-gray-900/90 px-3 py-1.5 text-[10px] text-gray-400"
                  >
                    <div class="flex items-center gap-1.5 font-mono">
                      <span class="h-2 w-2 rounded-full bg-red-500/80" />
                      <span class="h-2 w-2 rounded-full bg-amber-500/80" />
                      <span class="h-2 w-2 rounded-full bg-emerald-500/80" />
                      <span class="ml-1">checkpoint.json</span>
                    </div>
                    <button
                      type="button"
                      class="cursor-pointer font-medium text-gray-300 transition-colors hover:text-white"
                      @click="
                        handleCopyText(
                          toPrettyJson(item.rawEntry),
                          '检查点数据',
                        )
                      "
                    >
                      复制 JSON
                    </button>
                  </div>
                  <pre
                    class="max-h-64 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-5 text-gray-200"
                    >{{ toPrettyJson(item.rawEntry) }}</pre
                  >
                </div>
              </details>
            </div>
          </div>
        </template>
      </div>
      <div
        v-if="activeTab === 'history'"
        class="flex flex-wrap items-center gap-2"
      >
        <template v-if="hasMoreHistory">
          <BaseButton
            :disabled="historyLoading"
            variant="secondary"
            @click="emit('load-history', 20)"
          >
            {{ historyLoading ? "加载中..." : "加载更多 (+20)" }}
          </BaseButton>
          <BaseButton
            :disabled="historyLoading"
            variant="secondary"
            @click="emit('load-history', 50)"
          >
            +50 条
          </BaseButton>
          <BaseButton
            :disabled="historyLoading"
            variant="secondary"
            @click="emit('load-history', 100)"
          >
            +100 条 (快速翻页)
          </BaseButton>
        </template>
        <span v-else class="text-xs text-gray-400 dark:text-dark-400">
          已加载全部历史记录 (共 {{ historyView.totalEntries }} 条)
        </span>
        <BaseButton
          v-if="isViewingBranch"
          :disabled="!canExecute"
          @click="emit('fork')"
        >
          从此检查点重新执行
        </BaseButton>
      </div>
    </div>
  </BaseDrawer>
</template>
