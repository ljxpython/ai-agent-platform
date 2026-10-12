<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { useUsageDashboard } from "../composables/useUsageDashboard";
import { useUsageRuns } from "../composables/useUsageRuns";
import type {
  DashboardQueryParams,
  RunsQueryParams,
  UsageRun,
  UsageGroup,
} from "../types";
import {
  formatTokenNumber,
  resolveDisplayTokens,
  formatDashboardCost,
  formatChangeRatio,
  getAvailabilityBadge,
} from "../view-model";
import UsageFilterToolbar from "../components/UsageFilterToolbar.vue";
import UsageTrend from "../components/UsageTrend.vue";
import UsageBreakdown from "../components/UsageBreakdown.vue";
import RunUsage from "@/modules/chat/components/trajectory/RunUsage.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const route = useRoute();

// 1. 作用域派生 (严格从路由路径判定，防顶栏项目切换污染)
const currentScope = computed(() => {
  const projectIdParam = route.params.projectId;
  if (projectIdParam && typeof projectIdParam === "string") {
    return { kind: "project" as const, projectId: projectIdParam.trim() };
  }
  return { kind: "platform" as const };
});

const isPlatformScope = computed(() => currentScope.value.kind === "platform");

// 默认 7 天时间窗口
function getDefaultFilters(): DashboardQueryParams {
  const now = new Date();
  const from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  return {
    from: from.toISOString(),
    to: now.toISOString(),
    timezone: "Asia/Shanghai",
    granularity: "day",
    group_by: "model",
    rank_by: "known_total_tokens",
    top_n: 10,
  };
}

const filters = ref<DashboardQueryParams>(getDefaultFilters());

// 2. 报表数据组合器
const {
  data: dashboardData,
  loading: dashboardLoading,
  isRefreshing,
  error: dashboardError,
  refresh: refreshDashboard,
} = useUsageDashboard({
  scope: currentScope,
  filters,
});

// 3. 运行明细关联项目判定
const targetRunsProjectId = computed<string | undefined>(() => {
  if (currentScope.value.kind === "project") {
    return currentScope.value.projectId;
  }
  // 平台模式下，必须在筛选栏明确且仅选定 1 个项目才能查看明细
  if (filters.value.project_ids && filters.value.project_ids.length === 1) {
    return filters.value.project_ids[0];
  }
  return undefined;
});

// Runs 查询参数白名单
const runsFilters = computed<RunsQueryParams>(() => ({
  from: filters.value.from,
  to: filters.value.to,
  model_id: filters.value.model_id,
  model_mapping: filters.value.model_mapping,
  agent_id: filters.value.agent_id,
  purpose: filters.value.purpose,
  scope: filters.value.scope,
  limit: 50,
}));

// 4. Runs 分页组合器
const {
  items: runItems,
  nextCursor,
  loading: runsLoading,
  loadingMore: runsLoadingMore,
  error: runsError,
  hasEmptyWithCursor,
  loadFirstPage,
  loadNextPage,
} = useUsageRuns({
  projectId: targetRunsProjectId,
  filters: runsFilters,
});

// 5. 抽屉与详情交互
const drawerOpen = ref(false);
const activeRun = ref<UsageRun | null>(null);

function openRunDrawer(run: UsageRun) {
  activeRun.value = run;
  drawerOpen.value = true;
}

function closeDrawer() {
  drawerOpen.value = false;
  activeRun.value = null;
}

// 6. 重置所有筛选
function handleResetFilters() {
  filters.value = getDefaultFilters();
}

// 7. 排行点击钻取
function handleDrilldown(item: UsageGroup) {
  const currentGroupBy = dashboardData.value?.breakdown.group_by || "model";
  if (currentGroupBy === "model") {
    if (item.key === "unmapped") {
      filters.value = {
        ...filters.value,
        model_mapping: "unmapped",
        model_id: undefined,
      };
    } else {
      filters.value = {
        ...filters.value,
        model_id: item.key,
        model_mapping: undefined,
      };
    }
  } else if (currentGroupBy === "agent" && item.agent_id) {
    filters.value = { ...filters.value, agent_id: item.agent_id };
  } else if (currentGroupBy === "project" && item.project_id) {
    filters.value = { ...filters.value, project_ids: [item.project_id] };
  }
}

