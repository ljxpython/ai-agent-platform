<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import { platformHttpClient } from "@/services/http/client";
import { buildLangfuseTraceUrl } from "@/services/observability/langfuse-url";
import { useThemeStore } from "@/stores/theme";

interface TraceLogEntry {
  timestamp: string;
  nanos: string;
  service: string;
  level: string;
  event: string;
  summary: string;
  span_id: string;
  duration_ms?: number | null;
  payload: Record<string, unknown>;
  raw: string;
}

interface TraceLogsData {
  trace_id: string;
  total: number;
  duration_ms?: number | null;
  services: string[];
  logs: TraceLogEntry[];
  error?: string | null;
}

type ViewTab = "native" | "grafana";

const route = useRoute();
const router = useRouter();
const themeStore = useThemeStore();

// 演示用生产真实 Trace ID
const DEMO_TRACE_ID = "54aaf459b9c5415b90370e5874dbb255";

const traceQueryInput = ref(
  (route.query.traceId as string | undefined)?.trim() || "",
);
const activeTraceId = computed(
  () => (route.query.traceId as string | undefined)?.trim() || "",
);

// 视图 Tab 切换：native（极速大厂时间轴） / grafana（Explore 深度透视）
const currentTab = ref<ViewTab>("native");

const loading = ref(false);
const traceData = ref<TraceLogsData | null>(null);
const expandedLogNanos = ref<Set<string>>(new Set());
const copiedTrace = ref(false);
const copiedAll = ref(false);

// 客户端即时搜索与过滤状态
const keywordQuery = ref("");
const selectedLevel = ref<"all" | "error" | "warn" | "info">("all");
const selectedService = ref<string>("all");

// Grafana 内嵌与跳转配置
const rawDashboardUrl =
  (import.meta.env.VITE_GRAFANA_DASHBOARD_URL as string | undefined)?.trim() ||
  "http://49.233.222.54:3000";

const grafanaOrigin = computed(() => {
  try {
    return new URL(rawDashboardUrl).origin;
  } catch {
    return "http://49.233.222.54:3000";
  }
});

const iframeLoading = ref(true);
const iframeKey = ref(0);
const isFullscreen = ref(false);
const iframeContainer = ref<HTMLElement | null>(null);
let iframeTimeoutTimer: ReturnType<typeof setTimeout> | null = null;

const exploreEmbedUrl = computed(() => {
  const logExpr = activeTraceId.value
    ? `{job=~"systemd-journal|app-file-logs"} |= "${activeTraceId.value}"`
    : `{job=~"systemd-journal|app-file-logs"}`;
  const exploreParam = JSON.stringify({
    datasource: "Loki",
    queries: [{ refId: "A", expr: logExpr }],
    range: { from: "now-6h", to: "now" },
  });
  const theme = themeStore.mode === "dark" ? "dark" : "light";
  return `${grafanaOrigin.value}/explore?orgId=1&kiosk=1&theme=${theme}&left=${encodeURIComponent(exploreParam)}`;
});

const exploreExternalUrl = computed(() => {
  const logExpr = activeTraceId.value
    ? `{job=~"systemd-journal|app-file-logs"} |= "${activeTraceId.value}"`
    : `{job=~"systemd-journal|app-file-logs"}`;
  const exploreParam = JSON.stringify({
    datasource: "Loki",
    queries: [{ refId: "A", expr: logExpr }],
    range: { from: "now-6h", to: "now" },
  });
  return `${grafanaOrigin.value}/explore?orgId=1&left=${encodeURIComponent(exploreParam)}`;
});

const langfuseTraceUrl = computed(() => {
  return buildLangfuseTraceUrl(activeTraceId.value);
});

function handleIframeLoaded() {
  if (iframeTimeoutTimer) {
    clearTimeout(iframeTimeoutTimer);
    iframeTimeoutTimer = null;
  }
  iframeLoading.value = false;
}

function resetIframe() {
  iframeLoading.value = true;
  iframeKey.value += 1;
  if (iframeTimeoutTimer) {
    clearTimeout(iframeTimeoutTimer);
  }
  iframeTimeoutTimer = setTimeout(() => {
    iframeLoading.value = false;
  }, 2500);
}

// 数据统计与大厂指标
const errorCount = computed(() => {
  return (traceData.value?.logs || []).filter((l) => l.level === "error")
    .length;
});

const warnCount = computed(() => {
  return (traceData.value?.logs || []).filter((l) => l.level === "warn").length;
});

const maxLogDurationMs = computed(() => {
  const durations = (traceData.value?.logs || [])
    .map((l) => l.duration_ms)
    .filter((d): d is number => typeof d === "number" && d > 0);
  return durations.length ? Math.max(...durations) : 100;
});

