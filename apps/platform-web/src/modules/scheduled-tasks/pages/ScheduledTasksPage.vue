<script setup lang="ts">
import { computed, ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import ScheduledTaskCard from "../components/ScheduledTaskCard.vue";
import ScheduledTaskFormDrawer from "../components/ScheduledTaskFormDrawer.vue";
import ScheduledTaskRunsDrawer from "../components/ScheduledTaskRunsDrawer.vue";
import { useScheduledTasks } from "../composables/useScheduledTasks";
import type { ScheduledTask } from "../types";

const { activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();

const canWrite = computed(() =>
  can("project.runtime.write", activeProjectId.value),
);

const {
  items: rawItems,
  total,
  page,
  pageSize,
  filterEnabled,
  loading,
  error,
  triggeringTaskId,
  loadTasks,
  togglePause,
  remove,
  trigger,
  handleTaskSaved,
} = useScheduledTasks(activeProjectId);

const searchQuery = ref("");
const displayItems = computed(() => {
  if (!searchQuery.value.trim()) return rawItems.value;
  const q = searchQuery.value.trim().toLowerCase();
  return rawItems.value.filter(
    (t) =>
      t.title.toLowerCase().includes(q) ||
      t.agent_key.toLowerCase().includes(q),
  );
});

// 统计指标（精准区分活跃调度、人工暂停与单次耗尽）
const activeCount = computed(
  () => rawItems.value.filter((t) => t.schedule_status === "active").length,
);
const pausedCount = computed(
  () => rawItems.value.filter((t) => t.schedule_status === "paused").length,
);
const exhaustedCount = computed(
  () => rawItems.value.filter((t) => t.schedule_status === "exhausted").length,
);

// 抽屉状态
const showFormDrawer = ref(false);
const editingTask = ref<ScheduledTask | null>(null);

const showRunsDrawer = ref(false);
const currentRunsTask = ref<ScheduledTask | null>(null);

// 浮动 Toast 状态（彻底解决普通文档流撑开导致的页面垂直抖动）
const toastMessage = ref<string>("");
let toastTimer: ReturnType<typeof setTimeout> | null = null;

function showToast(msg: string) {
  toastMessage.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastMessage.value = "";
  }, 4000);
}

function openCreate() {
  editingTask.value = null;
  showFormDrawer.value = true;
}

function openEdit(task: ScheduledTask) {
  editingTask.value = task;
  showFormDrawer.value = true;
}

function openRuns(task: ScheduledTask) {
  currentRunsTask.value = task;
  showRunsDrawer.value = true;
}

function onTaskSaved(saved: ScheduledTask) {
  handleTaskSaved(saved);
  showFormDrawer.value = false;
  showToast(`定时任务「${saved.title}」已成功保存！`);
}

function onTriggerTask(task: ScheduledTask) {
  trigger(task, (runId) => {
    showToast(`任务已成功派发！Run ID: ${runId}`);
  });
}
</script>

