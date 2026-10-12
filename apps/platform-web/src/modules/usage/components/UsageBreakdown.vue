<script setup lang="ts">
import { computed } from "vue";
import type {
  Breakdown,
  GroupBy,
  RankBy,
  UsageGroup,
  UsageMetrics,
} from "../types";
import { formatTokenNumber, formatDashboardCost } from "../view-model";

const props = defineProps<{
  breakdown: Breakdown;
  isPlatformScope: boolean;
}>();

const emit = defineEmits<{
  "update:group_by": [group: GroupBy];
  "update:rank_by": [rank: RankBy];
  drilldown: [item: UsageGroup];
}>();

// 计算当前排行的最大指标值（作为 100% 基准）
const maxMetricValue = computed(() => {
  let max = 0;
  for (const item of props.breakdown.items) {
    const val = getMetricNumeric(item);
    if (val > max) max = val;
  }
  return max > 0 ? max : 1;
});

function getMetricNumeric(item: UsageMetrics): number {
  if (props.breakdown.rank_by === "known_cost_usd") {
    return Number(
      item.cost?.estimated_cost_usd ?? item.cost?.known_cost_usd ?? 0,
    );
  }
  if (props.breakdown.rank_by === "observed_call_count") {
    return item.coverage?.observed_call_count ?? 0;
  }
  // 默认 known_total_tokens
  return item.tokens?.total_tokens ?? item.known_tokens?.total_tokens ?? 0;
}

function formatMetricDisplay(item: UsageMetrics): string {
  if (props.breakdown.rank_by === "known_cost_usd") {
    return formatDashboardCost(item.cost).display;
  }
  if (props.breakdown.rank_by === "observed_call_count") {
    return `${item.coverage?.observed_call_count ?? 0} 次调用`;
  }
  return `${formatTokenNumber(item.tokens?.total_tokens ?? item.known_tokens?.total_tokens)} Tokens`;
}

function handleItemClick(item: UsageGroup) {
  emit("drilldown", item);
}
</script>

<template>
  <div
    class="pw-breakdown-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm"
    data-testid="usage-breakdown-panel"
  >
    <!-- 头部维度与指标切换 -->
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-4 dark:border-dark-800"
    >
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
          用量分解与排行
        </h3>
        <p class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
          点击具体分类可快速反填筛选栏下钻深入分析
        </p>
      </div>

      <div class="flex items-center gap-2">
        <!-- 分组维度下拉 -->
        <select
          :value="breakdown.group_by"
          class="h-7.5 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
          @change="
            emit(
              'update:group_by',
              ($event.target as HTMLSelectElement).value as GroupBy,
            )
          "
        >
          <option value="model">按模型分解</option>
          <option value="agent">按 Agent 分解</option>
          <option v-if="isPlatformScope" value="project">按项目分解</option>
          <option value="purpose">按业务用途分解</option>
          <option value="scope">按调用层级分解</option>
        </select>

        <!-- 排行依据下拉 -->
        <select
          :value="breakdown.rank_by"
          class="h-7.5 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
          @change="
            emit(
              'update:rank_by',
              ($event.target as HTMLSelectElement).value as RankBy,
            )
          "
        >
          <option value="known_total_tokens">按 Token 总量</option>
          <option value="known_cost_usd">按估算成本 (USD)</option>
          <option value="observed_call_count">按调用次数</option>
        </select>
      </div>
    </div>

    <!-- 主体排行列表 -->
    <div class="mt-4 space-y-3">
      <div
        v-if="breakdown.items.length === 0"
        class="py-12 text-center text-xs text-gray-400 dark:text-dark-500"
      >
        当前维度下无匹配的排行条目
      </div>

      <div
        v-for="(item, idx) in breakdown.items"
        :key="item.key"
        class="group cursor-pointer rounded-lg p-2 transition-colors hover:bg-gray-50 dark:hover:bg-dark-800/60"
        @click="handleItemClick(item)"
      >
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="inline-flex h-4.5 w-4.5 items-center justify-center rounded-full bg-gray-100 text-[10px] font-semibold text-gray-600 dark:bg-dark-800 dark:text-dark-300 font-mono"
            >
              {{ idx + 1 }}
            </span>
            <span
              class="font-medium text-gray-900 dark:text-gray-100 truncate group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors"
              :title="item.label"
            >
              {{ item.label }}
            </span>
          </div>

          <div class="flex items-center gap-2 font-mono text-xs shrink-0">
            <span class="font-semibold text-gray-900 dark:text-white">
              {{ formatMetricDisplay(item) }}
            </span>
          </div>
        </div>

        <!-- 进度条 -->
        <div
          class="mt-1.5 h-1.5 w-full rounded-full bg-gray-100 dark:bg-dark-800 overflow-hidden"
        >
          <div
            class="h-full rounded-full bg-primary-500 dark:bg-primary-600 transition-all duration-300"
            :style="{
              width: `${Math.min(Math.max((getMetricNumeric(item) / maxMetricValue) * 100, 2), 100)}%`,
            }"
          />
        </div>
      </div>

      <!-- “其他”聚合维度 (other) -->
      <div
        v-if="breakdown.other"
        class="rounded-lg border border-dashed border-gray-200 p-2.5 dark:border-dark-800 bg-gray-50/50 dark:bg-dark-950/30"
      >
        <div class="flex items-center justify-between text-xs">
          <span class="text-gray-500 dark:text-dark-400 font-medium"
            >其他未上榜项小计</span
          >
          <span
            class="font-mono font-semibold text-gray-700 dark:text-gray-300"
          >
            {{ formatMetricDisplay(breakdown.other) }}
          </span>
        </div>
        <div
          class="mt-1.5 h-1.5 w-full rounded-full bg-gray-200 dark:bg-dark-700 overflow-hidden"
        >
          <div
            class="h-full rounded-full bg-gray-400 dark:bg-dark-500"
            :style="{
              width: `${Math.min(Math.max((getMetricNumeric(breakdown.other) / maxMetricValue) * 100, 2), 100)}%`,
            }"
          />
        </div>
      </div>
    </div>
  </div>
</template>