// 前端即时搜索与过滤
const filteredLogs = computed(() => {
  if (!traceData.value?.logs) return [];
  const q = keywordQuery.value.trim().toLowerCase();

  return traceData.value.logs.filter((log) => {
    // 级别筛选
    if (selectedLevel.value === "error" && log.level !== "error") return false;
    if (
      selectedLevel.value === "warn" &&
      log.level !== "warn" &&
      log.level !== "error"
    )
      return false;
    if (selectedLevel.value === "info" && log.level !== "info") return false;

    // 服务筛选
    if (
      selectedService.value !== "all" &&
      log.service !== selectedService.value
    )
      return false;

    // 关键词过滤
    if (q) {
      const match =
        log.summary.toLowerCase().includes(q) ||
        log.service.toLowerCase().includes(q) ||
        log.event.toLowerCase().includes(q) ||
        log.span_id.toLowerCase().includes(q) ||
        log.raw.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });
});

async function fetchTraceLogs(traceId: string) {
  if (!traceId) {
    traceData.value = null;
    return;
  }
  loading.value = true;
  try {
    const res = await platformHttpClient.get<TraceLogsData>(
      `/api/v1/observability/traces/${encodeURIComponent(traceId)}/logs`,
    );
    traceData.value = res.data;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : "network_error";
    traceData.value = {
      trace_id: traceId,
      total: 0,
      services: [],
      logs: [],
      error: errorMsg,
    };
  } finally {
    loading.value = false;
  }
}

function handleSearchTrace() {
  const trimmed = traceQueryInput.value.trim();
  if (trimmed === activeTraceId.value) {
    void fetchTraceLogs(trimmed);
    if (currentTab.value === "grafana") resetIframe();
    return;
  }
  void router.push({
    query: {
      ...route.query,
      traceId: trimmed || undefined,
    },
  });
}

function handleClearTrace() {
  traceQueryInput.value = "";
  traceData.value = null;
  keywordQuery.value = "";
  selectedLevel.value = "all";
  selectedService.value = "all";
  void router.push({
    query: {
      ...route.query,
      traceId: undefined,
    },
  });
}

function applyDemoTrace() {
  traceQueryInput.value = DEMO_TRACE_ID;
  handleSearchTrace();
}

function toggleLogDetail(nanos: string) {
  if (expandedLogNanos.value.has(nanos)) {
    expandedLogNanos.value.delete(nanos);
  } else {
    expandedLogNanos.value.add(nanos);
  }
}

function toggleAllLogs() {
  if (!traceData.value?.logs) return;
  if (expandedLogNanos.value.size >= traceData.value.logs.length) {
    expandedLogNanos.value.clear();
  } else {
    expandedLogNanos.value = new Set(traceData.value.logs.map((l) => l.nanos));
  }
}

async function copyTraceId() {
  if (!activeTraceId.value) return;
  try {
    await navigator.clipboard.writeText(activeTraceId.value);
    copiedTrace.value = true;
    setTimeout(() => {
      copiedTrace.value = false;
    }, 2000);
  } catch {
    // 忽略
  }
}

async function copyAllLogs() {
  if (!traceData.value?.logs) return;
  try {
    const text = JSON.stringify(traceData.value, null, 2);
    await navigator.clipboard.writeText(text);
    copiedAll.value = true;
    setTimeout(() => {
      copiedAll.value = false;
    }, 2000);
  } catch {
    // 忽略
  }
}

function openGrafanaExplore() {
  window.open(exploreExternalUrl.value, "_blank", "noopener,noreferrer");
}

function goToDashboard() {
  void router.push({ name: "workspace-observability" });
}

async function toggleFullscreen() {
  if (!iframeContainer.value) return;
  try {
    if (!document.fullscreenElement) {
      await iframeContainer.value.requestFullscreen();
      isFullscreen.value = true;
    } else {
      await document.exitFullscreen();
      isFullscreen.value = false;
    }
  } catch {
    // 忽略
  }
}

function onFullscreenChange() {
  isFullscreen.value =
    Boolean(document.fullscreenElement) &&
    document.fullscreenElement === iframeContainer.value;
}

watch(
  () => route.query.traceId,
  (newId) => {
    const id = (newId as string | undefined)?.trim() || "";
    traceQueryInput.value = id;
    void fetchTraceLogs(id);
    if (currentTab.value === "grafana") resetIframe();
  },
  { immediate: true },
);

watch(currentTab, (tab) => {
  if (tab === "grafana") {
    resetIframe();
  }
});

onMounted(() => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
  if (activeTraceId.value) {
    void fetchTraceLogs(activeTraceId.value);
  }
});

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  if (iframeTimeoutTimer) {
    clearTimeout(iframeTimeoutTimer);
  }
});
</script>

