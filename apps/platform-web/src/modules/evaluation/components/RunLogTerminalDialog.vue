<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import type {
  EvalRunItem,
  EvalRunLogEntry,
  EvalRunLogsResponse,
  EvalRunProgress,
} from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  run: EvalRunItem | null;
  fetchLogs: (
    runId: string,
    params?: { after_seq?: number; limit?: number },
  ) => Promise<EvalRunLogsResponse | null>;
}>();

const emit = defineEmits<{
  close: [];
}>();

const logs = ref<EvalRunLogEntry[]>([]);
const lastSeq = ref(0);
const liveStatus = ref("");
const liveProgress = ref<EvalRunProgress | null>(null);
const loading = ref(false);
const loadError = ref("");
const keyword = ref("");
const levelFilter = ref("ALL");
const autoScroll = ref(true);
const copied = ref(false);
const logContainerEl = ref<HTMLElement | null>(null);

let pollTimer: ReturnType<typeof setInterval> | null = null;
const seenSeqs = new Set<number>();

const levelOptions = [
  { label: "全部级别", value: "ALL" },
  { label: "INFO", value: "INFO" },
  { label: "WARN", value: "WARN" },
  { label: "ERROR", value: "ERROR" },
];

const isActiveStatus = computed(() =>
  ["queued", "running", "rescoring"].includes(
    liveStatus.value || props.run?.status || "",
  ),
);

const effectiveStatus = computed(
  () => liveStatus.value || props.run?.status || "unknown",
);

const filteredLogs = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  return logs.value.filter((entry) => {
    if (levelFilter.value !== "ALL" && entry.level !== levelFilter.value) {
      return false;
    }
    if (!kw) return true;
    return (
      entry.message.toLowerCase().includes(kw) ||
      (entry.case_key ?? "").toLowerCase().includes(kw)
    );
  });
});

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function scrollToBottom() {
  if (!autoScroll.value) return;
  await nextTick();
  if (logContainerEl.value) {
    logContainerEl.value.scrollTop = logContainerEl.value.scrollHeight;
  }
}

