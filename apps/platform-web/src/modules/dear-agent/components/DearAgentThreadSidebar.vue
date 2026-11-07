<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import type {
  ChatThreadStatusFilter,
  ChatThreadSummaryGroup,
} from "../thread-list-view-model";

type ThreadStatusFilterOption = {
  value: ChatThreadStatusFilter;
  label: string;
};

const props = defineProps<{
  showContextBar: boolean;
  targetText: string;
  targetTypeText: string;
  search: string;
  statusFilter: ChatThreadStatusFilter;
  filters: readonly ThreadStatusFilterOption[];
  loading: boolean;
  threadCount: number;
  filteredCount: number;
  canStartThread: boolean;
  activeThreadId: string;
  deletingThreadId: string;
  groups: ChatThreadSummaryGroup[];
  summarizingThreadId?: string;
  currentPage?: number;
  totalPages?: number;
  totalCount?: number;
  hasMore?: boolean;
  canDelete?: boolean;
  canDeleteThread?: (threadId: string) => boolean;
  canEditThread?: (threadId: string) => boolean;
  canSummarizeThread?: (threadId: string) => boolean;
}>();

const emit = defineEmits<{
  "update:search": [value: string];
  "update:statusFilter": [value: ChatThreadStatusFilter];
  "start-new-thread": [];
  "select-thread": [threadId: string];
  "delete-thread": [threadId: string];
  "batch-delete": [threadIds: string[]];
  "rename-thread": [threadId: string, newTitle: string];
  "ai-summarize-title": [threadId: string];
  collapse: [];
  "page-change": [page: number];
  "load-more": [];
}>();

const editingThreadId = ref<string | null>(null);
const editingTitle = ref("");
const isBatchMode = ref(false);
const selectedThreadIds = ref<string[]>([]);

const deletableThreadIds = computed(() => {
  return props.groups
    .flatMap((g) => g.items.map((i) => i.id))
    .filter((id) => (props.canDeleteThread ? props.canDeleteThread(id) : true));
});

const isAllSelected = computed(() => {
  if (deletableThreadIds.value.length === 0) return false;
  return deletableThreadIds.value.every((id) =>
    selectedThreadIds.value.includes(id),
  );
});

function toggleBatchMode() {
  isBatchMode.value = !isBatchMode.value;
  selectedThreadIds.value = [];
}

function toggleSelectThread(threadId: string) {
  if (props.canDeleteThread && !props.canDeleteThread(threadId)) return;
  const index = selectedThreadIds.value.indexOf(threadId);
  if (index >= 0) {
    selectedThreadIds.value.splice(index, 1);
  } else {
    selectedThreadIds.value.push(threadId);
  }
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedThreadIds.value = [];
  } else {
    selectedThreadIds.value = [...deletableThreadIds.value];
  }
}

function handleRequestBatchDelete() {
  if (selectedThreadIds.value.length === 0) return;
  emit("batch-delete", [...selectedThreadIds.value]);
}

defineExpose({
  exitBatchMode: () => {
    isBatchMode.value = false;
    selectedThreadIds.value = [];
  },
});

function startRename(item: { id: string; title: string }) {
  editingThreadId.value = item.id;
  editingTitle.value = item.title;
}

function cancelRename() {
  editingThreadId.value = null;
  editingTitle.value = "";
}

function confirmRename(threadId: string) {
  const nextTitle = editingTitle.value.trim();
  if (nextTitle) {
    emit("rename-thread", threadId, nextTitle);
  }
  editingThreadId.value = null;
  editingTitle.value = "";
}

const searchModel = computed({
  get: () => props.search,
  set: (value: string) => emit("update:search", value),
});

const inputPage = ref(String(props.currentPage || 1));

watch(
  () => props.currentPage,
  (newPage) => {
    inputPage.value = String(newPage || 1);
  },
);

