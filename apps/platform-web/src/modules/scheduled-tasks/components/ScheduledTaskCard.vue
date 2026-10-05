<script setup lang="ts">
import { computed, ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import type { ScheduledTask } from "../types";
import { describeCron } from "../utils/cron";
import { formatDisplayTime } from "../utils/timezone";

const props = defineProps<{
  task: ScheduledTask;
  canWrite: boolean;
  triggering?: boolean;
}>();

const emit = defineEmits<{
  (e: "edit", task: ScheduledTask): void;
  (e: "togglePause", task: ScheduledTask): void;
  (e: "trigger", task: ScheduledTask): void;
  (e: "viewRuns", task: ScheduledTask): void;
  (e: "delete", task: ScheduledTask): void;
}>();

const confirmDeleting = ref(false);

const GRADIENT_LIST = [
  "from-emerald-500/80 to-teal-600/90 text-emerald-100",
  "from-blue-500/80 to-indigo-600/90 text-blue-100",
  "from-violet-500/80 to-purple-600/90 text-violet-100",
  "from-amber-500/80 to-orange-600/90 text-amber-100",
  "from-rose-500/80 to-pink-600/90 text-rose-100",
  "from-cyan-500/80 to-blue-600/90 text-cyan-100",
];

const avatarGradient = computed(() => {
  const key = props.task.agent_key || props.task.title;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash << 5) - hash + key.charCodeAt(i);
  }
  const index = Math.abs(hash) % GRADIENT_LIST.length;
  return GRADIENT_LIST[index];
});

const avatarLetter = computed(() => {
  const name = props.task.title.trim() || props.task.agent_key;
  return name.charAt(0).toUpperCase();
});

const statusTone = computed(() => {
  switch (props.task.schedule_status) {
    case "active":
      return "success";
    case "paused":
      return "warning";
    case "exhausted":
      return "neutral";
    default:
      return "neutral";
  }
});

const statusLabel = computed(() => {
  switch (props.task.schedule_status) {
    case "active":
      return "计划运行中";
    case "paused":
      return "已暂停";
    case "exhausted":
      return "单次已完成";
    default:
      return props.task.schedule_status;
  }
});

const scheduleDescription = computed(() => {
  if (props.task.schedule_type === "cron") {
    return describeCron(props.task.cron || "");
  }
  return `单次: ${formatDisplayTime(props.task.run_at, props.task.timezone)}`;
});

function handleDelete() {
  if (!confirmDeleting.value) {
    confirmDeleting.value = true;
    setTimeout(() => {
      confirmDeleting.value = false;
    }, 3500);
    return;
  }
  emit("delete", props.task);
  confirmDeleting.value = false;
}
</script>

<template>
  <div
    class="group relative rounded-2xl border border-border/70 bg-surface/90 p-5 shadow-xs backdrop-blur-xs transition-all duration-200 hover:-translate-y-0.5 hover:border-border-hover hover:shadow-md dark:border-dark-700/80 dark:bg-dark-900/80 flex flex-col justify-between gap-4"
  >
    <!-- 头部：微头像、标题与状态 Pill -->
    <div class="space-y-3">
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-center gap-3 min-w-0">
          <!-- 渐变毛玻璃头像 -->
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-inner font-bold text-sm select-none"
            :class="avatarGradient"
          >
            {{ avatarLetter }}
          </div>
          <div class="min-w-0">
            <h3
              class="text-sm font-semibold text-foreground tracking-tight line-clamp-1 group-hover:text-primary transition-colors"
              :title="task.title"
            >
              {{ task.title }}
            </h3>
            <div
              class="flex items-center gap-1.5 mt-0.5 text-[11px] text-muted-foreground font-mono"
            >
              <span>Agent:</span>
              <span
                class="text-foreground/80 font-medium truncate max-w-[140px]"
                :title="task.agent_key"
              >
                {{ task.agent_key }}
              </span>
            </div>
          </div>
        </div>

        <StatusPill :tone="statusTone" class="shrink-0 font-medium">
          {{ statusLabel }}
        </StatusPill>
      </div>

      <!-- 提示词引用区 (Quote block) -->
      <div
        class="relative rounded-xl bg-surface-subtle/80 px-3 py-2 border-l-2 border-primary/60 dark:bg-dark-800/50"
      >
        <p
          class="text-xs text-muted-foreground line-clamp-2 leading-relaxed"
          :title="task.prompt"
        >
          “{{ task.prompt }}”
        </p>
      </div>
    </div>

    <!-- 关键属性指标芯片阵列 (Badges/Chips) -->
    <div class="grid grid-cols-2 gap-2 text-xs">
      <div
        class="rounded-xl border border-border/50 bg-surface/50 p-2.5 space-y-1 dark:bg-dark-800/40"
      >
        <div class="flex items-center gap-1 text-[11px] text-muted-foreground">
          <BaseIcon name="refresh" size="xs" class="text-primary/80" />
          <span>执行周期</span>
        </div>
        <div
          class="font-medium text-foreground truncate text-xs"
          :title="scheduleDescription"
        >
          {{ scheduleDescription }}
        </div>
      </div>

      <div
        class="rounded-xl border border-border/50 bg-surface/50 p-2.5 space-y-1 dark:bg-dark-800/40"
      >
        <div class="flex items-center gap-1 text-[11px] text-muted-foreground">
          <BaseIcon name="activity" size="xs" class="text-amber-500/80" />
          <span>下次触发</span>
        </div>
        <div class="font-mono text-xs text-foreground font-medium truncate">
          {{
            task.next_run_at
              ? formatDisplayTime(task.next_run_at, task.timezone)
              : "—"
          }}
        </div>
      </div>
    </div>

    <!-- 底部操作按钮栏（分层设计：主操作 + 工具项） -->
    <div
      class="flex items-center justify-between gap-2 pt-3 border-t border-border/40"
    >
      <div class="flex items-center gap-2">
        <BaseButton
          v-if="canWrite"
          variant="primary"
          size="xs"
          :loading="triggering"
          class="rounded-lg shadow-xs"
          @click="emit('trigger', task)"
        >
          立即运行
        </BaseButton>

        <BaseButton
          variant="secondary"
          size="xs"
          class="rounded-lg"
          @click="emit('viewRuns', task)"
        >
          运行历史
        </BaseButton>
      </div>

      <!-- 次级操作组 -->
      <div v-if="canWrite" class="flex items-center gap-0.5">
        <button
          v-if="task.schedule_status !== 'exhausted'"
          type="button"
          class="p-1.5 rounded-lg text-muted-foreground hover:bg-muted/70 hover:text-foreground transition-colors text-xs"
          :title="task.enabled ? '暂停任务' : '恢复任务'"
          @click="emit('togglePause', task)"
        >
          {{ task.enabled ? "暂停" : "恢复" }}
        </button>

        <button
          type="button"
          class="p-1.5 rounded-lg text-muted-foreground hover:bg-muted/70 hover:text-foreground transition-colors text-xs"
          title="编辑任务"
          @click="emit('edit', task)"
        >
          编辑
        </button>

        <button
          type="button"
          class="px-2 py-1 rounded-lg text-xs transition-colors"
          :class="
            confirmDeleting
              ? 'bg-rose-500/10 text-rose-600 font-semibold'
              : 'text-muted-foreground hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20'
          "
          :title="confirmDeleting ? '点击确认删除' : '删除任务'"
          @click="handleDelete"
        >
          {{ confirmDeleting ? "确认?" : "删除" }}
        </button>
      </div>
    </div>
  </div>
</template>
