<script setup lang="ts">
import { ref, computed } from "vue";
import type { SeriesPoint } from "../types";
import {
  formatTokenNumber,
  formatTokenCompact,
  formatDashboardCost,
} from "../view-model";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  series: SeriesPoint[];
  granularity: "day" | "hour";
}>();

// 视图模式：'token' | 'cost'
const viewMode = ref<"token" | "cost">("token");
// 呈现形态：'chart' | 'table'
const displayType = ref<"chart" | "table">("chart");
// 当前悬停点
const hoveredIndex = ref<number | null>(null);

// SVG 尺寸参数
const svgWidth = 800;
const svgHeight = 260;
const padding = { top: 20, right: 30, bottom: 40, left: 60 };
const chartWidth = svgWidth - padding.left - padding.right;
const chartHeight = svgHeight - padding.top - padding.bottom;

// 计算最大值 (Y 轴比例尺)
const maxTokenValue = computed(() => {
  let max = 0;
  for (const p of props.series) {
    const total = p.tokens?.total_tokens ?? p.known_tokens?.total_tokens ?? 0;
    if (total > max) max = total;
  }
  return max > 0 ? max * 1.15 : 1000;
});

const maxCostValue = computed(() => {
  let max = 0;
  for (const p of props.series) {
    const costUsd = Number(
      p.cost?.estimated_cost_usd ?? p.cost?.known_cost_usd ?? 0,
    );
    if (!isNaN(costUsd) && costUsd > max) max = costUsd;
  }
  return max > 0 ? max * 1.15 : 0.01;
});

// 计算 Y 轴刻度
const yTicks = computed(() => {
  const steps = 4;
  const isCost = viewMode.value === "cost";
  const max = isCost ? maxCostValue.value : maxTokenValue.value;
  return Array.from({ length: steps + 1 }, (_, i) => {
    const val = (max / steps) * i;
    const y = padding.top + chartHeight - (val / max) * chartHeight;
    const label = isCost
      ? val < 0.001
        ? `$${val.toFixed(4)}`
        : `$${val.toFixed(2)}`
      : formatTokenCompact(Math.round(val));
    return { value: val, y, label };
  });
});

// 计算柱子几何信息
const bars = computed(() => {
  const count = props.series.length;
  if (count === 0) return [];
  const slotWidth = chartWidth / count;
  const barWidth = Math.max(Math.min(slotWidth * 0.65, 36), 4);

  return props.series.map((p, i) => {
    const xCenter = padding.left + i * slotWidth + slotWidth / 2;
    const x = xCenter - barWidth / 2;

    const inTokens =
      p.tokens?.input_tokens ?? p.known_tokens?.input_tokens ?? null;
    const outTokens =
      p.tokens?.output_tokens ?? p.known_tokens?.output_tokens ?? null;
    const totalTokens =
      p.tokens?.total_tokens ?? p.known_tokens?.total_tokens ?? null;
    const isPartial =
      p.tokens?.total_tokens === null && p.known_tokens?.total_tokens !== null;
    const isMissing = totalTokens === null;

    const costNum = Number(
      p.cost?.estimated_cost_usd ?? p.cost?.known_cost_usd ?? 0,
    );
    const costY =
      padding.top +
      chartHeight -
      (Math.max(costNum, 0) / maxCostValue.value) * chartHeight;

    let inHeight = 0;
    let outHeight = 0;
    let inY = padding.top + chartHeight;
    let outY = padding.top + chartHeight;

    if (!isMissing) {
      const validIn = inTokens ?? 0;
      const validOut = outTokens ?? 0;
      inHeight = (validIn / maxTokenValue.value) * chartHeight;
      outHeight = (validOut / maxTokenValue.value) * chartHeight;
      inY = padding.top + chartHeight - inHeight;
      outY = inY - outHeight;
    }

    // 格式化日期标尺
    const dateObj = new Date(p.from);
    const timeLabel =
      props.granularity === "hour"
        ? `${dateObj.getMonth() + 1}/${dateObj.getDate()} ${String(dateObj.getHours()).padStart(2, "0")}:00`
        : `${dateObj.getMonth() + 1}/${dateObj.getDate()}`;

    return {
      index: i,
      x,
      xCenter,
      barWidth,
      inY,
      inHeight,
      outY,
      outHeight,
      costY,
      isPartial,
      isMissing,
      point: p,
      timeLabel,
    };
  });
});