// 指标卡计算数据
const displayTokens = computed(() =>
  resolveDisplayTokens(
    dashboardData.value?.summary.tokens,
    dashboardData.value?.summary.known_tokens,
  ),
);

const costViewModel = computed(() =>
  formatDashboardCost(
    dashboardData.value?.summary.cost,
    dashboardData.value?.availability,
    dashboardData.value?.unavailable_reason,
  ),
);

const availBadge = computed(() =>
  getAvailabilityBadge(
    dashboardData.value?.availability || "unavailable",
    dashboardData.value?.unavailable_reason,
  ),
);

const dashboardErrorMessage = computed(() => {
  if (!dashboardError.value) return "";
  const err = dashboardError.value as { code?: string; message: string };
  if (err.code === "usage_query_capacity_exhausted") {
    return "用量查询服务容量暂时饱和（排队或处理超时），已保留当前筛选条件，请点击重试";
  }
  return `查询用量数据失败：${err.message}`;
});

const runsErrorMessage = computed(() => {
  if (!runsError.value) return "";
  const err = runsError.value as { code?: string; message: string };
  if (err.code === "usage_query_capacity_exhausted") {
    return "运行明细查询容量暂时饱和，已保留筛选条件，请点击重试";
  }
  return `检索运行明细失败：${err.message}`;
});
</script>