async function pullIncremental(reset = false) {
  if (!props.run) return;
  if (reset) {
    loading.value = true;
    loadError.value = "";
  }
  try {
    const res = await props.fetchLogs(props.run.id, {
      after_seq: reset ? 0 : lastSeq.value,
      limit: 300,
    });
    if (!res) return;
    liveStatus.value = res.status;
    liveProgress.value = res.progress;
    if (res.logs.length > 0) {
      const appended: EvalRunLogEntry[] = [];
      for (const item of res.logs) {
        if (!seenSeqs.has(item.seq)) {
          seenSeqs.add(item.seq);
          appended.push(item);
        }
      }
      if (appended.length > 0) {
        logs.value = reset ? appended : [...logs.value, ...appended];
        await scrollToBottom();
      }
      lastSeq.value = Math.max(lastSeq.value, res.last_seq);
    }
    if (!["queued", "running", "rescoring"].includes(res.status)) {
      stopPolling();
    }
  } catch (err) {
    loadError.value =
      err instanceof Error ? err.message : "拉取执行日志失败，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

function startPolling() {
  stopPolling();
  if (!props.show || !props.run) return;
  if (
    !["queued", "running", "rescoring"].includes(
      liveStatus.value || props.run.status,
    )
  ) {
    return;
  }
  pollTimer = setInterval(() => {
    void pullIncremental(false);
  }, 2000);
}

watch(
  () => [props.show, props.run?.id] as const,
  async ([open, runId]) => {
    stopPolling();
    logs.value = [];
    seenSeqs.clear();
    lastSeq.value = 0;
    loadError.value = "";
    liveStatus.value = props.run?.status ?? "";
    liveProgress.value =
      (props.run?.summary_metrics?.progress as EvalRunProgress | undefined) ??
      null;
    if (open && runId) {
      await pullIncremental(true);
      startPolling();
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  stopPolling();
});

function statusTone(st: string) {
  if (st === "completed" || st === "success") return "success";
  if (st === "failed" || st === "error") return "danger";
  if (st === "running" || st === "queued" || st === "rescoring") return "info";
  return "warning";
}

function levelClass(level: string) {
  if (level === "ERROR") return "text-rose-400 font-semibold";
  if (level === "WARN") return "text-amber-300 font-semibold";
  return "text-cyan-300";
}

function formatTime(iso: string | null) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString();
}

async function copyAllLogs() {
  const text = filteredLogs.value
    .map(
      (l) =>
        `${l.seq}\t${formatTime(l.created_at)}\t[${l.level}]\t${l.case_key ? `[${l.case_key}] ` : ""}${l.message}`,
    )
    .join("\n");
  try {
    await navigator.clipboard.writeText(text);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1800);
  } catch {
    copied.value = false;
  }
}
</script>

<template>
  <BaseDialog
    :show="show"
    width="wide"
    :title="
      run
        ? `打擂实时执行日志终端 · #${run.id.slice(0, 8)} (${run.suite_name || run.target_graph_id})`
        : '打擂执行日志终端'
    "
    @close="emit('close')"
  >
    <div class="space-y-3 text-xs">
      <!-- 顶部状态与实时进度条 -->
      <div
        class="p-3 rounded-xl border border-gray-200 dark:border-dark-700 bg-gray-50/80 dark:bg-dark-800/60 space-y-2"
      >
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="size-2 rounded-full"
              :class="
                isActiveStatus
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-gray-400 dark:bg-dark-500'
              "
            />
            <StatusPill :tone="statusTone(effectiveStatus)">{{
              effectiveStatus
            }}</StatusPill>
            <span
              v-if="liveProgress"
              class="font-mono text-gray-600 dark:text-dark-300"
            >
              进度 {{ liveProgress.done }}/{{
                liveProgress.active_total ?? liveProgress.total
              }}
              ({{ liveProgress.percent }}%) · 运行中
              {{ liveProgress.running }} · 待执行 {{ liveProgress.pending }} ·
              失败/异常
              {{ liveProgress.failed + liveProgress.error }}
            </span>
          </div>
          <span class="text-[11px] text-gray-500 font-mono">
            共 {{ logs.length }} 条日志
            <span v-if="isActiveStatus">· 2s 自动增量刷新中</span>
          </span>
        </div>

        <div
          v-if="liveProgress"
          class="h-1.5 w-full rounded-full bg-gray-200 dark:bg-dark-700 overflow-hidden"
        >
          <div
            class="h-full bg-primary-600 transition-all duration-300"
            :style="{ width: `${liveProgress.percent}%` }"
          />
        </div>
      </div>

      <!-- 过滤与控制栏 -->
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex flex-wrap items-center gap-2">
          <div class="w-56">
            <BaseInput
              v-model="keyword"
              placeholder="按用例 case_key 或日志关键词过滤..."
            />
          </div>
          <div class="w-36">
            <BaseSelect
              v-model="levelFilter"
              :options="levelOptions"
              placeholder="级别"
            />
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label
            class="inline-flex items-center gap-1.5 text-gray-600 dark:text-dark-300 cursor-pointer"
          >
            <input v-model="autoScroll" type="checkbox" />
            <span>自动滚到底部</span>
          </label>
          <BaseButton
            size="sm"
            variant="secondary"
            @click="pullIncremental(false)"
          >
            手动刷新
          </BaseButton>
          <BaseButton
            size="sm"
            variant="secondary"
            :disabled="!filteredLogs.length"
            @click="copyAllLogs"
          >
            {{ copied ? "已复制 ✓" : "复制日志" }}
          </BaseButton>
        </div>
      </div>

      <div
        v-if="loadError"
        class="p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300"
      >
        {{ loadError }}
      </div>

      <!-- 深色终端日志窗口 -->
      <div
        ref="logContainerEl"
        class="h-96 overflow-y-auto rounded-xl bg-slate-950 text-slate-100 border border-slate-800 p-3 font-mono text-[11px] leading-relaxed space-y-0.5 shadow-inner"
      >
        <div
          v-if="loading && !logs.length"
          class="h-full flex items-center justify-center text-slate-400"
        >
          正在加载执行日志流...
        </div>
        <div
          v-else-if="!filteredLogs.length"
          class="h-full flex items-center justify-center text-slate-500"
        >
          {{
            logs.length
              ? "当前过滤条件下暂无匹配日志"
              : "暂无执行日志（任务排队中或历史旧运行未启用持久化日志）"
          }}
        </div>
        <div
          v-for="entry in filteredLogs"
          v-else
          :key="entry.seq"
          class="flex items-start gap-2 px-1.5 py-0.5 rounded hover:bg-slate-900/70 break-all"
        >
          <span class="text-slate-500 select-none w-8 text-right shrink-0">{{
            entry.seq
          }}</span>
          <span class="text-slate-400 shrink-0">{{
            formatTime(entry.created_at)
          }}</span>
          <span class="w-12 shrink-0" :class="levelClass(entry.level)"
            >[{{ entry.level }}]</span
          >
          <span
            v-if="entry.case_key"
            class="px-1.5 py-0.2 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/60 shrink-0"
          >
            {{ entry.case_key }}
          </span>
          <span class="text-slate-100 whitespace-pre-wrap">{{
            entry.message
          }}</span>
        </div>
      </div>

      <div class="flex justify-end pt-1">
        <BaseButton variant="secondary" @click="emit('close')">
          关闭终端
        </BaseButton>
      </div>
    </div>
  </BaseDialog>
</template>
