<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import { useThemeStore } from "@/stores/theme";

const themeStore = useThemeStore();
const route = useRoute();
const router = useRouter();

// 演示用生产真实 Trace ID（刚才在生产实测打入 Loki 的 trace_id）
const DEMO_TRACE_ID = "54aaf459b9c5415b90370e5874dbb255";

// 优先使用环境变量配置的大盘 URL，未配置则回退到生产默认地址
const rawDashboardUrl =
  (import.meta.env.VITE_GRAFANA_DASHBOARD_URL as string | undefined)?.trim() ||
  "http://49.233.222.54:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1";

const grafanaOrigin = computed(() => {
  try {
    const url = new URL(rawDashboardUrl);
    return url.origin;
  } catch {
    return "http://49.233.222.54:3000";
  }
});

const traceQueryInput = ref(
  (route.query.traceId as string | undefined)?.trim() || "",
);
const activeTraceId = computed(
  () => (route.query.traceId as string | undefined)?.trim() || "",
);

const iframeLoading = ref(true);
const iframeKey = ref(0);
const isFullscreen = ref(false);
const iframeContainer = ref<HTMLElement | null>(null);
const copied = ref(false);
let loadingTimeoutTimer: ReturnType<typeof setTimeout> | null = null;

function resetLoadingWithTimeout() {
  iframeLoading.value = true;
  iframeKey.value += 1;
  if (loadingTimeoutTimer) {
    clearTimeout(loadingTimeoutTimer);
  }
  // 兜底超时保护：至多 2 秒后强制关闭 loading 遮罩，绝不阻塞用户排障交互
  loadingTimeoutTimer = setTimeout(() => {
    iframeLoading.value = false;
  }, 2000);
}

function handleIframeLoaded() {
  if (loadingTimeoutTimer) {
    clearTimeout(loadingTimeoutTimer);
    loadingTimeoutTimer = null;
  }
  iframeLoading.value = false;
}

watch(
  () => route.query.traceId,
  (newId) => {
    traceQueryInput.value = (newId as string | undefined)?.trim() || "";
    resetLoadingWithTimeout();
  },
);

// 生成 Loki Explore 全链路日志视角嵌入 URL
const exploreEmbedUrl = computed(() => {
  const theme = themeStore.mode === "dark" ? "dark" : "light";
  try {
    const logExpr = activeTraceId.value
      ? `{job=~"systemd-journal|app-file-logs"} |= "${activeTraceId.value}"`
      : `{job=~"systemd-journal|app-file-logs"}`;

    const exploreParam = JSON.stringify({
      datasource: "Loki",
      queries: [
        {
          refId: "A",
          expr: logExpr,
        },
      ],
      range: { from: "now-6h", to: "now" },
    });

    const url = new URL(`${grafanaOrigin.value}/explore`);
    url.searchParams.set("orgId", "1");
    url.searchParams.set("left", exploreParam);
    url.searchParams.set("kiosk", "");
    url.searchParams.set("theme", theme);
    return url.toString();
  } catch {
    return `${grafanaOrigin.value}/explore`;
  }
});

function handleSearchTrace() {
  const trimmed = traceQueryInput.value.trim();
  if (trimmed === activeTraceId.value) return;
  iframeLoading.value = true;
  void router.push({
    query: {
      ...route.query,
      traceId: trimmed || undefined,
    },
  });
}

function handleClearTrace() {
  traceQueryInput.value = "";
  iframeLoading.value = true;
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

function reloadDashboard() {
  resetLoadingWithTimeout();
}

function openInNewTab() {
  window.open(exploreEmbedUrl.value, "_blank", "noopener,noreferrer");
}

function goToDashboard() {
  void router.push({ name: "workspace-observability" });
}

async function copyTraceId() {
  if (!activeTraceId.value) return;
  try {
    await navigator.clipboard.writeText(activeTraceId.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // 忽略剪贴板写入失败
  }
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
    // 忽略不支持全屏环境的异常
  }
}

function onFullscreenChange() {
  isFullscreen.value =
    Boolean(document.fullscreenElement) &&
    document.fullscreenElement === iframeContainer.value;
}

onMounted(() => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
  resetLoadingWithTimeout();
});

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  if (loadingTimeoutTimer) {
    clearTimeout(loadingTimeoutTimer);
  }
});
</script>