function jumpToPage() {
  const parsed = parseInt(inputPage.value, 10);
  const max = props.totalPages || 1;
  if (Number.isNaN(parsed) || parsed < 1) {
    inputPage.value = String(props.currentPage || 1);
    return;
  }
  const target = Math.min(Math.max(1, parsed), max);
  inputPage.value = String(target);
  if (target !== (props.currentPage || 1)) {
    emit("page-change", target);
  }
}
</script>

<template>
  <aside
    aria-label="对话列表"
    class="w-72 lg:w-80 border-r border-gray-200 dark:border-dark-800 bg-white dark:bg-dark-900 flex flex-col h-full shrink-0"
  >
    <!-- Header: Search and New Thread (方案A: 工业级三段式布局) -->
    <div
      class="px-3 py-2.5 border-b border-gray-200 dark:border-dark-800 shrink-0 space-y-2"
    >
      <!-- Row 1: 业务标头与工具组 -->
      <div class="flex items-center justify-between h-7">
        <div class="flex items-center gap-1.5 min-w-0">
          <span
            class="text-xs font-semibold text-gray-800 dark:text-gray-200 tracking-tight"
            >历史会话</span
          >
          <span
            v-if="totalCount !== undefined || threadCount !== undefined"
            class="inline-flex items-center rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-dark-800 dark:text-dark-400"
          >
            {{ totalCount ?? threadCount }}
          </span>
        </div>
        <div class="flex items-center gap-0.5 shrink-0">
          <!-- 批量模式切换按钮 -->
          <button
            type="button"
            class="inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium transition-colors"
            :class="
              isBatchMode
                ? 'bg-primary-50 text-primary-600 dark:bg-primary-950/60 dark:text-primary-300 font-semibold ring-1 ring-primary-500/20'
                : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white'
            "
            :title="isBatchMode ? '退出批量管理' : '批量管理会话'"
            @click="toggleBatchMode"
          >
            <BaseIcon :name="isBatchMode ? 'check' : 'folder'" size="xs" />
            <span>{{ isBatchMode ? "退出" : "批量" }}</span>
          </button>
          <!-- 新建会话按钮 -->
          <button
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-800 disabled:opacity-40 disabled:cursor-not-allowed dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white transition-colors"
            :disabled="!canStartThread"
            title="新建会话"
            @click="emit('start-new-thread')"
          >
            <BaseIcon name="chat" size="xs" />
          </button>
          <!-- 收起按钮 -->
          <button
            type="button"
            class="inline-flex h-7 w-7 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white transition-colors"
            title="收起历史会话"
            @click="emit('collapse')"
          >
            <BaseIcon name="chevron-left" size="xs" />
          </button>
        </div>
      </div>

      <!-- Row 2: 全宽紧凑搜索栏 -->
      <div class="relative w-full flex items-center">
        <BaseIcon
          name="search"
          size="xs"
          class="pointer-events-none absolute left-2.5 text-gray-400 dark:text-dark-400"
        />
        <input
          v-model="searchModel"
          type="text"
          placeholder="搜索会话..."
          class="h-8 w-full rounded-lg border border-gray-200/90 bg-gray-50/70 pl-8 pr-7 text-xs text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-primary-500/30 dark:border-dark-700/80 dark:bg-dark-800/60 dark:text-gray-100 dark:placeholder:text-dark-400 dark:focus:border-primary-400 dark:focus:bg-dark-900 transition-colors"
        />
        <button
          v-if="searchModel"
          type="button"
          class="absolute right-2 flex h-4 w-4 items-center justify-center rounded-full text-gray-400 hover:bg-gray-200 hover:text-gray-600 dark:hover:bg-dark-700 dark:hover:text-gray-200 transition-colors"
          title="清空搜索"
          @click="searchModel = ''"
        >
          <BaseIcon name="x" size="xs" />
        </button>
      </div>

      <!-- Row 3: 单行滑动状态分段胶囊（永不断行，整齐划一） -->
      <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-0.5">
        <button
          v-for="filter in filters"
          :key="filter.value"
          type="button"
          class="shrink-0 rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors"
          :class="
            statusFilter === filter.value
              ? 'bg-primary-50 text-primary-700 font-semibold ring-1 ring-primary-500/20 dark:bg-primary-950/50 dark:text-primary-300 dark:ring-primary-400/20'
              : 'text-gray-500 hover:bg-gray-100/80 hover:text-gray-800 dark:text-dark-400 dark:hover:bg-dark-800/80 dark:hover:text-gray-200'
          "
          @click="emit('update:statusFilter', filter.value)"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>

    <!-- Scrollable Thread List -->
    <div class="flex-1 overflow-y-auto p-3 space-y-4">
      <div v-if="loading && threadCount === 0" class="space-y-3">
        <div
          v-for="index in 4"
          :key="index"
          class="pw-panel-muted h-20 animate-pulse rounded-lg"
        />
      </div>

      <div
        v-else-if="threadCount === 0"
        class="p-4 text-center text-sm text-gray-500 dark:text-dark-400"
      >
        无会话记录，发送消息将自动创建。
      </div>

      <div
        v-else-if="filteredCount === 0"
        class="p-4 text-center text-sm text-gray-500 dark:text-dark-400"
      >
        没有匹配的会话。
      </div>

      <div v-else class="space-y-4">
        <div v-for="group in groups" :key="group.key" class="space-y-1.5">
          <div
            class="px-2 text-[10px] font-bold uppercase tracking-wider text-gray-400 dark:text-dark-500"
          >
            {{ group.label }}
          </div>

          <div class="space-y-1">
            <div
              v-for="item in group.items"
              :key="item.id"
              class="group relative"
            >
              <!-- 编辑模式 -->
              <div
                v-if="editingThreadId === item.id"
                class="w-full rounded-lg p-1.5 border border-primary-500 bg-white dark:bg-dark-800 shadow-sm flex items-center gap-1.5"
                @click.stop
              >
                <input
                  v-model="editingTitle"
                  type="text"
                  class="flex-1 min-w-0 text-xs px-2 py-1 rounded border border-gray-300 dark:border-dark-600 bg-transparent text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary-500 font-medium"
                  placeholder="会话标题"
                  autofocus
                  @keydown.enter.prevent="confirmRename(item.id)"
                  @keydown.esc.prevent="cancelRename"
                />
                <button
                  type="button"
                  class="p-1 rounded text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-950/50"
                  title="确认"
                  @click.stop="confirmRename(item.id)"
                >
                  <BaseIcon name="check" size="xs" />
                </button>
                <button
                  type="button"
                  class="p-1 rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-700"
                  title="取消"
                  @click.stop="cancelRename"
                >
                  <BaseIcon name="x" size="xs" />
                </button>
              </div>

              <!-- 常规展示模式 -->
              <template v-else>
                <div
                  class="w-full rounded-lg px-2.5 py-2 text-left transition-colors flex items-center gap-2 cursor-pointer"
                  :class="[
                    isBatchMode && selectedThreadIds.includes(item.id)
                      ? 'bg-primary-50/90 dark:bg-primary-950/50 border border-primary-300 dark:border-primary-700'
                      : item.id === activeThreadId
                        ? 'bg-primary-50/80 dark:bg-primary-950/40 border border-primary-100/80 dark:border-primary-900/50'
                        : 'border border-transparent hover:bg-gray-100/80 dark:hover:bg-dark-800/60',
                    isBatchMode ? 'pr-2' : 'pr-14',
                  ]"
                  @click="
                    isBatchMode
                      ? toggleSelectThread(item.id)
                      : emit('select-thread', item.id)
                  "
                >
                  <!-- 批量模式下的复选框 -->
                  <div
                    v-if="isBatchMode"
                    class="flex items-center justify-center shrink-0"
                    @click.stop="toggleSelectThread(item.id)"
                  >
                    <input
                      type="checkbox"
                      :checked="selectedThreadIds.includes(item.id)"
                      :disabled="
                        canDeleteThread ? !canDeleteThread(item.id) : false
                      "
                      class="h-3.5 w-3.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-dark-600 dark:bg-dark-800 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                    />
                  </div>

                  <div class="flex-1 min-w-0 flex flex-col gap-0.5">
                    <div class="flex items-start justify-between gap-2">
                      <div
                        class="truncate text-xs font-medium"
                        :class="
                          item.id === activeThreadId
                            ? 'text-primary-900 dark:text-primary-100 font-semibold'
                            : 'text-gray-800 dark:text-gray-200'
                        "
                      >
                        {{ item.title }}
                      </div>
                    </div>

                    <div
                      class="flex items-center justify-between text-[10px] text-gray-400 dark:text-dark-500 mt-1"
                    >
                      <span>{{ item.time }}</span>
                      <div class="flex items-center gap-1">
                        <span
                          v-if="item.status === 'interrupted'"
                          class="w-1.5 h-1.5 rounded-full bg-amber-500"
                          title="等待确认"
                        />
                        <span
                          v-else-if="item.status === 'error'"
                          class="w-1.5 h-1.5 rounded-full bg-red-500"
                          title="错误"
                        />
                        <span
                          v-else-if="item.status === 'busy'"
                          class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"
                          title="运行中"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-if="!isBatchMode"
                  class="absolute right-2 top-2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition"
                  :class="summarizingThreadId === item.id ? '!opacity-100' : ''"
                >
                  <button
                    type="button"
                    class="rounded p-1 text-gray-400 transition hover:bg-purple-50 hover:text-purple-600 dark:hover:bg-purple-950/40 dark:hover:text-purple-300 disabled:opacity-50"
                    :class="
                      summarizingThreadId === item.id
                        ? '!opacity-100 text-purple-600 dark:text-purple-400'
                        : ''
                    "
                    :disabled="
                      summarizingThreadId === item.id ||
                      (canSummarizeThread
                        ? !canSummarizeThread(item.id)
                        : canEditThread
                          ? !canEditThread(item.id)
                          : false)
                    "
                    :aria-label="
                      summarizingThreadId === item.id
                        ? '正在智能生成标题...'
                        : `AI智能生成标题：${item.title}`
                    "
                    :title="
                      summarizingThreadId === item.id
                        ? '正在智能生成标题...'
                        : 'AI 智能生成标题'
                    "
                    @click.stop="emit('ai-summarize-title', item.id)"
                  >
                    <BaseIcon
                      :name="
                        summarizingThreadId === item.id ? 'refresh' : 'sparkle'
                      "
                      size="xs"
                      :class="{
                        'animate-spin': summarizingThreadId === item.id,
                      }"
                    />
                  </button>

                  <button
                    type="button"
                    class="rounded p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-700 dark:hover:text-gray-200"
                    :aria-label="`重命名会话：${item.title}`"
                    title="重命名会话"
                    :disabled="canEditThread ? !canEditThread(item.id) : false"
                    @click.stop="startRename(item)"
                  >
                    <BaseIcon name="pencil" size="xs" />
                  </button>

                  <button
                    v-if="
                      canDeleteThread ? canDeleteThread(item.id) : canDelete
                    "
                    type="button"
                    class="rounded p-1 text-gray-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                    :class="deletingThreadId === item.id ? 'opacity-100' : ''"
                    :disabled="deletingThreadId === item.id"
                    :aria-label="`删除会话：${item.title}`"
                    title="删除会话"
                    @click.stop="emit('delete-thread', item.id)"
                  >
                    <BaseIcon name="x" size="xs" />
                  </button>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量管理底部悬浮操作条 -->
    <div
      v-if="isBatchMode"
      class="border-t border-gray-200 dark:border-dark-800 bg-white/95 dark:bg-dark-900/95 px-3 py-2 flex items-center justify-between shrink-0 shadow-md backdrop-blur-xs transition-all z-20"
    >
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400"
          @click="toggleSelectAll"
        >
          {{ isAllSelected ? "取消全选" : "全选" }}
        </button>
        <span class="text-[11px] text-gray-500 dark:text-dark-400">
          已选 {{ selectedThreadIds.length }} 项
        </span>
      </div>
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          class="px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-dark-700 dark:text-dark-300 dark:hover:bg-dark-800 transition-colors"
          @click="toggleBatchMode"
        >
          取消
        </button>
        <button
          type="button"
          class="px-2.5 py-1 text-xs rounded bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed shadow-2xs transition-colors"
          :disabled="selectedThreadIds.length === 0"
          @click="handleRequestBatchDelete"
        >
          删除 ({{ selectedThreadIds.length }})
        </button>
      </div>
    </div>

    <!-- 极简高质感微型分页器 (Compact Pagination) -->
    <div
      v-if="
        currentPage !== undefined ||
        hasMore ||
        (totalCount !== undefined && totalCount > 0)
      "
      class="border-t border-gray-100 dark:border-dark-800 px-3 py-2 shrink-0 bg-gray-50/70 dark:bg-dark-900/60 flex items-center justify-between font-mono text-[11px] text-gray-500 select-none"
    >
      <div
        class="flex items-center gap-1 text-gray-400 dark:text-dark-400 min-w-0"
      >
        <span class="truncate">
          共
          <strong class="text-gray-700 dark:text-dark-200 font-semibold">{{
            totalCount !== undefined ? totalCount : threadCount
          }}</strong>
          条<template v-if="filteredCount !== threadCount">
            (筛选 {{ filteredCount }} 条)</template
          >
        </span>
      </div>

      <div class="flex items-center gap-1 shrink-0">
        <!-- 首页 (跳转第一页) -->
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded border border-gray-200 bg-white text-gray-600 shadow-2xs hover:bg-gray-50 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors text-xs font-bold leading-none"
          :disabled="(currentPage || 1) <= 1 || loading"
          title="首页"
          aria-label="首页"
          @click="emit('page-change', 1)"
        >
          «
        </button>

        <!-- 上一页 -->
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded border border-gray-200 bg-white text-gray-600 shadow-2xs hover:bg-gray-50 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors"
          :disabled="(currentPage || 1) <= 1 || loading"
          title="上一页"
          aria-label="上一页"
          @click="emit('page-change', (currentPage || 1) - 1)"
        >
          <BaseIcon name="chevron-left" size="xs" />
        </button>

        <!-- 当前页输入框 / 总页数 -->
        <div class="flex items-center gap-1 px-0.5">
          <input
            v-model="inputPage"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            class="h-6 w-8 rounded border border-blue-200 bg-blue-50/70 px-0.5 text-center font-mono text-[11px] font-bold text-blue-700 shadow-2xs outline-none focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-300 dark:focus:bg-dark-800 transition-colors"
            title="输入页码回车跳转"
            aria-label="输入页码跳转"
            @keydown.enter="jumpToPage"
            @blur="jumpToPage"
          />
          <span class="text-gray-400 dark:text-dark-500"
            >/ {{ totalPages || 1 }}</span
          >
        </div>

        <!-- 下一页 -->
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded border border-gray-200 bg-white text-gray-600 shadow-2xs hover:bg-gray-50 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors"
          :disabled="
            (totalPages ? (currentPage || 1) >= totalPages : !hasMore) ||
            loading
          "
          title="下一页"
          aria-label="下一页"
          @click="emit('page-change', (currentPage || 1) + 1)"
        >
          <BaseIcon name="chevron-right" size="xs" />
        </button>

        <!-- 末页 (跳转最后一页) -->
        <button
          type="button"
          class="flex h-6 w-6 items-center justify-center rounded border border-gray-200 bg-white text-gray-600 shadow-2xs hover:bg-gray-50 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors text-xs font-bold leading-none"
          :disabled="
            (totalPages ? (currentPage || 1) >= totalPages : !hasMore) ||
            loading
          "
          title="末页"
          aria-label="末页"
          @click="emit('page-change', totalPages || 1)"
        >
          »
        </button>
      </div>
    </div>
  </aside>
</template>
