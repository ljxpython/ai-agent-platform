<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import { useThemeStore } from "@/stores/theme";

const themeStore = useThemeStore();
const router = useRouter();

// 优先使用环境变量配置的大盘 URL，未配置则回退到生产默认地址
const rawDashboardUrl =
  (import.meta.env.VITE_GRAFANA_DASHBOARD_URL as string | undefined)?.trim() ||
  "http://49.233.222.54:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1";

const iframeLoading = ref(true);
const iframeKey = ref(0);
const isFullscreen = ref(false);
const iframeContainer = ref<HTMLElement | null>(null);
let loadingTimeoutTimer: ReturnType<typeof setTimeout> | null = null;

function resetLoadingWithTimeout() {
  iframeLoading.value = true;
  iframeKey.value += 1;
  if (loadingTimeoutTimer) {
    clearTimeout(loadingTimeoutTimer);
  }
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

// 默认视角：全栈基础设施大盘，跟随主题模式联动
const dashboardEmbedUrl = computed(() => {
  const theme = themeStore.mode === "dark" ? "dark" : "light";
  try {
    const url = new URL(rawDashboardUrl);
    url.searchParams.set("kiosk", "");
    url.searchParams.set("theme", theme);
    return url.toString();
  } catch {
    return rawDashboardUrl;
  }
});

function reloadDashboard() {
  resetLoadingWithTimeout();
}

function openInNewTab() {
  window.open(dashboardEmbedUrl.value, "_blank", "noopener,noreferrer");
}

function goToTraceDiagnostics() {
  void router.push({ name: "workspace-trace-diagnostics" });
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
      title="指标大盘"
      description="基于 Prometheus + Grafana 的全栈性能与资源监控。实时洞察微服务 QPS、P99 延时、容器内存与活跃会话。"
    >
      <template #actions>
        <div class="flex items-center gap-2">
          <BaseButton
            variant="secondary"
            size="sm"
            @click="goToTraceDiagnostics"
          >
            <BaseIcon name="search" class="w-4 h-4 mr-1 text-sky-500" />
            链路诊断中心
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

    <!-- Grafana 指标大盘内嵌容器 -->
    <div
      ref="iframeContainer"
      class="relative flex-1 w-full bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-inner flex flex-col"
    >
      <div
        v-if="iframeLoading"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm text-slate-300"
      >
        <BaseIcon
          name="activity"
          class="w-8 h-8 text-sky-400 animate-pulse mb-3"
        />
        <p class="text-sm font-medium">正在建立可观测性指标流连接...</p>
        <p class="text-xs text-slate-500 mt-1">
          加载 Prometheus & Grafana 监控大盘
        </p>
      </div>

      <iframe
        :key="iframeKey"
        :src="dashboardEmbedUrl"
        class="w-full h-full border-0 flex-1"
        allow="fullscreen"
        @load="handleIframeLoaded"
      />
    </div>
  </section>
</template>