<template>
  <section class="pw-page-shell flex flex-col h-[calc(100vh-4rem)] space-y-4">
    <PageHeader
      eyebrow="Governance"
      title="链路诊断中心"
      description="基于 W3C TraceContext + Grafana Loki 的分布式排障中枢。输入全局 Trace ID 即可一键穿透跨服务微服务日志与链路瀑布流。"
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
          <BaseButton variant="primary" size="sm" @click="handleSearchTrace">
            <BaseIcon name="search" class="w-4 h-4 mr-1" />
            诊断
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
          <BaseButton
            variant="ghost"
            size="sm"
            :disabled="iframeLoading"
            @click="reloadDashboard"
          >
            <BaseIcon name="refresh" class="w-4 h-4 mr-1" />
            刷新
          </BaseButton>
          <BaseButton variant="ghost" size="sm" @click="toggleFullscreen">
            <BaseIcon
              :name="isFullscreen ? 'minimize' : 'maximize'"
              class="w-4 h-4 mr-1"
            />
            {{ isFullscreen ? "退出全屏" : "全屏" }}
          </BaseButton>
          <BaseButton variant="ghost" size="sm" @click="openInNewTab">
            <BaseIcon name="globe" class="w-4 h-4 mr-1" />
            独立窗口
          </BaseButton>
        </div>
      </template>
    </PageHeader>

    <!-- 诊断状态提示条 -->
    <div
      v-if="activeTraceId"
      class="px-4 py-3 bg-slate-900 border border-sky-500/40 rounded-lg flex items-center justify-between text-xs shadow-xs"
    >
      <div class="flex items-center gap-2 flex-wrap">
        <span
          class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"
        />
        <span class="font-medium text-slate-200">当前诊断 Trace ID:</span>
        <code
          class="px-2 py-0.5 bg-slate-800 text-sky-400 border border-sky-800 rounded font-mono font-semibold cursor-pointer hover:bg-slate-700 hover:border-sky-500 transition"
          title="点击复制 Trace ID"
          @click="copyTraceId"
        >
          {{ activeTraceId }}
        </code>
        <span v-if="copied" class="text-emerald-400 font-bold">✓ 已复制!</span>
        <span class="text-slate-400 hidden sm:inline">
          (已自动聚合 platform-api 与 runtime-service 跨服务详细上下文日志)
        </span>
      </div>
      <div class="flex items-center gap-3">
        <a
          :href="`https://jp.cloud.langfuse.com/trace/${activeTraceId}`"
          target="_blank"
          rel="noopener noreferrer"
          class="text-sky-400 hover:text-sky-300 hover:underline flex items-center gap-1 font-semibold"
        >
          在 Langfuse 查看大模型链路树 ↗
        </a>
      </div>
    </div>

    <!-- 未输入 Trace ID 时的排障获取指引卡片 -->
    <div
      v-if="!activeTraceId"
      class="p-4 bg-slate-900/70 border border-slate-800 rounded-lg text-xs text-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-4"
    >
      <div class="space-y-1">
        <div class="flex items-center gap-2 font-medium text-slate-200">
          <BaseIcon name="info" class="w-4 h-4 text-sky-400" />
          <span>Trace ID 获取途径与排障指引：</span>
        </div>
        <p class="text-slate-400">
          ①
          <b>对话出错时</b
          >：点击错误提示中的【查看详情】，在弹窗中一键复制或点击【微服务全链路日志】直达。<br />
          ② <b>系统审计中心</b>：在【平台管理 -> 审计】中查看每一条 API
          调用及任务执行记录的 Trace ID。<br />
          ③ <b>网络请求头</b>：F12 开发者工具查看任意 API 响应头的
          <code class="text-sky-300">x-trace-id</code> 或
          <code class="text-sky-300">traceparent</code>。
        </p>
      </div>
      <div class="flex items-center gap-2 self-start md:self-auto shrink-0">
        <BaseButton variant="secondary" size="sm" @click="applyDemoTrace">
          <BaseIcon name="sparkle" class="w-4 h-4 mr-1 text-amber-400" />
          演示：载入生产真实 Trace
        </BaseButton>
      </div>
    </div>

    <!-- Loki Explore 日志检索嵌入容器 -->
    <div
      ref="iframeContainer"
      class="relative flex-1 w-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-inner flex flex-col"
    >
      <div
        v-if="iframeLoading"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm text-slate-300"
      >
        <BaseIcon
          name="search"
          class="w-8 h-8 text-sky-400 animate-pulse mb-3"
        />
        <p class="text-sm font-medium">正在检索跨微服务全链路日志...</p>
        <p class="text-xs text-slate-500 mt-1">
          加载 Grafana Loki Explore 聚合日志流
        </p>
      </div>

      <iframe
        :key="iframeKey"
        :src="exploreEmbedUrl"
        class="w-full h-full border-0 flex-1"
        allow="fullscreen"
        @load="handleIframeLoaded"
      />
    </div>
  </section>
</template>