// 成本折线路径
const costPolylinePoints = computed(() => {
  return bars.value.map((b) => `${b.xCenter},${b.costY}`).join(" ");
});

// 当前悬浮项详情
const activeBar = computed(() => {
  if (hoveredIndex.value === null) return null;
  return bars.value[hoveredIndex.value] || null;
});
</script>

<template>
  <div
    class="pw-trend-card rounded-xl border border-gray-200 bg-white p-5 dark:border-dark-800 dark:bg-dark-900 shadow-sm"
    data-testid="usage-trend-panel"
  >
    <!-- 头部工具栏 -->
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-4 dark:border-dark-800"
    >
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
          用量与成本趋势
        </h3>
        <p class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
          {{
            granularity === "hour"
              ? "按小时切片分布（最近 7 天）"
              : "按日切片分布"
          }}，支持输入输出堆叠与成本分析
        </p>
      </div>

      <div class="flex items-center gap-2.5">
        <!-- 指标切换 (Token / 成本) -->
        <div
          class="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 dark:border-dark-700 dark:bg-dark-950"
        >
          <button
            type="button"
            class="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
            :class="
              viewMode === 'token'
                ? 'bg-white text-gray-950 shadow-sm dark:bg-dark-800 dark:text-white'
                : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
            "
            @click="viewMode = 'token'"
          >
            Token 堆叠
          </button>
          <button
            type="button"
            class="rounded-md px-2.5 py-1 text-xs font-medium transition-all"
            :class="
              viewMode === 'cost'
                ? 'bg-white text-gray-950 shadow-sm dark:bg-dark-800 dark:text-white'
                : 'text-gray-600 hover:text-gray-900 dark:text-dark-400 dark:hover:text-gray-200'
            "
            @click="viewMode = 'cost'"
          >
            成本折线 (USD)
          </button>
        </div>

        <!-- 视图切换 (图表 / 数据表格) -->
        <button
          type="button"
          class="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 hover:text-gray-900 dark:border-dark-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white transition-colors"
          :title="
            displayType === 'chart' ? '切换为数据表格视图' : '切换为图表视图'
          "
          @click="displayType = displayType === 'chart' ? 'table' : 'chart'"
        >
          <BaseIcon
            :name="displayType === 'chart' ? 'table' : 'activity'"
            size="xs"
          />
        </button>
      </div>
    </div>

    <!-- 主体区域：图表模式 -->
    <div v-if="displayType === 'chart'" class="relative mt-4">
      <div
        v-if="series.length === 0"
        class="flex h-56 flex-col items-center justify-center text-center text-gray-400 dark:text-dark-500"
      >
        <BaseIcon name="activity" size="lg" class="mb-2 opacity-50" />
        <span class="text-xs">所选时间窗口内暂无趋势数据点</span>
      </div>

      <div v-else class="relative overflow-x-auto">
        <svg
          :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
          class="w-full h-auto select-none overflow-visible"
        >
          <defs>
            <!-- partial 桶斜条纹 pattern -->
            <pattern
              id="diagonal-stripes"
              patternUnits="userSpaceOnUse"
              width="6"
              height="6"
              patternTransform="rotate(45)"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="6"
                stroke="rgba(245, 158, 11, 0.4)"
                stroke-width="2.5"
              />
            </pattern>
          </defs>

          <!-- 水平网格线与 Y 轴刻度文字 -->
          <g class="grid-lines">
            <g v-for="t in yTicks" :key="t.y">
              <line
                :x1="padding.left"
                :y1="t.y"
                :x2="svgWidth - padding.right"
                :y2="t.y"
                class="stroke-gray-100 dark:stroke-dark-800"
                stroke-dasharray="3 3"
              />
              <text
                :x="padding.left - 8"
                :y="t.y + 4"
                text-anchor="end"
                class="fill-gray-400 dark:fill-dark-500 text-[10px] font-mono"
              >
                {{ t.label }}
              </text>
            </g>
          </g>

          <!-- 模式 A：Token 堆叠柱状图 -->
          <g v-if="viewMode === 'token'">
            <g
              v-for="b in bars"
              :key="b.index"
              class="cursor-pointer group"
              @mouseenter="hoveredIndex = b.index"
              @mouseleave="hoveredIndex = null"
            >
              <!-- 缺失缺口占位 (null 值) -->
              <rect
                v-if="b.isMissing"
                :x="b.x"
                :y="padding.top"
                :width="b.barWidth"
                :height="chartHeight"
                class="fill-gray-50/50 dark:fill-dark-950/30"
              />

              <!-- 输入 Token 柱 (蓝色) -->
              <rect
                v-if="!b.isMissing"
                :x="b.x"
                :y="b.inY"
                :width="b.barWidth"
                :height="Math.max(b.inHeight, 0)"
                class="fill-primary-500 dark:fill-primary-600 transition-opacity group-hover:opacity-85"
                rx="1"
              />

              <!-- 输出 Token 柱 (绿色堆叠) -->
              <rect
                v-if="!b.isMissing"
                :x="b.x"
                :y="b.outY"
                :width="b.barWidth"
                :height="Math.max(b.outHeight, 0)"
                class="fill-emerald-500 dark:fill-emerald-600 transition-opacity group-hover:opacity-85"
                rx="1"
              />

              <!-- partial 斜条纹遮罩 -->
              <rect
                v-if="b.isPartial"
                :x="b.x"
                :y="b.outY"
                :width="b.barWidth"
                :height="Math.max(b.inHeight + b.outHeight, 0)"
                fill="url(#diagonal-stripes)"
                rx="1"
              />
            </g>
          </g>

          <!-- 模式 B：成本折线图 -->
          <g v-if="viewMode === 'cost'">
            <polyline
              :points="costPolylinePoints"
              fill="none"
              class="stroke-amber-500 dark:stroke-amber-400"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle
              v-for="b in bars"
              :key="b.index"
              :cx="b.xCenter"
              :cy="b.costY"
              r="3.5"
              class="fill-white stroke-amber-500 dark:fill-dark-900 dark:stroke-amber-400 cursor-pointer"
              stroke-width="2"
              @mouseenter="hoveredIndex = b.index"
              @mouseleave="hoveredIndex = null"
            />
          </g>

          <!-- X 轴日期刻度文字 (每隔若干个显示一个，防拥挤) -->
          <g class="x-axis-labels">
            <template v-for="(b, idx) in bars" :key="b.index">
              <text
                v-if="
                  bars.length <= 14 || idx % Math.ceil(bars.length / 10) === 0
                "
                :x="b.xCenter"
                :y="svgHeight - padding.bottom + 18"
                text-anchor="middle"
                class="fill-gray-400 dark:fill-dark-500 text-[10px] font-mono"
              >
                {{ b.timeLabel }}
              </text>
            </template>
          </g>
        </svg>

        <!-- 悬停 Tooltip 浮层 -->
        <div
          v-if="activeBar"
          class="pointer-events-none absolute z-20 rounded-lg border border-gray-200 bg-white/95 p-3 shadow-xl backdrop-blur-sm dark:border-dark-700 dark:bg-dark-900/95 text-xs text-gray-800 dark:text-gray-200"
          :style="{
            left: `${Math.min(Math.max(activeBar.xCenter - 80, 10), chartWidth - 100)}px`,
            top: '10px',
          }"
        >
          <div
            class="font-semibold text-gray-950 dark:text-white border-b border-gray-100 dark:border-dark-800 pb-1 mb-1.5"
          >
            {{ activeBar.timeLabel }}
            <span
              v-if="activeBar.isPartial"
              class="ml-1 text-[10px] text-amber-600 dark:text-amber-400"
              >(部分未结)</span
            >
            <span
              v-if="activeBar.isMissing"
              class="ml-1 text-[10px] text-gray-400"
              >(缺失)</span
            >
          </div>
          <div class="space-y-1 font-mono text-[11px]">
            <div class="flex justify-between gap-4">
              <span class="text-primary-600 dark:text-primary-400 font-sans"
                >输入 Token:</span
              >
              <span>{{
                formatTokenNumber(
                  activeBar.point.tokens?.input_tokens ??
                    activeBar.point.known_tokens?.input_tokens,
                )
              }}</span>
            </div>
            <div class="flex justify-between gap-4">
              <span class="text-emerald-600 dark:text-emerald-400 font-sans"
                >输出 Token:</span
              >
              <span>{{
                formatTokenNumber(
                  activeBar.point.tokens?.output_tokens ??
                    activeBar.point.known_tokens?.output_tokens,
                )
              }}</span>
            </div>
            <div
              class="flex justify-between gap-4 border-t border-gray-100 dark:border-dark-800 pt-1"
            >
              <span class="font-sans font-medium">总计 Token:</span>
              <span class="font-bold">{{
                formatTokenNumber(
                  activeBar.point.tokens?.total_tokens ??
                    activeBar.point.known_tokens?.total_tokens,
                )
              }}</span>
            </div>
            <div
              class="flex justify-between gap-4 text-amber-600 dark:text-amber-400"
            >
              <span class="font-sans">估算成本:</span>
              <span>{{
                formatDashboardCost(activeBar.point.cost).display
              }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部图例 -->
      <div
        class="mt-2 flex items-center justify-center gap-5 text-xs text-gray-500 dark:text-dark-400"
      >
        <div class="flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-sm bg-primary-500" />
          <span>输入 Tokens</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-sm bg-emerald-500" />
          <span>输出 Tokens</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span
            class="h-2.5 w-2.5 rounded-sm border border-amber-400 bg-amber-50 dark:bg-amber-950/40"
          />
          <span>部分入账 (Partial)</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="h-0.5 w-3 bg-amber-500" />
          <span>成本趋势 (USD)</span>
        </div>
      </div>
    </div>

    <!-- 主体区域：数据表格模式 (无障碍 a11y) -->
    <div v-else class="mt-4 overflow-x-auto">
      <table class="w-full text-left text-xs text-gray-700 dark:text-gray-300">
        <thead
          class="border-b border-gray-200 bg-gray-50 text-[11px] uppercase tracking-wider text-gray-500 dark:border-dark-800 dark:bg-dark-950 dark:text-dark-400"
        >
          <tr>
            <th class="px-3 py-2">时间区间</th>
            <th class="px-3 py-2 text-right">输入 Token</th>
            <th class="px-3 py-2 text-right">输出 Token</th>
            <th class="px-3 py-2 text-right">总计 Token</th>
            <th class="px-3 py-2 text-right">估算成本 (USD)</th>
            <th class="px-3 py-2 text-center">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-dark-800 font-mono">
          <tr
            v-for="(p, i) in series"
            :key="i"
            class="hover:bg-gray-50/50 dark:hover:bg-dark-800/50"
          >
            <td class="px-3 py-2 font-sans">{{ p.from }}</td>
            <td class="px-3 py-2 text-right">
              {{
                formatTokenNumber(
                  p.tokens?.input_tokens ?? p.known_tokens?.input_tokens,
                )
              }}
            </td>
            <td class="px-3 py-2 text-right">
              {{
                formatTokenNumber(
                  p.tokens?.output_tokens ?? p.known_tokens?.output_tokens,
                )
              }}
            </td>
            <td class="px-3 py-2 text-right font-semibold">
              {{
                formatTokenNumber(
                  p.tokens?.total_tokens ?? p.known_tokens?.total_tokens,
                )
              }}
            </td>
            <td class="px-3 py-2 text-right text-amber-600 dark:text-amber-400">
              {{ formatDashboardCost(p.cost).display }}
            </td>
            <td class="px-3 py-2 text-center font-sans">
              <span
                v-if="p.tokens?.total_tokens !== null"
                class="text-emerald-600 dark:text-emerald-400"
                >完整</span
              >
              <span
                v-else-if="p.known_tokens?.total_tokens !== null"
                class="text-amber-600 dark:text-amber-400"
                >部分</span
              >
              <span v-else class="text-gray-400">缺失</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
