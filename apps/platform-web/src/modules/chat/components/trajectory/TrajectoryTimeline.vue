<script setup lang="ts">
import { computed, ref } from "vue";
import type { TrajectoryRecord, TrajectoryRecordKind } from "../../trajectory/types";

const props = withDefaults(
  defineProps<{
    records: TrajectoryRecord[];
    selectedRecordId: string | null;
    actualDuration?: boolean;
  }>(),
  {
    actualDuration: true,
  },
);

const emit = defineEmits<{
  select: [record: TrajectoryRecord];
}>();

interface TimelineSpan {
  record: TrajectoryRecord;
  lane: 0 | 1 | 2; // 0: Input, 1: Model, 2: Tools
  leftPercent: number;
  widthPercent: number;
  colorClass: string;
}

function getLaneForKind(kind: TrajectoryRecordKind): 0 | 1 | 2 {
  switch (kind) {
    case "system":
    case "context":
    case "user":
      return 0; // Input
    case "reasoning":
    case "assistant":
      return 1; // Model
    case "tool":
    case "subagent":
    default:
      return 2; // Tools
  }
}

function getColorClass(record: TrajectoryRecord): string {
  if (record.status === "error") {
    return "bg-red-500 text-white";
  }
  switch (record.kind) {
    case "system":
      return "bg-gray-400 dark:bg-gray-600";
    case "user":
      return "bg-blue-500 dark:bg-blue-600";
    case "context":
      return "bg-emerald-500 dark:bg-emerald-600";
    case "reasoning":
      return "bg-purple-400 dark:bg-purple-500";
    case "assistant":
      return "bg-purple-600 dark:bg-purple-500";
    case "tool":
    case "subagent":
      return "bg-amber-500 dark:bg-amber-600";
    default:
      return "bg-gray-500";
  }
}