<template>
  <div
    class="space-y-6 p-6 max-w-[1600px] mx-auto select-text font-sans"
    data-testid="usage-dashboard-page"
  >
    <!-- 1. 顶部 Header -->
    <header
      class="flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-5 dark:border-dark-800"
    >
      <div>
        <div class="flex items-center gap-2.5">
          <h1
            class="text-xl font-bold tracking-tight text-gray-950 dark:text-white"
          >
            Token 看板 · {{ isPlatformScope ? "平台用量" : "项目用量" }}
          </h1>
          <span
            class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border"
            :class="{
              'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800':
                availBadge.variant === 'success',
              'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800':
                availBadge.variant === 'warning',
              'bg-gray-100 text-gray-700 border-gray-200 dark:bg-dark-800 dark:text-gray-300 dark:border-dark-700':
                availBadge.variant === 'muted',
              'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800':
                availBadge.variant === 'error',
            }"
            :title="availBadge.description"
          >
            {{ availBadge.label }}
          </span>
        </div>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          数据快照时刻：{{ dashboardData?.as_of || "加载中..." }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-gray-200 dark:hover:bg-dark-800 transition-colors shadow-sm disabled:opacity-50"
          :disabled="dashboardLoading || isRefreshing"
          @click="refreshDashboard"
        >
          <BaseIcon
            name="refresh"
            size="xs"
            :class="{ 'animate-spin': isRefreshing }"
          />
          {{ isRefreshing ? "刷新中..." : "手动刷新" }}
        </button>
      </div>
    </header>

    <!-- 2. 常驻业务说明条 (参考 deer-flow 最佳实践) -->
    <aside
      class="flex items-start gap-3 rounded-xl border border-primary-100 bg-primary-50/50 p-4 text-xs leading-5 text-primary-900 dark:border-primary-950/80 dark:bg-primary-950/20 dark:text-primary-200 shadow-sm"
    >
      <BaseIcon
        name="info"
        size="sm"
        class="mt-0.5 shrink-0 text-primary-600 dark:text-primary-400"
      />
      <div class="flex-1">
        <p class="font-medium">
          已采集当前范围内 Agent
          运行用量；辅助开销（标题生成、推荐问题等）及未落账调用未计入。
        </p>
        <p class="mt-0.5 text-primary-700/80 dark:text-primary-300/70">
          由于系统重试、内部调用及供应商计费周期差异，汇总数据与供应商账单可能存在微小偏差。金额展示保留
          12 位原文字符串精度，严防截断丢失。
        </p>
      </div>
    </aside>

    <!-- 3. 筛选工具栏 -->
    <UsageFilterToolbar
      :filters="filters"
      :facets="dashboardData?.facets"
      :is-platform-scope="isPlatformScope"
      @update:filters="filters = $event"
      @reset="handleResetFilters"
    />

    <!-- 错误状态提示卡 -->
    <div
      v-if="dashboardError"
      class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200 flex items-center justify-between"
    >
      <div class="flex items-center gap-2">
        <BaseIcon name="alert" size="sm" class="text-rose-600" />
        <span>{{ dashboardErrorMessage }}</span>
      </div>
      <button
        type="button"
        class="font-medium underline hover:text-rose-950 dark:hover:text-white"
        @click="refreshDashboard"
      >
        重试
      </button>
    </div>

    <!-- 4. 四组金融级核心指标卡 -->
    <section
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 transition-opacity duration-150"
      :class="{ 'opacity-70': isRefreshing }"
    >
      <!-- 卡片 1: 已记录 Token -->
      <article
        class="pw-stat-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm flex flex-col justify-between"
      >
        <div>
          <div
            class="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
          >
            <span>已记录 Token</span>
            <span
              v-if="displayTokens.isPartial"
              class="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
            >
              部分小计
            </span>
          </div>
          <div
            class="mt-2 text-2xl font-bold font-mono tracking-tight text-gray-950 dark:text-white"
          >
            {{ formatTokenNumber(displayTokens.data?.total_tokens) }}
          </div>
        </div>
        <div
          class="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500 dark:border-dark-800 dark:text-dark-400 flex items-center justify-between"
        >
          <span>较紧邻前窗：</span>
          <span
            class="font-mono font-medium"
            :class="
              Number(
                dashboardData?.previous_window.total_token_change_ratio || 0,
              ) > 0
                ? 'text-emerald-600'
                : 'text-gray-600 dark:text-gray-400'
            "
          >
            {{
              formatChangeRatio(
                dashboardData?.previous_window.total_token_change_ratio,
              )
            }}
          </span>
        </div>
      </article>

      <!-- 卡片 2: 输入 / 输出明细 -->
      <article
        class="pw-stat-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm flex flex-col justify-between"
      >
        <div>
          <div
            class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
          >
            输入 / 输出 Tokens
          </div>
          <div
            class="mt-2 text-2xl font-bold font-mono tracking-tight text-gray-950 dark:text-white"
          >
            <span class="text-primary-600 dark:text-primary-400">{{
              formatTokenNumber(displayTokens.data?.input_tokens)
            }}</span>
            <span class="mx-1 text-gray-300 dark:text-dark-600">/</span>
            <span class="text-emerald-600 dark:text-emerald-400">{{
              formatTokenNumber(displayTokens.data?.output_tokens)
            }}</span>
          </div>
        </div>
        <div
          class="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500 dark:border-dark-800 dark:text-dark-400 flex items-center justify-between"
        >
          <span
            >缓存读:
            <strong class="font-mono text-gray-700 dark:text-gray-300">{{
              formatTokenNumber(displayTokens.data?.cache_read_tokens)
            }}</strong></span
          >
          <span
            >推理:
            <strong class="font-mono text-gray-700 dark:text-gray-300">{{
              formatTokenNumber(displayTokens.data?.reasoning_tokens)
            }}</strong></span
          >
        </div>
      </article>

      <!-- 卡片 3: 估算成本 (USD) -->
      <article
        class="pw-stat-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm flex flex-col justify-between"
      >
        <div>
          <div
            class="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
          >
            <span>估算成本 (USD)</span>
            <span
              v-if="costViewModel.isPartial"
              class="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border border-amber-200"
            >
              部分计价
            </span>
          </div>
          <div
            class="mt-2 text-2xl font-bold font-mono tracking-tight text-amber-600 dark:text-amber-400"
            :title="`完整精度：${costViewModel.fullUsd}`"
          >
            {{ costViewModel.display }}
          </div>
        </div>
        <div
          class="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500 dark:border-dark-800 dark:text-dark-400 flex items-center justify-between"
        >
          <span>未计价调用数：</span>
          <span class="font-mono font-medium">{{
            dashboardData?.summary.cost.unpriced_call_count ?? "—"
          }}</span>
        </div>
      </article>

      <!-- 卡片 4: 已采集调用 / Run -->
      <article
        class="pw-stat-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm flex flex-col justify-between"
      >
        <div>
          <div
            class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-dark-400"
          >
            已采集调用 / 运行数
          </div>
          <div
            class="mt-2 text-2xl font-bold font-mono tracking-tight text-gray-950 dark:text-white"
          >
            <span>{{
              dashboardData?.summary.coverage.observed_call_count ?? "—"
            }}</span>
            <span class="mx-1 text-gray-300 dark:text-dark-600">/</span>
            <span>{{ dashboardData?.summary.recorded_run_count ?? "—" }}</span>
          </div>
        </div>
        <div
          class="mt-3 border-t border-gray-100 pt-2 text-xs text-gray-500 dark:border-dark-800 dark:text-dark-400 flex items-center justify-between"
        >
          <span>调用报告率：</span>
          <span
            class="font-mono font-medium text-emerald-600 dark:text-emerald-400"
          >
            {{
              dashboardData?.summary.coverage.observed_call_count
                ? `${Math.round(((dashboardData.summary.coverage.reported_call_count || 0) / dashboardData.summary.coverage.observed_call_count) * 100)}%`
                : "—"
            }}
          </span>
        </div>
      </article>
    </section>

    <!-- 5. 趋势图与排行分解双栏 -->
    <section
      class="grid grid-cols-1 gap-6 lg:grid-cols-2 transition-opacity duration-150"
      :class="{ 'opacity-70': isRefreshing }"
    >
      <!-- 趋势堆叠图与折线图 -->
      <UsageTrend
        :series="dashboardData?.series || []"
        :granularity="filters.granularity || 'day'"
      />

      <!-- 排行与分解 -->
      <UsageBreakdown
        v-if="dashboardData"
        :breakdown="dashboardData.breakdown"
        :is-platform-scope="isPlatformScope"
        @update:group_by="filters.group_by = $event"
        @update:rank_by="filters.rank_by = $event"
        @drilldown="handleDrilldown"
      />
    </section>

    <!-- 6. 运行明细表格区域 -->
    <section
      class="rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm space-y-4"
      data-testid="usage-runs-section"
    >
      <div
        class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-4 dark:border-dark-800"
      >
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
            运行明细 (期间消费)
          </h3>
          <p class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
            仅显示当前账号有权查看的 Run；展示数据覆盖所选筛选期间
          </p>
        </div>

        <div v-if="targetRunsProjectId" class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex h-7 items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 text-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-dark-700 dark:text-dark-300 dark:hover:bg-dark-800"
            :disabled="runsLoading"
            @click="loadFirstPage"
          >
            <BaseIcon
              name="refresh"
              size="xs"
              :class="{ 'animate-spin': runsLoading }"
            />
            重新开始
          </button>
        </div>
      </div>

      <!-- 场景 A：平台模式未限定单项目 -> 展示友好引导态 -->
      <div
        v-if="!targetRunsProjectId"
        class="flex h-44 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 p-6 text-center text-gray-500 dark:border-dark-800 dark:text-dark-400 bg-gray-50/40 dark:bg-dark-950/20"
      >
        <BaseIcon
          name="project"
          size="lg"
          class="mb-2 text-gray-400 opacity-60"
        />
        <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
          平台汇总视图未指定单个项目
        </p>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400 max-w-md">
          运行明细与会话正文遵循强权限隔离。请在上方筛选栏限定单个具体项目，以检索该项目下你可查看的详细运行。
        </p>
      </div>

      <!-- 场景 B：已锁定单项目 -> 展示 Runs 数据表格 -->
      <div v-else>
        <!-- 运行检索错误提示 -->
        <div
          v-if="runsError"
          class="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300 flex items-center justify-between"
        >
          <div class="flex items-center gap-2">
            <BaseIcon name="alert" size="xs" class="text-rose-600" />
            <span>{{ runsErrorMessage }}</span>
          </div>
          <button
            type="button"
            class="font-semibold underline hover:text-rose-950 dark:hover:text-rose-100"
            @click="loadFirstPage"
          >
            重试
          </button>
        </div>

        <!-- 空页带 cursor 穿透扫描提示 -->
        <div
          v-if="hasEmptyWithCursor"
          class="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300 flex items-center justify-between"
        >
          <div class="flex items-center gap-2">
            <BaseIcon name="info" size="xs" />
            <span
              >当前扫描批次中无可见会话（已受 Thread ACL
              过滤），但后端仍有后续候选记录。</span
            >
          </div>
          <button
            type="button"
            class="font-semibold underline hover:text-amber-950 dark:hover:text-amber-100"
            @click="loadNextPage"
          >
            继续穿透扫描
          </button>
        </div>

        <div class="overflow-x-auto">
          <table
            class="w-full text-left text-xs text-gray-700 dark:text-gray-300"
          >
            <thead
              class="border-b border-gray-200 bg-gray-50 text-[11px] uppercase tracking-wider text-gray-500 dark:border-dark-800 dark:bg-dark-950 dark:text-dark-400 font-sans"
            >
              <tr>
                <th class="px-3.5 py-2.5">调用开始时间</th>
                <th class="px-3.5 py-2.5">Agent 名称</th>
                <th class="px-3.5 py-2.5">Run ID</th>
                <th class="px-3.5 py-2.5 text-right">期间 Token</th>
                <th class="px-3.5 py-2.5 text-right">期间估算成本</th>
                <th class="px-3.5 py-2.5 text-center">覆盖率</th>
                <th class="px-3.5 py-2.5 text-right">操作</th>
              </tr>
            </thead>
            <tbody
              class="divide-y divide-gray-100 dark:divide-dark-800 font-mono"
            >
              <tr v-if="runsLoading && runItems.length === 0">
                <td
                  colspan="7"
                  class="py-12 text-center text-xs text-gray-400 font-sans"
                >
                  正在检索运行明细...
                </td>
              </tr>
              <tr v-else-if="runItems.length === 0">
                <td
                  colspan="7"
                  class="py-12 text-center text-xs text-gray-400 font-sans"
                >
                  当前筛选条件与权限范围内未检索到任何匹配运行
                </td>
              </tr>
              <tr
                v-for="run in runItems"
                :key="`${run.project_id}_${run.run_id}`"
                class="hover:bg-gray-50/60 dark:hover:bg-dark-800/40 transition-colors"
              >
                <td class="px-3.5 py-2.5 font-sans">
                  {{ run.first_matching_call_at }}
                </td>
                <td
                  class="px-3.5 py-2.5 font-sans font-medium text-gray-900 dark:text-white"
                >
                  {{ run.agent_name || run.graph_id }}
                </td>
                <td
                  class="px-3.5 py-2.5 text-gray-500 dark:text-dark-400 text-[11px]"
                  :title="run.run_id"
                >
                  {{ run.run_id.slice(0, 8) }}...
                </td>
                <td class="px-3.5 py-2.5 text-right font-semibold">
                  {{
                    formatTokenNumber(
                      run.tokens?.total_tokens ??
                        run.known_tokens?.total_tokens,
                    )
                  }}
                </td>
                <td
                  class="px-3.5 py-2.5 text-right text-amber-600 dark:text-amber-400"
                >
                  {{ formatDashboardCost(run.cost).display }}
                </td>
                <td class="px-3.5 py-2.5 text-center font-sans">
                  <span
                    class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-dark-800 dark:text-dark-300"
                  >
                    {{ run.coverage.reported_call_count }}/{{
                      run.coverage.observed_call_count
                    }}
                  </span>
                </td>
                <td class="px-3.5 py-2.5 text-right font-sans">
                  <button
                    type="button"
                    class="rounded px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-950/50 transition-colors"
                    @click="openRunDrawer(run)"
                  >
                    查看用量
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 分页底部 -->
        <div v-if="nextCursor" class="mt-4 flex items-center justify-center">
          <button
            type="button"
            class="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-4 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-900 dark:text-gray-200 dark:hover:bg-dark-800 shadow-sm disabled:opacity-50"
            :disabled="runsLoadingMore"
            @click="loadNextPage"
          >
            <BaseIcon
              v-if="runsLoadingMore"
              name="refresh"
              size="xs"
              class="animate-spin"
            />
            <span>{{
              runsLoadingMore ? "正在扫描后续批次..." : "继续加载下一批"
            }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- 7. 无头模式挂载 RunUsage 抽屉 (彻底消除双 Header 与双滚动条冲突) -->
    <BaseDrawer
      :show="drawerOpen"
      title="完整运行用量分析"
      width="wide"
      flush
      @close="closeDrawer"
    >
      <RunUsage
        v-if="drawerOpen && activeRun"
        :project-id="activeRun.project_id"
        :thread-id="activeRun.thread_id"
        :run-id="activeRun.run_id"
        headless
        @close="closeDrawer"
      />
    </BaseDrawer>
  </div>
</template>
