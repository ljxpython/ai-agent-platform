<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
  TrajectoryRecord,
  TrajectoryRecordKind,
  TrajectoryTurnGroup,
} from "../../trajectory/types";

const props = withDefaults(
  defineProps<{
    groups: TrajectoryTurnGroup[];
    selectedRecordId: string | null;
    filter?: "all" | "tools" | "errors";
    searchQuery?: string;
    allTurnsCollapsed?: boolean;
    allCallsCollapsed?: boolean;
  }>(),
  {
    filter: "all",
    searchQuery: "",
    allTurnsCollapsed: false,
    allCallsCollapsed: false,
  },
);

const emit = defineEmits<{
  select: [record: TrajectoryRecord];
}>();

// 单独轮次折叠状态
const collapsedTurnMap = ref<Record<number, boolean>>({});

watch(
  () => props.allTurnsCollapsed,
  (collapsed) => {
    const next: Record<number, boolean> = {};
    for (const g of props.groups) {
      next[g.turnIndex] = collapsed;
    }
    collapsedTurnMap.value = next;
  },
  { immediate: true },
);

function toggleTurn(turnIndex: number) {
  collapsedTurnMap.value[turnIndex] = !collapsedTurnMap.value[turnIndex];
}

function isTurnCollapsed(turnIndex: number): boolean {
  return Boolean(collapsedTurnMap.value[turnIndex]);
}

const filteredGroups = computed(() => {
  const query = props.searchQuery?.trim().toLowerCase();
  return props.groups
    .map((group) => {
      const records = group.records.filter((r) => {
        // Calls 折叠：隐藏 tool 和 subagent
        if (props.allCallsCollapsed && (r.kind === "tool" || r.kind === "subagent")) {
          return false;
        }
        // 类型筛选
        if (props.filter === "tools" && r.kind !== "tool" && r.kind !== "subagent") {
          return false;
        }
        if (props.filter === "errors" && r.status !== "error") {
          return false;
        }
        // 搜索框过滤
        if (query) {
          const matchName = r.name.toLowerCase().includes(query);
          const matchSummary = r.summary.toLowerCase().includes(query);
          const matchKind = r.kind.toLowerCase().includes(query);
          if (!matchName && !matchSummary && !matchKind) {
            return false;
          }
        }
        return true;
      });
      return {
        ...group,
        records,
      };
    })
    .filter((group) => group.records.length > 0 || isTurnCollapsed(group.turnIndex));
});

function getBadgeStyle(kind: TrajectoryRecordKind) {
  switch (kind) {
    case "system":
      return "bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-gray-300 border-gray-200 dark:border-dark-700";
    case "context":
      return "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900";
    case "user":
      return "bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-900";
    case "assistant":
      return "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-900";
    case "reasoning":
      return "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900";
    case "tool":
    case "subagent":
    default:
      return "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-900";
  }
}
</script>

<template>
  <div
    class="flex-1 overflow-y-auto bg-white font-sans text-xs select-none dark:bg-dark-900"
    data-testid="trajectory-ledger"
  >
    <!-- 空状态提示 -->
    <div
      v-if="filteredGroups.length === 0"
      class="flex flex-col items-center justify-center py-16 text-center text-xs text-gray-400 dark:text-dark-500"
    >
      <span>暂无匹配的轨迹事件</span>
    </div>

    <!-- 紧凑单行行内事件表格 -->
    <div
      v-for="group in filteredGroups"
      :key="group.turnIndex"
      class="relative"
    >
      <!-- Turn Header (可折叠) -->
      <div
        class="flex h-6 items-center justify-between border-b border-gray-100 bg-gray-50/70 px-2.5 font-mono text-[10px] text-gray-500 cursor-pointer select-none hover:bg-gray-100/80 dark:border-dark-800/80 dark:bg-dark-900/70 dark:text-dark-400 dark:hover:bg-dark-800"
        @click="toggleTurn(group.turnIndex)"
      >
        <div class="flex items-center gap-1.5 font-semibold text-gray-700 dark:text-dark-200">
          <span
            class="inline-block transition-transform duration-150 text-[8px]"
            :class="{ '-rotate-90': isTurnCollapsed(group.turnIndex) }"
          >▼</span>
          <span>Turn {{ group.turnIndex }}</span>
        </div>
        <div class="text-[9px] text-gray-400 dark:text-dark-500">
          {{ group.records.length }} 步
        </div>
      </div>

      <!-- Turn 内容列表（受折叠控制） -->
      <div v-show="!isTurnCollapsed(group.turnIndex)">
        <div
          v-for="(record, recordIdx) in group.records"
          :key="record.id"
          data-testid="trajectory-record-row"
          class="group relative flex h-8 items-center border-b border-gray-100 pr-3 transition-colors cursor-pointer dark:border-dark-800/80"
          :class="[
            selectedRecordId === record.id
              ? 'bg-blue-50/70 dark:bg-blue-950/40'
              : 'hover:bg-gray-50/90 dark:hover:bg-dark-800/50',
          ]"
          @click="emit('select', record)"
        >
          <!-- 选中态左侧 3px 指示竖条 -->
          <div
            v-if="selectedRecordId === record.id"
            class="absolute inset-y-0 left-0 w-0.75 bg-blue-600 dark:bg-blue-400 z-10"
          />

          <!-- 左侧纵向贯穿树状轨道 (Turn Rail) -->
          <div class="relative flex h-full w-8 shrink-0 items-center justify-center">
            <!-- 纵向贯穿灰线 (Turn Rail) -->
            <div
              class="absolute top-0 bottom-0 left-4 w-[1.5px] bg-gray-200/90 dark:bg-dark-700"
              :class="{
                'top-1/2': recordIdx === 0,
                'bottom-1/2': recordIdx === group.records.length - 1,
              }"
            />

            <!-- 树状节点圆点 (Node Dot) -->
            <div
              class="relative z-1 h-2 w-2 rounded-full border border-white bg-gray-300 dark:border-dark-900 dark:bg-dark-500 group-hover:bg-blue-500"
              :class="{
                '!bg-blue-600 !border-blue-200 dark:!bg-blue-400': selectedRecordId === record.id,
                '!bg-red-500': record.status === 'error',
              }"
            />
          </div>

          <!-- 类别徽章 (Badge) -->
          <div class="w-18 shrink-0 pl-1">
            <span
              class="inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border leading-none font-mono"
              :class="getBadgeStyle(record.kind)"
            >
              {{ record.kind }}
            </span>
          </div>

          <!-- 单行摘要内容 (Summary) -->
          <div class="min-w-0 flex-1 px-2 font-mono text-[11px] text-gray-700 truncate dark:text-gray-200">
            <span
              v-if="record.kind === 'tool'"
              class="font-semibold text-gray-900 dark:text-white mr-1"
            >
              {{ record.name }}
            </span>
            <span class="text-gray-600 dark:text-dark-300">
              {{ record.summary }}
            </span>
          </div>

          <!-- 右侧耗时与状态 -->
          <div class="flex shrink-0 items-center gap-1.5 font-mono text-[10px] text-gray-400 dark:text-dark-400">
            <span
              v-if="record.status === 'error'"
              class="rounded bg-red-100 px-1 py-0.2 text-[9px] font-bold text-red-600 dark:bg-red-950 dark:text-red-300"
            >
              ERR
            </span>
            <span
              v-else-if="record.durationMs"
              class="text-gray-400 dark:text-dark-500"
            >
              {{ record.durationMs }}ms
            </span>
            <span
              v-else-if="record.status === 'running'"
              class="h-1.5 w-1.5 rounded-full bg-blue-500 animate-ping"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
