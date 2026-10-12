<script setup lang="ts">
import { computed } from "vue";
import type {
  DashboardQueryParams,
  Facets,
  Granularity,
  Timezone,
  CallPurpose,
  CallScope,
} from "../types";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  filters: DashboardQueryParams;
  facets?: Facets;
  isPlatformScope: boolean;
}>();

const emit = defineEmits<{
  "update:filters": [filters: DashboardQueryParams];
  reset: [];
}>();

// 快捷时间范围
type QuickRangeKey = "24h" | "7d" | "30d" | "custom";

const currentQuickRange = computed<QuickRangeKey>(() => {
  const fromMs = new Date(props.filters.from).getTime();
  const toMs = new Date(props.filters.to).getTime();
  const diffDays = Math.round((toMs - fromMs) / (1000 * 60 * 60 * 24));
  if (diffDays <= 1) return "24h";
  if (diffDays <= 7) return "7d";
  if (diffDays <= 30) return "30d";
  return "custom";
});

// 计算当前时间跨度天数
const timeSpanDays = computed(() => {
  const fromMs = new Date(props.filters.from).getTime();
  const toMs = new Date(props.filters.to).getTime();
  return (toMs - fromMs) / (1000 * 60 * 60 * 24);
});

// 是否支持小时粒度（严格防 400：跨度必须 <= 7 天）
const canUseHourGranularity = computed(() => timeSpanDays.value <= 7.001);

