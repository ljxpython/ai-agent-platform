<script setup lang="ts">
import { computed } from "vue";
import type { TrajectoryRecord, TrajectoryRecordKind } from "../../trajectory/types";

const props = defineProps<{
  records: TrajectoryRecord[];
  selectedRecordId: string | null;
}>();

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

// 计算时间片在横轴上的百分比布局
const spans = computed<TimelineSpan[]>(() => {
  const total = props.records.length;
  if (total === 0) return [];

  // 如果有实际耗时总和则按真实耗时占比，否则按步进序列均分
  const hasRealDuration = props.records.some(
    (r) => typeof r.durationMs === "number" && r.durationMs > 0,
  );

  let cumulativeOffset = 0;
  const result: TimelineSpan[] = [];

  if (hasRealDuration) {
    const totalDuration = props.records.reduce(
      (sum, r) => sum + (r.durationMs && r.durationMs > 0 ? r.durationMs : 100),
      0,
    );
    for (const record of props.records) {
      const dur = record.durationMs && record.durationMs > 0 ? record.durationMs : 100;
      const leftPercent = (cumulativeOffset / totalDuration) * 100;
      const widthPercent = Math.max((dur / totalDuration) * 100, 1.2);
      cumulativeOffset += dur;
      result.push({
        record,
        lane: getLaneForKind(record.kind),
        leftPercent,
        widthPercent,
        colorClass: getColorClass(record),
      });
    }
  } else {
    // 均分切片模式
    const stepPercent = 100 / total;
    for (let i = 0; i < total; i++) {
      const record = props.records[i]!;
      result.push({
        record,
        lane: getLaneForKind(record.kind),
        leftPercent: i * stepPercent,
        widthPercent: Math.max(stepPercent * 0.95, 1.5),
        colorClass: getColorClass(record),
      });
    }
  }

  return result;
});
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
    <div class="relative flex-1 py-1.5 px-1 overflow-hidden h-12">
      <!-- Background Guide Lines for Lanes -->
      <div class="absolute inset-x-0 top-1.5 h-3.5 border-b border-dashed border-gray-200/40 pointer-events-none dark:border-dark-800/40" />
      <div class="absolute inset-x-0 top-5 h-3.5 border-b border-dashed border-gray-200/40 pointer-events-none dark:border-dark-800/40" />

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
        ]"
        :style="{
          left: `${span.leftPercent}%`,
          width: `${span.widthPercent}%`,
          top: span.lane === 0 ? '6px' : span.lane === 1 ? '20px' : '34px',
          height: '9px',
        }"
        :title="`Turn ${span.record.turnIndex} · [${span.record.kind.toUpperCase()}] ${span.record.name} - ${span.record.summary}`"
        @click="emit('select', span.record)"
      />
    </div>
  </div>
</template>