<template>
  <div class="space-y-6">
    <!-- 顶栏：标题与操作 -->
    <PageHeader
      title="定时任务"
      description="配置并托管周期性或一次性自动化 Agent 调度任务，支持 HMAC 安全代行与无人值守守护"
    >
      <template #actions>
        <BaseButton
          variant="primary"
          :disabled="!canWrite"
          :title="
            !canWrite ? '需要项目运行时写入权限 (project.runtime.write)' : ''
          "
          class="rounded-xl shadow-xs px-4"
          @click="openCreate"
        >
          <BaseIcon name="plus" size="xs" class="mr-1.5" />
          <span>新建任务</span>
        </BaseButton>
      </template>
    </PageHeader>

    <!-- 错误横幅（仅在发生不可恢复的接口错误时呈现） -->
    <StateBanner
      v-if="error"
      variant="danger"
      title="操作失败"
      :description="error"
    />

    <!-- 现代化统计指标看板 (Metric Cards) -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4.5">
      <!-- 指标卡 1：总任务规模 -->
      <div
        class="rounded-2xl border border-border/70 bg-surface/90 p-5 shadow-xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover hover:shadow-md dark:border-dark-700/80 dark:bg-dark-900/80 flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 text-primary border border-primary/20 shadow-xs"
          >
            <BaseIcon name="overview" size="md" />
          </div>
          <span
            class="inline-flex items-center rounded-full bg-surface-subtle px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground border border-border/50"
          >
            全部托管
          </span>
        </div>
        <div class="mt-4">
          <div
            class="text-3xl font-extrabold tracking-tight font-mono text-foreground"
          >
            {{ total }}
          </div>
          <div
            class="mt-2.5 flex items-center justify-between text-xs text-muted-foreground"
          >
            <span class="font-medium">总配置任务数</span>
            <span
              v-if="exhaustedCount > 0"
              class="text-[11px] text-primary font-mono"
            >
              含 {{ exhaustedCount }} 项单次完成
            </span>
            <span v-else class="text-[11px] text-muted-foreground/80">
              持续托管规格
            </span>
          </div>
        </div>
      </div>

      <!-- 指标卡 2：运行监听中 -->
      <div
        class="rounded-2xl border border-border/70 bg-surface/90 p-5 shadow-xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover hover:shadow-md dark:border-dark-700/80 dark:bg-dark-900/80 flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/15 to-emerald-500/5 text-emerald-500 border border-emerald-500/20 shadow-xs"
          >
            <BaseIcon name="activity" size="md" />
          </div>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
          >
            <span
              class="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"
            />
            <span>监控中</span>
          </span>
        </div>
        <div class="mt-4">
          <div
            class="text-3xl font-extrabold tracking-tight font-mono text-emerald-600 dark:text-emerald-400"
          >
            {{ activeCount }}
          </div>
          <div
            class="mt-2.5 flex items-center justify-between text-xs text-muted-foreground"
          >
            <span class="font-medium">周期调度就绪</span>
            <span class="text-[11px] text-muted-foreground/80">
              无人值守守护
            </span>
          </div>
        </div>
      </div>

      <!-- 指标卡 3：已休眠暂停 -->
      <div
        class="rounded-2xl border border-border/70 bg-surface/90 p-5 shadow-xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover hover:shadow-md dark:border-dark-700/80 dark:bg-dark-900/80 flex flex-col justify-between"
      >
        <div class="flex items-center justify-between">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-500/15 to-amber-500/5 text-amber-500 border border-amber-500/20 shadow-xs"
          >
            <BaseIcon name="lock" size="md" />
          </div>
          <span
            class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium border"
            :class="
              pausedCount > 0
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                : 'bg-surface-subtle text-muted-foreground border-border/50'
            "
          >
            {{ pausedCount > 0 ? "已挂起" : "无暂停" }}
          </span>
        </div>
        <div class="mt-4">
          <div
            class="text-3xl font-extrabold tracking-tight font-mono text-amber-500"
          >
            {{ pausedCount }}
          </div>
          <div
            class="mt-2.5 flex items-center justify-between text-xs text-muted-foreground"
          >
            <span class="font-medium">人工休眠暂停</span>
            <span
              v-if="exhaustedCount > 0"
              class="text-[11px] text-muted-foreground font-mono"
            >
              单次已归档: {{ exhaustedCount }}
            </span>
            <span v-else class="text-[11px] text-muted-foreground/80">
              随时可恢复
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 现代化控制过滤栏 (Control Bar) -->
    <div
      class="flex flex-wrap items-center justify-between gap-4 p-3 rounded-2xl border border-border/70 bg-surface/90 shadow-xs backdrop-blur-xs dark:bg-dark-900/80"
    >
      <div class="flex items-center gap-2">
        <div class="relative w-72">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索任务标题或 Agent 名称..."
            class="w-full h-9 pl-3.5 pr-8 text-xs rounded-xl border border-border/80 bg-surface-subtle transition focus:border-primary focus:ring-2 focus:ring-primary/20 dark:bg-dark-800"
          />
        </div>
        <BaseButton
          variant="secondary"
          size="sm"
          :disabled="loading"
          class="rounded-xl shadow-xs"
          @click="loadTasks"
        >
          <BaseIcon
            name="refresh"
            size="xs"
            :class="loading ? 'animate-spin' : ''"
            class="mr-1.5"
          />
          <span>刷新</span>
        </BaseButton>
      </div>

      <!-- 状态分段选择器 -->
      <div
        class="flex rounded-xl bg-surface-subtle p-1 border border-border/60 text-xs"
      >
        <button
          type="button"
          class="px-3 py-1 rounded-lg font-medium transition-all"
          :class="
            filterEnabled === undefined
              ? 'bg-surface text-foreground shadow-xs font-semibold'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="filterEnabled = undefined"
        >
          全部
        </button>
        <button
          type="button"
          class="px-3 py-1 rounded-lg font-medium transition-all"
          :class="
            filterEnabled === true
              ? 'bg-surface text-foreground shadow-xs font-semibold'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="filterEnabled = true"
        >
          已启用
        </button>
        <button
          type="button"
          class="px-3 py-1 rounded-lg font-medium transition-all"
          :class="
            filterEnabled === false
              ? 'bg-surface text-foreground shadow-xs font-semibold'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="filterEnabled = false"
        >
          已暂停
        </button>
      </div>
    </div>

    <!-- 卡片网格列表 -->
    <div
      v-if="loading && displayItems.length === 0"
      class="py-24 text-center text-xs text-muted-foreground"
    >
      <BaseIcon
        name="refresh"
        size="lg"
        class="mx-auto mb-2 animate-spin text-primary"
      />
      <span>加载定时调度任务中...</span>
    </div>

    <div
      v-else-if="displayItems.length === 0"
      class="py-24 text-center space-y-3.5 rounded-2xl border border-dashed border-border/80 bg-surface-subtle/60 p-8"
    >
      <div
        class="flex h-12 w-12 mx-auto items-center justify-center rounded-2xl bg-muted text-muted-foreground"
      >
        <BaseIcon name="activity" size="md" />
      </div>
      <div class="text-sm font-semibold text-foreground">暂无定时任务</div>
      <p class="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
        当前项目未配置任何定时调度任务。您可以创建周期性或单次触发的智能体，系统将自动代行执行。
      </p>
      <div class="pt-1">
        <BaseButton
          v-if="canWrite"
          variant="primary"
          size="sm"
          class="rounded-xl shadow-xs"
          @click="openCreate"
        >
          创建首个定时任务
        </BaseButton>
      </div>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
      <ScheduledTaskCard
        v-for="task in displayItems"
        :key="task.id"
        :task="task"
        :can-write="canWrite"
        :triggering="triggeringTaskId === task.id"
        @edit="openEdit"
        @toggle-pause="togglePause"
        @trigger="onTriggerTask"
        @view-runs="openRuns"
        @delete="remove"
      />
    </div>

    <!-- 分页条 -->
    <PaginationBar
      v-if="total > pageSize"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      :disabled="loading"
    />

    <!-- 创建/编辑双栏抽屉 -->
    <ScheduledTaskFormDrawer
      :show="showFormDrawer"
      :project-id="activeProjectId"
      :task="editingTask"
      @close="showFormDrawer = false"
      @saved="onTaskSaved"
    />

    <!-- 运行历史记录抽屉 -->
    <ScheduledTaskRunsDrawer
      :show="showRunsDrawer"
      :project-id="activeProjectId"
      :task="currentRunsTask"
      @close="showRunsDrawer = false"
    />

    <!-- 全局浮动反馈微通知 (Toast Notification - 彻底消除普通文档流撑开引起的CLS抖动) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-4 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 -translate-y-2 scale-95"
      >
        <div
          v-if="toastMessage"
          class="fixed top-6 right-6 z-[100] flex items-center gap-3 rounded-2xl border border-emerald-500/30 bg-surface/95 px-4.5 py-3 shadow-2xl backdrop-blur-md dark:border-emerald-500/40 dark:bg-dark-900/95 max-w-md ring-1 ring-black/5"
        >
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-500"
          >
            <BaseIcon name="check" size="sm" />
          </div>
          <div class="text-xs font-medium text-foreground leading-snug">
            {{ toastMessage }}
          </div>
          <button
            type="button"
            class="ml-auto text-muted-foreground hover:text-foreground p-1 rounded-lg transition-colors"
            title="关闭通知"
            @click="toastMessage = ''"
          >
            <BaseIcon name="x" size="xs" />
          </button>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