function selectQuickRange(key: QuickRangeKey) {
  const now = new Date();
  const toIso = now.toISOString();
  let fromDate = new Date(now);

  if (key === "24h") {
    fromDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  } else if (key === "7d") {
    fromDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else if (key === "30d") {
    fromDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }

  const updated: DashboardQueryParams = {
    ...props.filters,
    from: fromDate.toISOString(),
    to: toIso,
  };

  // 若切换到 30 天且当前是小时粒度，强制防呆切回按日
  if (key === "30d" && updated.granularity === "hour") {
    updated.granularity = "day";
  }

  emit("update:filters", updated);
}

function updateField<K extends keyof DashboardQueryParams>(
  key: K,
  value: DashboardQueryParams[K],
) {
  const updated: DashboardQueryParams = { ...props.filters, [key]: value };

  // 粒度与时间跨度防呆
  if (key === "granularity" && value === "hour" && timeSpanDays.value > 7) {
    // 自动收缩为 7 天
    const toDate = new Date(props.filters.to);
    const fromDate = new Date(toDate.getTime() - 7 * 24 * 60 * 60 * 1000);
    updated.from = fromDate.toISOString();
  }

  // 模型与未映射互斥联动
  if (key === "model_id" && value) {
    delete updated.model_mapping;
  }
  if (key === "model_mapping" && value) {
    delete updated.model_id;
  }

  emit("update:filters", updated);
}

// 判定平台多项目时是否需要禁用 Agent 筛选
const isAgentFilterDisabled = computed(() => {
  if (!props.isPlatformScope) return false;
  const projectIds = props.filters.project_ids;
  // 未选择项目，或者选择了 >= 2 个项目
  return !projectIds || projectIds.length !== 1;
});
</script>

<template>
  <div
    class="pw-filter-bar flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl border border-gray-200 bg-white dark:border-dark-800 dark:bg-dark-900 shadow-sm"
    data-testid="usage-filter-toolbar"
  >
    <!-- 左侧筛选控制组 -->
    <div class="flex flex-wrap items-center gap-2.5">
      <!-- 快捷时间窗口按钮组 -->
      <div
        class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-dark-700 dark:bg-dark-950"
      >
        <button
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
          :class="
            currentQuickRange === '24h'
              ? 'bg-white text-gray-950 shadow-sm dark:bg-dark-800 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
          "
          @click="selectQuickRange('24h')"
        >
          近24小时
        </button>
        <button
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
          :class="
            currentQuickRange === '7d'
              ? 'bg-white text-gray-950 shadow-sm dark:bg-dark-800 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
          "
          @click="selectQuickRange('7d')"
        >
          近7天
        </button>
        <button
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
          :class="
            currentQuickRange === '30d'
              ? 'bg-white text-gray-950 shadow-sm dark:bg-dark-800 dark:text-white'
              : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
          "
          @click="selectQuickRange('30d')"
        >
          近30天
        </button>
      </div>

      <!-- 粒度切换 -->
      <select
        :value="filters.granularity || 'day'"
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          updateField(
            'granularity',
            ($event.target as HTMLSelectElement).value as Granularity,
          )
        "
      >
        <option value="day">按日聚合</option>
        <option value="hour" :disabled="!canUseHourGranularity">
          按小时 ({{ canUseHourGranularity ? "支持" : "需≤7天" }})
        </option>
      </select>

      <!-- 时区选择 -->
      <select
        :value="filters.timezone || 'Asia/Shanghai'"
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          updateField(
            'timezone',
            ($event.target as HTMLSelectElement).value as Timezone,
          )
        "
      >
        <option value="Asia/Shanghai">Asia/Shanghai (CST)</option>
        <option value="UTC">UTC 时区</option>
      </select>

      <!-- 平台模式下的项目单选/筛选 -->
      <select
        v-if="isPlatformScope && facets?.projects?.items"
        :value="filters.project_ids?.[0] || ''"
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          updateField(
            'project_ids',
            ($event.target as HTMLSelectElement).value
              ? [($event.target as HTMLSelectElement).value]
              : undefined,
          )
        "
      >
        <option value="">全部项目 (跨项目汇总)</option>
        <option v-for="p in facets.projects.items" :key="p.id" :value="p.id">
          {{ p.label }}
        </option>
      </select>

      <!-- Agent 筛选（多项目时自动防呆禁用） -->
      <div
        class="relative inline-flex items-center"
        :title="
          isAgentFilterDisabled ? '请先限定单一项目后再按 Agent 筛选' : ''
        "
      >
        <select
          :value="filters.agent_id || ''"
          :disabled="isAgentFilterDisabled"
          class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          @change="
            updateField(
              'agent_id',
              ($event.target as HTMLSelectElement).value || undefined,
            )
          "
        >
          <option value="">
            {{ isAgentFilterDisabled ? "Agent (需先选单项目)" : "全部 Agent" }}
          </option>
          <option
            v-for="a in facets?.agents?.items || []"
            :key="a.graph_id"
            :value="a.agent_id || ''"
          >
            {{ a.label }}
          </option>
        </select>
      </div>

      <!-- 模型筛选 -->
      <select
        :value="
          filters.model_mapping === 'unmapped'
            ? 'unmapped'
            : filters.model_id || ''
        "
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          (e) => {
            const val = (e.target as HTMLSelectElement).value;
            if (val === 'unmapped') {
              updateField('model_mapping', 'unmapped');
            } else {
              updateField('model_id', val || undefined);
            }
          }
        "
      >
        <option value="">全部模型连接</option>
        <option value="unmapped">未映射模型 (unmapped)</option>
        <option
          v-for="m in (facets?.models?.items || []).filter(
            (item) => item.id !== 'unmapped',
          )"
          :key="m.id"
          :value="m.id"
        >
          {{ m.label }}
        </option>
      </select>

      <!-- 调用用途 -->
      <select
        :value="filters.purpose || ''"
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          updateField(
            'purpose',
            (($event.target as HTMLSelectElement).value as CallPurpose) ||
              undefined,
          )
        "
      >
        <option value="">全部用途</option>
        <option value="agent">Agent 执行</option>
        <option value="summarization">长文摘要</option>
        <option value="memory_extraction">记忆提取</option>
        <option value="vision">图像视觉</option>
        <option value="other">其他</option>
      </select>

      <!-- 范围层级 -->
      <select
        :value="filters.scope || ''"
        class="h-8 rounded-lg border border-gray-200 bg-white px-2.5 text-xs font-medium text-gray-800 dark:border-dark-700 dark:bg-dark-950 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
        @change="
          updateField(
            'scope',
            (($event.target as HTMLSelectElement).value as CallScope) ||
              undefined,
          )
        "
      >
        <option value="">全部范围</option>
        <option value="primary">主图调用 (primary)</option>
        <option value="subagent">子智能体 (subagent)</option>
        <option value="auxiliary">辅助调用 (auxiliary)</option>
      </select>
    </div>

    <!-- 右侧重置操作 -->
    <div class="flex items-center gap-2">
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 px-3 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white transition-colors"
        @click="emit('reset')"
      >
        <BaseIcon name="refresh" size="xs" />
        重置筛选
      </button>
    </div>
  </div>
</template>