// 格式化时间
function formatTime(timestamp: number): string {
  const d = new Date(timestamp);
  const pad = (n: number, z = 2) => String(n).padStart(z, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

function formatDuration(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${Math.round(ms)} ms`;
}

function formatRange(record: TrajectoryRecord): string {
  const start = record.startedAt ? new Date(record.startedAt).getTime() : Date.now();
  const dur = record.durationMs || 0;
  return `${formatTime(start)} → ${formatTime(start + dur)}`;
}

// 悬停 Tooltip 状态
const hoveredSpan = ref<TimelineSpan | null>(null);
const tooltipStyle = ref<{ left: string; top: string }>({ left: "0px", top: "0px" });

function handleSpanEnter(span: TimelineSpan, event: MouseEvent) {
  hoveredSpan.value = span;
  const target = event.currentTarget as HTMLElement;
  const parent = target.parentElement;
  if (!parent) return;
  const rect = target.getBoundingClientRect();
  const parentRect = parent.getBoundingClientRect();

  const rawLeft = rect.left - parentRect.left + rect.width / 2;
  const clampedLeft = Math.min(Math.max(rawLeft, 80), parentRect.width - 80);

  tooltipStyle.value = {
    left: `${clampedLeft}px`,
    top: `${rect.bottom - parentRect.top + 6}px`,
  };
}

function handleSpanLeave() {
  hoveredSpan.value = null;
}

// 计算时间片在横轴上的百分比布局
const spans = computed<TimelineSpan[]>(() => {
  const total = props.records.length;
  if (total === 0) return [];

  // 均分切片模式
  if (!props.actualDuration) {
    const stepPercent = 100 / total;
    return props.records.map((record, i) => ({
      record,
      lane: getLaneForKind(record.kind),
      leftPercent: i * stepPercent,
      widthPercent: Math.max(stepPercent * 0.92, 1.5),
      colorClass: getColorClass(record),
    }));
  }

  // 实际耗时模式
  let cumulativeOffset = 0;
  const totalDuration = props.records.reduce(
    (sum, r) => sum + (r.durationMs && r.durationMs > 0 ? r.durationMs : 100),
    0,
  );
  return props.records.map((record) => {
    const dur = record.durationMs && record.durationMs > 0 ? record.durationMs : 100;
    const leftPercent = (cumulativeOffset / totalDuration) * 100;
    const widthPercent = Math.max((dur / totalDuration) * 100, 1.2);
    cumulativeOffset += dur;
    return {
      record,
      lane: getLaneForKind(record.kind),
      leftPercent,
      widthPercent,
      colorClass: getColorClass(record),
    };
  });
});

function getSpanStyle(span: TimelineSpan) {
  const style: Record<string, string> = {
    left: `${span.leftPercent}%`,
    width: `${span.widthPercent}%`,
    top: span.lane === 0 ? "6px" : span.lane === 1 ? "20px" : "34px",
    height: "9px",
  };
  if (span.record.kind === "assistant" && span.record.ttftMs && span.record.durationMs) {
    const ttftPct = Math.min(
      Math.max(
        Math.round((span.record.ttftMs / span.record.durationMs) * 100),
        15,
      ),
      85,
    );
    // 两段式渐变：前半截浅紫 (TTFT)，后半截深紫 (Decoding) (图 3 原版同款)
    style.background = `linear-gradient(to right, #b49fd9 0%, #b49fd9 ${ttftPct}%, #7e57c2 ${ttftPct}%, #7e57c2 100%)`;
  }
  return style;
}
</script>

<template>
  <div
    class="relative flex border-b border-gray-200/80 bg-gray-50/70 text-[10px] select-none dark:border-dark-800 dark:bg-dark-900/60"
    data-testid="trajectory-timeline"
  >
    <!-- Left: Lane Labels -->
    <div class="flex w-12 shrink-0 flex-col justify-between border-r border-gray-200/80 py-1.5 pr-1.5 text-right font-mono font-medium text-gray-400 dark:border-dark-800 dark:text-dark-500">
      <span class="h-3.5 leading-3.5">Input</span>
      <span class="h-3.5 leading-3.5">Model</span>
      <span class="h-3.5 leading-3.5">Tools</span>
    </div>

    <!-- Right: Multi-lane Track -->
    <div class="relative flex-1 py-1.5 px-1 overflow-visible h-12">
      <!-- Background Guide Lines for Lanes -->
      <div class="absolute inset-x-0 top-1.5 h-3.5 border-b border-dashed border-gray-200/50 pointer-events-none dark:border-dark-800/50" />
      <div class="absolute inset-x-0 top-5 h-3.5 border-b border-dashed border-gray-200/50 pointer-events-none dark:border-dark-800/50" />

      <!-- Spans -->
      <div
        v-for="span in spans"
        :key="span.record.id"
        class="absolute rounded-[2px] cursor-pointer transition-all duration-100 group"
        :class="[
          span.colorClass,
          selectedRecordId === span.record.id
            ? 'z-10 ring-2 ring-blue-500 ring-offset-1 dark:ring-offset-dark-900 shadow-sm opacity-100'
            : 'opacity-85 hover:opacity-100 hover:ring-1 hover:ring-blue-400',
          span.record.kind === 'assistant' ? 'border border-blue-400/80 dark:border-blue-400/60 shadow-2xs' : '',
        ]"
        :style="getSpanStyle(span)"
        @mouseenter="handleSpanEnter(span, $event)"
        @mouseleave="handleSpanLeave"
        @click="emit('select', span.record)"
      />

      <!-- Dark Hover Tooltip (图 3 原版同款) -->
      <div
        v-if="hoveredSpan"
        class="pointer-events-none absolute z-50 flex flex-col gap-0.5 rounded-lg border border-gray-700/80 bg-gray-900/95 px-2.5 py-1.5 font-mono text-[11px] text-white shadow-2xl backdrop-blur-xs -translate-x-1/2 whitespace-nowrap"
        :style="tooltipStyle"
      >
        <div class="font-bold tracking-wider text-gray-200 uppercase text-xs">
          {{ hoveredSpan.record.kind }}
        </div>
        <div class="text-[10px] text-gray-300">
          {{ formatRange(hoveredSpan.record) }}
        </div>
        <div class="text-[10px] text-gray-300">
          Total {{ formatDuration(hoveredSpan.record.durationMs || 0) }}
          <template v-if="hoveredSpan.record.ttftMs && hoveredSpan.record.decodingMs">
            · TTFT {{ formatDuration(hoveredSpan.record.ttftMs) }} · Decoding {{ formatDuration(hoveredSpan.record.decodingMs) }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