<template>
  <section
    class="pw-page-shell flex flex-col min-h-[calc(100vh-4rem)] space-y-4"
  >
    <PageHeader
      eyebrow="Governance"
      title="链路诊断中心"
      description="基于 W3C TraceContext + Loki 毫秒级直连代理。输入全局 Trace ID 即时拉取跨微服务调用日志流与可视化耗时瀑布。"
    >
      <template #actions>
        <div class="flex items-center gap-2">
          <div class="w-64 sm:w-72">
            <BaseInput
              v-model="traceQueryInput"
              placeholder="输入 32 位 Trace ID..."
              @keydown.enter="handleSearchTrace"
            />
          </div>
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="loading"
            @click="handleSearchTrace"
          >
            <BaseIcon name="search" class="w-4 h-4 mr-1" />
            {{ loading ? "检索中..." : "诊断" }}
          </BaseButton>
          <BaseButton
            v-if="traceQueryInput || activeTraceId"
            variant="ghost"
            size="sm"
            @click="handleClearTrace"
          >
            清空
          </BaseButton>
          <BaseButton variant="secondary" size="sm" @click="goToDashboard">
            <BaseIcon name="activity" class="w-4 h-4 mr-1 text-emerald-500" />
            指标大盘
          </BaseButton>
        </div>
      </template>
    </PageHeader>

    <!-- 诊断状态条与视角 Tab 切换器 -->
    <div
      class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-2.5 bg-sky-50/70 dark:bg-sky-950/30 border border-sky-200/80 dark:border-sky-800/60 rounded-xl text-xs shadow-xs"
    >
      <div class="flex items-center gap-2 flex-wrap">
        <span
          class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse"
        />
        <span class="font-medium text-gray-700 dark:text-dark-200"
          >诊断 Trace ID:</span
        >
        <code
          v-if="activeTraceId"
          class="px-2.5 py-1 bg-white dark:bg-dark-900 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/80 rounded-md font-mono font-semibold cursor-pointer hover:bg-sky-50 dark:hover:bg-dark-800 hover:border-sky-300 dark:hover:border-sky-600 transition shadow-2xs"
          title="点击复制 Trace ID"
          @click="copyTraceId"
        >
          {{ activeTraceId }}
        </code>
        <span v-else class="text-gray-400 italic">未指定</span>
        <span
          v-if="copiedTrace"
          class="text-emerald-600 dark:text-emerald-400 font-bold ml-1"
          >✓ 已复制!</span
        >
      </div>

      <!-- 视角切换 Tab 切换器（双剑合璧） -->
      <div class="flex items-center gap-2 self-start sm:self-auto">
        <div
          class="inline-flex p-0.5 bg-white/80 dark:bg-dark-900/80 border border-gray-200 dark:border-dark-700 rounded-lg shadow-2xs"
        >
          <button
            type="button"
            class="px-3 py-1 text-xs font-semibold rounded-md transition-all flex items-center gap-1.5"
            :class="
              currentTab === 'native'
                ? 'bg-sky-600 text-white shadow-xs'
                : 'text-gray-600 dark:text-dark-300 hover:text-gray-900 dark:hover:text-white'
            "
            @click="currentTab = 'native'"
          >
            <BaseIcon name="sparkle" class="w-3.5 h-3.5" />
            极速时间轴 (毫秒直出)
          </button>
          <button
            type="button"
            class="px-3 py-1 text-xs font-semibold rounded-md transition-all flex items-center gap-1.5"
            :class="
              currentTab === 'grafana'
                ? 'bg-sky-600 text-white shadow-xs'
                : 'text-gray-600 dark:text-dark-300 hover:text-gray-900 dark:hover:text-white'
            "
            @click="currentTab = 'grafana'"
          >
            <BaseIcon name="globe" class="w-3.5 h-3.5" />
            Grafana Explore (深度透视)
          </button>
        </div>

        <a
          v-if="activeTraceId && langfuseTraceUrl"
          :href="langfuseTraceUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="hidden md:flex text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 hover:underline items-center gap-1 font-medium ml-2"
        >
          Langfuse 链路树 ↗
        </a>
      </div>
    </div>

    <!-- 未输入 Trace ID 时的排障获取指引卡片 -->
    <div
      v-if="!activeTraceId"
      class="p-4 bg-gray-50/90 dark:bg-dark-900/65 border border-gray-200 dark:border-dark-800 rounded-xl text-xs text-gray-600 dark:text-dark-300 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs"
    >
      <div class="space-y-1.5">
        <div
          class="flex items-center gap-2 font-medium text-gray-900 dark:text-white"
        >
          <BaseIcon
            name="info"
            class="w-4 h-4 text-sky-500 dark:text-sky-400"
          />
          <span class="font-semibold">Trace ID 获取途径与排障指引：</span>
        </div>
        <p class="text-gray-600 dark:text-dark-300 leading-relaxed">
          ①
          <b>对话出错时</b
          >：点击错误提示中的【查看详情】，在弹窗中一键复制或点击【微服务全链路日志】直达。<br />
          ② <b>系统审计中心</b>：在【平台管理 -> 审计】中查看每一条 API
          调用及任务执行记录的 Trace ID。<br />
          ③ <b>网络请求头</b>：F12 开发者工具查看任意 API 响应头的
          <code
            class="px-1.5 py-0.5 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded text-sky-600 dark:text-sky-400 font-mono text-[11px]"
            >x-trace-id</code
          >
          或
          <code
            class="px-1.5 py-0.5 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded text-sky-600 dark:text-sky-400 font-mono text-[11px]"
            >traceparent</code
          >。
        </p>
      </div>
      <div class="flex items-center gap-2 self-start md:self-auto shrink-0">
        <BaseButton variant="secondary" size="sm" @click="applyDemoTrace">
          <BaseIcon name="sparkle" class="w-4 h-4 mr-1 text-amber-500" />
          演示：载入生产真实 Trace
        </BaseButton>
      </div>
    </div>

    <!-- 视角 1: 原生极速时间轴 (大厂工业级可视化排障) -->
    <div v-if="currentTab === 'native'" class="flex-1 flex flex-col space-y-3">
      <!-- 大厂链路诊断概览四联卡片 (仅在有诊断数据时呈现) -->
      <div
        v-if="activeTraceId && traceData && traceData.logs.length > 0"
        class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs"
      >
        <!-- 耗时卡片 -->
        <div
          class="p-3 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl shadow-2xs flex flex-col justify-between"
        >
          <div
            class="text-gray-500 dark:text-dark-400 flex items-center justify-between"
          >
            <span>执行总耗时</span>
            <BaseIcon name="activity" class="w-3.5 h-3.5 text-sky-500" />
          </div>
          <div
            class="mt-2 text-lg font-bold font-mono text-gray-900 dark:text-white"
          >
            {{
              traceData.duration_ms ? `${traceData.duration_ms} ms` : "即时响应"
            }}
          </div>
          <div class="text-[11px] text-gray-400 dark:text-dark-400 mt-0.5">
            单步最大耗时: {{ maxLogDurationMs }} ms
          </div>
        </div>

        <!-- 日志条目卡片 -->
        <div
          class="p-3 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl shadow-2xs flex flex-col justify-between"
        >
          <div
            class="text-gray-500 dark:text-dark-400 flex items-center justify-between"
          >
            <span>关联调用日志</span>
            <BaseIcon name="file" class="w-3.5 h-3.5 text-indigo-500" />
          </div>
          <div
            class="mt-2 text-lg font-bold font-mono text-gray-900 dark:text-white"
          >
            {{
              filteredLogs.length === traceData.total
                ? traceData.total
                : `${filteredLogs.length} / ${traceData.total}`
            }}
            条
          </div>
          <div class="text-[11px] text-gray-400 dark:text-dark-400 mt-0.5">
            {{ keywordQuery ? "已启用关键词过滤" : "包含完整请求全链路" }}
          </div>
        </div>

        <!-- 涉及微服务卡片 -->
        <div
          class="p-3 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl shadow-2xs flex flex-col justify-between"
        >
          <div
            class="text-gray-500 dark:text-dark-400 flex items-center justify-between"
          >
            <span>拓扑涉及服务</span>
            <BaseIcon name="branch" class="w-3.5 h-3.5 text-purple-500" />
          </div>
          <div class="mt-1.5 flex items-center gap-1 flex-wrap">
            <span
              v-for="svc in traceData.services"
              :key="svc"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold"
              :class="
                svc === 'platform-api'
                  ? 'bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-950 dark:text-sky-300 dark:border-sky-800'
                  : 'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'
              "
            >
              {{ svc }}
            </span>
          </div>
          <div class="text-[11px] text-gray-400 dark:text-dark-400 mt-1">
            跨越 {{ traceData.services.length }} 个分布式节点
          </div>
        </div>

        <!-- 异常与健康状态卡片 -->
        <div
          class="p-3 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl shadow-2xs flex flex-col justify-between"
        >
          <div
            class="text-gray-500 dark:text-dark-400 flex items-center justify-between"
          >
            <span>链路健康状态</span>
            <BaseIcon
              :name="errorCount > 0 ? 'alert' : 'check'"
              class="w-3.5 h-3.5"
              :class="errorCount > 0 ? 'text-red-500' : 'text-emerald-500'"
            />
          </div>
          <div class="mt-2 text-base font-bold flex items-center gap-1.5">
            <span v-if="errorCount > 0" class="text-red-600 dark:text-red-400">
              {{ errorCount }} 项错误 / {{ warnCount }} 告警
            </span>
            <span v-else class="text-emerald-600 dark:text-emerald-400">
              调用健康 (0 错误)
            </span>
          </div>
          <div class="text-[11px] text-gray-400 dark:text-dark-400 mt-0.5">
            {{ errorCount > 0 ? "点击卡片展开异常排查" : "全链路返回正常" }}
          </div>
        </div>
      </div>

      <!-- 交互式排障筛选工具栏 -->
      <div
        v-if="activeTraceId && traceData && traceData.logs.length > 0"
        class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl shadow-2xs text-xs"
      >
        <div class="flex items-center gap-2 flex-1 flex-wrap">
          <!-- 关键词即时搜索输入框 -->
          <div class="w-full sm:w-60">
            <BaseInput
              v-model="keywordQuery"
              placeholder="按关键字/路径/错误搜索..."
            />
          </div>

          <!-- 级别筛选药丸 -->
          <div
            class="flex items-center bg-gray-100 dark:bg-dark-800 p-0.5 rounded-lg border border-gray-200 dark:border-dark-700"
          >
            <button
              type="button"
              class="px-2 py-1 rounded text-[11px] font-medium transition"
              :class="
                selectedLevel === 'all'
                  ? 'bg-white dark:bg-dark-900 text-gray-900 dark:text-white shadow-2xs font-semibold'
                  : 'text-gray-500 hover:text-gray-800 dark:hover:text-white'
              "
              @click="selectedLevel = 'all'"
            >
              全部 ({{ traceData.total }})
            </button>
            <button
              v-if="errorCount > 0"
              type="button"
              class="px-2 py-1 rounded text-[11px] font-medium transition text-red-600 dark:text-red-400"
              :class="
                selectedLevel === 'error'
                  ? 'bg-red-50 dark:bg-red-950/60 shadow-2xs font-semibold'
                  : 'hover:text-red-700'
              "
              @click="selectedLevel = 'error'"
            >
              错误 ({{ errorCount }})
            </button>
            <button
              type="button"
              class="px-2 py-1 rounded text-[11px] font-medium transition"
              :class="
                selectedLevel === 'info'
                  ? 'bg-white dark:bg-dark-900 text-gray-900 dark:text-white shadow-2xs font-semibold'
                  : 'text-gray-500 hover:text-gray-800 dark:hover:text-white'
              "
              @click="selectedLevel = 'info'"
            >
              INFO
            </button>
          </div>

          <!-- 微服务筛选下拉/药丸 -->
          <div
            v-if="traceData.services.length > 1"
            class="flex items-center gap-1"
          >
            <button
              type="button"
              class="px-2 py-1 rounded text-[11px] border transition"
              :class="
                selectedService === 'all'
                  ? 'bg-gray-200 dark:bg-dark-700 text-gray-900 dark:text-white border-transparent font-semibold'
                  : 'bg-white dark:bg-dark-900 text-gray-500 border-gray-200 dark:border-dark-700 hover:text-gray-800'
              "
              @click="selectedService = 'all'"
            >
              所有服务
            </button>
            <button
              v-for="svc in traceData.services"
              :key="svc"
              type="button"
              class="px-2 py-1 rounded text-[11px] border transition"
              :class="
                selectedService === svc
                  ? 'bg-sky-100 text-sky-800 border-sky-300 font-semibold dark:bg-sky-950 dark:text-sky-300 dark:border-sky-800'
                  : 'bg-white dark:bg-dark-900 text-gray-500 border-gray-200 dark:border-dark-700 hover:text-gray-800'
              "
              @click="selectedService = svc"
            >
              {{ svc }}
            </button>
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <BaseButton
            variant="ghost"
            size="sm"
            class="text-xs text-gray-500 dark:text-dark-400 hover:text-gray-900 dark:hover:text-white"
            @click="toggleAllLogs"
          >
            {{
              expandedLogNanos.size >= filteredLogs.length
                ? "全部折叠"
                : "全部展开"
            }}
          </BaseButton>
          <BaseButton
            variant="ghost"
            size="sm"
            class="text-xs text-gray-500 dark:text-dark-400 hover:text-gray-900 dark:hover:text-white"
            @click="copyAllLogs"
          >
            <BaseIcon name="copy" class="w-3.5 h-3.5 mr-1" />
            {{ copiedAll ? "已复制!" : "复制全量包" }}
          </BaseButton>
        </div>
      </div>

      <!-- 日志主体时间轴与瀑布流卡片列表 -->
      <div
        class="flex-1 w-full bg-white dark:bg-dark-900/70 border border-gray-200/90 dark:border-dark-800 rounded-2xl p-5 shadow-xs overflow-y-auto"
      >
        <!-- 检索中骨架屏 -->
        <div v-if="loading" class="space-y-4 py-12">
          <div
            class="flex items-center justify-center gap-3 text-sky-600 dark:text-sky-400"
          >
            <BaseIcon name="refresh" class="w-6 h-6 animate-spin" />
            <span class="text-sm font-medium"
              >正在毫秒级检索 Loki 微服务日志流...</span
            >
          </div>
          <div class="max-w-2xl mx-auto space-y-3 pt-4">
            <div
              class="h-12 bg-gray-100 dark:bg-dark-800/60 rounded-xl animate-pulse"
            />
            <div
              class="h-12 bg-gray-100/70 dark:bg-dark-800/40 rounded-xl animate-pulse"
            />
            <div
              class="h-12 bg-gray-100/40 dark:bg-dark-800/20 rounded-xl animate-pulse"
            />
          </div>
        </div>

        <!-- 无日志状态 -->
        <div
          v-else-if="
            activeTraceId && (!traceData?.logs || traceData.logs.length === 0)
          "
          class="flex flex-col items-center justify-center py-16 text-gray-500 dark:text-dark-400 space-y-3"
        >
          <BaseIcon
            name="search"
            class="w-12 h-12 text-gray-300 dark:text-dark-600 mb-1"
          />
          <p class="text-sm font-semibold text-gray-800 dark:text-dark-200">
            未检索到关联日志记录
          </p>
          <p
            class="text-xs text-gray-500 dark:text-dark-400 max-w-md text-center leading-relaxed"
          >
            可能原因：1) 该请求未经过微服务打标；2) 本地日志尚未推入 Loki
            (通常有 1~2s 延迟)；3) 该日志已超过 7 天保留期被自动淘汰。
          </p>
          <BaseButton variant="secondary" size="sm" @click="handleSearchTrace">
            <BaseIcon name="refresh" class="w-4 h-4 mr-1" />
            重试检索
          </BaseButton>
        </div>

        <!-- 筛选结果为空提示 -->
        <div
          v-else-if="activeTraceId && filteredLogs.length === 0"
          class="flex flex-col items-center justify-center py-16 text-gray-400 dark:text-dark-500 space-y-2"
        >
          <BaseIcon
            name="filter"
            class="w-10 h-10 text-gray-300 dark:text-dark-600 mb-1"
          />
          <p class="text-sm font-medium text-gray-700 dark:text-dark-200">
            未找到符合当前过滤条件的日志
          </p>
          <p class="text-xs text-gray-500">
            尝试清空关键词或切换日志级别/服务筛选
          </p>
          <BaseButton
            variant="ghost"
            size="sm"
            @click="
              keywordQuery = '';
              selectedLevel = 'all';
              selectedService = 'all';
            "
          >
            重置所有筛选
          </BaseButton>
        </div>

        <!-- 空白未搜索引导 -->
        <div
          v-else-if="!activeTraceId"
          class="flex flex-col items-center justify-center py-24 text-gray-400 dark:text-dark-500 space-y-2"
        >
          <BaseIcon
            name="search"
            class="w-14 h-14 text-gray-300 dark:text-dark-600 mb-2 stroke-1"
          />
          <p class="text-base font-semibold text-gray-800 dark:text-dark-200">
            准备就绪，请输入 Trace ID 开始诊断
          </p>
          <p class="text-xs text-gray-500 dark:text-dark-400">
            系统将自动聚合 platform-api 与 runtime-service
            的上下文日志并毫秒级呈现
          </p>
        </div>

        <!-- 原生时间轴列表 -->
        <div v-else class="space-y-4">
          <div
            class="relative pl-6 space-y-3.5 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200 dark:before:bg-dark-700"
          >
            <div
              v-for="(log, idx) in filteredLogs"
              :key="log.nanos || idx"
              class="relative group"
            >
              <!-- 时间轴圆点 -->
              <div
                class="absolute -left-6 top-3.5 w-3 h-3 rounded-full border-2 transition-transform group-hover:scale-125 shadow-xs"
                :class="[
                  log.level === 'error'
                    ? 'bg-red-500 border-white dark:border-dark-900'
                    : log.level === 'warn'
                      ? 'bg-amber-500 border-white dark:border-dark-900'
                      : log.service === 'platform-api'
                        ? 'bg-sky-500 border-white dark:border-dark-900'
                        : 'bg-purple-500 border-white dark:border-dark-900',
                ]"
              />

              <!-- 日志卡片主体 -->
              <div
                class="p-3.5 rounded-xl border transition-all duration-150 shadow-2xs hover:shadow-xs"
                :class="[
                  log.level === 'error'
                    ? 'bg-red-50/50 dark:bg-red-950/20 border-red-200/90 dark:border-red-900/60 hover:border-red-300 dark:hover:border-red-700/80'
                    : log.level === 'warn'
                      ? 'bg-amber-50/50 dark:bg-amber-950/20 border-amber-200/90 dark:border-amber-900/60 hover:border-amber-300'
                      : 'bg-white dark:bg-dark-900/90 border-gray-200/90 dark:border-dark-700/80 hover:border-sky-300 dark:hover:border-sky-500/50',
                ]"
              >
                <!-- 卡片首行：标签、耗时瀑布条与展开切换 -->
                <div
                  class="flex items-center justify-between gap-3 cursor-pointer select-none"
                  @click="toggleLogDetail(log.nanos)"
                >
                  <div class="flex items-center gap-2 flex-wrap">
                    <!-- 微服务标签 -->
                    <span
                      class="px-2 py-0.5 rounded text-[11px] font-mono font-bold tracking-tight uppercase"
                      :class="
                        log.service === 'platform-api'
                          ? 'bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-950/80 dark:text-sky-300 dark:border-sky-800'
                          : 'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950/80 dark:text-purple-300 dark:border-purple-800'
                      "
                    >
                      {{ log.service }}
                    </span>

                    <!-- 日志级别 -->
                    <span
                      class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase"
                      :class="[
                        log.level === 'error'
                          ? 'bg-red-100 text-red-700 border border-red-200 dark:bg-red-900/60 dark:text-red-200 dark:border-red-800'
                          : log.level === 'warn'
                            ? 'bg-amber-100 text-amber-700 border border-amber-200 dark:bg-amber-900/60 dark:text-amber-200 dark:border-amber-800'
                            : 'bg-gray-100 text-gray-600 border border-gray-200 dark:bg-dark-800 dark:text-dark-300 dark:border-dark-700',
                      ]"
                    >
                      {{ log.level }}
                    </span>

                    <!-- Span ID 徽章 -->
                    <span
                      v-if="log.span_id"
                      class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-gray-100 text-gray-500 border border-gray-200 dark:bg-dark-800 dark:text-dark-400 dark:border-dark-700"
                      title="Span ID"
                    >
                      span:{{ log.span_id.slice(0, 8) }}
                    </span>

                    <!-- 耗时徽章（如果有） -->
                    <span
                      v-if="log.duration_ms"
                      class="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-tight"
                      :class="
                        log.duration_ms > 500
                          ? 'bg-red-100 text-red-700 border border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800'
                          : log.duration_ms > 100
                            ? 'bg-amber-100 text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800'
                      "
                    >
                      ⏱️ {{ log.duration_ms }}ms
                      <span
                        v-if="log.duration_ms > 500"
                        class="ml-1 text-[9px] uppercase font-bold text-red-600"
                        >慢</span
                      >
                    </span>

                    <!-- 时间戳 -->
                    <span
                      class="text-xs font-mono text-gray-400 dark:text-dark-400"
                    >
                      {{
                        log.timestamp
                          ? log.timestamp.split("T")[1]?.replace("Z", "")
                          : ""
                      }}
                    </span>
                  </div>

                  <div class="flex items-center gap-2">
                    <span
                      class="text-xs text-gray-400 dark:text-dark-400 group-hover:text-gray-700 dark:group-hover:text-dark-200 transition-colors"
                    >
                      {{
                        expandedLogNanos.has(log.nanos) ? "收起" : "展开详情"
                      }}
                    </span>
                    <BaseIcon
                      :name="
                        expandedLogNanos.has(log.nanos)
                          ? 'chevron-down'
                          : 'chevron-right'
                      "
                      class="w-3.5 h-3.5 text-gray-400 dark:text-dark-400 transition-transform"
                    />
                  </div>
                </div>

                <!-- 可视化耗时甘特条 (Waterfall Gantt Bar) -->
                <div
                  v-if="log.duration_ms"
                  class="mt-2.5 w-full bg-gray-100 dark:bg-dark-800 h-1.5 rounded-full overflow-hidden"
                  title="相对耗时比例"
                >
                  <div
                    class="h-full rounded-full transition-all duration-300"
                    :class="
                      log.duration_ms > 500
                        ? 'bg-red-500'
                        : log.duration_ms > 100
                          ? 'bg-amber-500'
                          : 'bg-sky-500'
                    "
                    :style="{
                      width: `${Math.min(Math.max((log.duration_ms / maxLogDurationMs) * 100, 3), 100)}%`,
                    }"
                  />
                </div>

                <!-- 卡片次行：人类可读摘要 -->
                <div
                  class="mt-2 text-xs font-mono text-gray-800 dark:text-dark-100 cursor-pointer break-all"
                  @click="toggleLogDetail(log.nanos)"
                >
                  {{ log.summary }}
                </div>

                <!-- 展开的详细 JSON / 原始日志 -->
                <div
                  v-if="expandedLogNanos.has(log.nanos)"
                  class="mt-3 pt-3 border-t border-gray-100 dark:border-dark-800 text-xs font-mono space-y-2.5"
                >
                  <div
                    v-if="log.payload && Object.keys(log.payload).length > 0"
                  >
                    <div
                      class="text-[11px] font-semibold text-gray-500 dark:text-dark-400 mb-1"
                    >
                      结构化元数据 (JSON):
                    </div>
                    <pre
                      class="p-3 bg-gray-50 dark:bg-dark-950 rounded-lg border border-gray-200/80 dark:border-dark-800 overflow-x-auto text-sky-800 dark:text-sky-300 leading-relaxed text-[11px]"
                      >{{ JSON.stringify(log.payload, null, 2) }}</pre
                    >
                  </div>
                  <div>
                    <div
                      class="text-[11px] font-semibold text-gray-500 dark:text-dark-400 mb-1"
                    >
                      原始日志行 (Raw Log):
                    </div>
                    <pre
                      class="p-3 bg-gray-50 dark:bg-dark-950 rounded-lg border border-gray-200/80 dark:border-dark-800 overflow-x-auto text-gray-700 dark:text-dark-300 leading-relaxed whitespace-pre-wrap break-all text-[11px]"
                      >{{ log.raw }}</pre
                    >
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 视角 2: Grafana Explore (嵌入式深度透视) -->
    <div
      v-else-if="currentTab === 'grafana'"
      class="flex-1 flex flex-col space-y-3"
    >
      <div
        class="flex items-center justify-between px-3 py-2 bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 rounded-xl text-xs shadow-2xs"
      >
        <div class="text-gray-500 dark:text-dark-400 flex items-center gap-2">
          <BaseIcon name="info" class="w-4 h-4 text-sky-500" />
          <span
            >Grafana Explore 视角：支持直接在此手写 LogQL
            语句进行深度数据挖掘与时序聚合。</span
          >
        </div>
        <div class="flex items-center gap-2">
          <BaseButton
            variant="ghost"
            size="sm"
            :disabled="iframeLoading"
            @click="resetIframe"
          >
            <BaseIcon name="refresh" class="w-4 h-4 mr-1" />
            重载
          </BaseButton>
          <BaseButton variant="ghost" size="sm" @click="toggleFullscreen">
            <BaseIcon
              :name="isFullscreen ? 'minimize' : 'maximize'"
              class="w-4 h-4 mr-1"
            />
            {{ isFullscreen ? "退出全屏" : "全屏" }}
          </BaseButton>
          <BaseButton variant="ghost" size="sm" @click="openGrafanaExplore">
            <BaseIcon name="globe" class="w-4 h-4 mr-1" />
            独立窗口 ↗
          </BaseButton>
        </div>
      </div>

      <div
        ref="iframeContainer"
        class="relative flex-1 w-full bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-inner flex flex-col min-h-[550px]"
      >
        <div
          v-if="iframeLoading"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm text-slate-300"
        >
          <BaseIcon
            name="search"
            class="w-8 h-8 text-sky-400 animate-pulse mb-3"
          />
          <p class="text-sm font-medium">
            正在拉取 Grafana Loki Explore 聚合视图...
          </p>
          <p class="text-xs text-slate-500 mt-1">
            包含 LogQL 编辑器与直方图分析
          </p>
        </div>

        <iframe
          :key="iframeKey"
          :src="exploreEmbedUrl"
          class="w-full h-full border-0 flex-1 min-h-[550px]"
          allow="fullscreen"
          @load="handleIframeLoaded"
        />
      </div>
    </div>
  </section>
</template>
