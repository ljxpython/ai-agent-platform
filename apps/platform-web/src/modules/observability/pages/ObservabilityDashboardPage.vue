<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import { useThemeStore } from "@/stores/theme";

const themeStore = useThemeStore();

// 优先使用环境变量配置的大盘 URL，未配置则回退到生产默认地址
const rawDashboardUrl =
  (import.meta.env.VITE_GRAFANA_DASHBOARD_URL as string | undefined)?.trim() ||
  "http://49.233.222.54:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1";

const iframeLoading = ref(true);
const iframeKey = ref(0);
const isFullscreen = ref(false);
const iframeContainer = ref<HTMLElement | null>(null);

// 拼接带 kiosk 沉浸模式以及联动主题参数的最终嵌入 URL
const dashboardEmbedUrl = computed(() => {
  try {
    const url = new URL(rawDashboardUrl);
    // kiosk: 隐藏 Grafana 自身菜单栏与顶栏，保持 Platform 平台一体化视觉
    url.searchParams.set("kiosk", "");
    // 同步当前系统深色 / 浅色模式
    url.searchParams.set(
      "theme",
      themeStore.mode === "dark" ? "dark" : "light",
    );
    return url.toString();
  } catch {
    // 兜底防御非法 URL
    return rawDashboardUrl;
  }
});

function reloadDashboard() {
  iframeLoading.value = true;
  iframeKey.value += 1;
}

function openInNewTab() {
  window.open(rawDashboardUrl, "_blank", "noopener,noreferrer");
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
  isFullscreen.value = Boolean(document.fullscreenElement);
}

onMounted(() => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onUnmounted(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
});

function handleIframeLoaded() {
  iframeLoading.value = false;
}
</script>

<template>
  <section class="pw-page-shell flex flex-col h-[calc(100vh-4rem)] space-y-4">
    <PageHeader
      eyebrow="Governance"
      title="指标大盘"
      description="基于 Prometheus + Grafana 的工业级全栈可观测性中枢。实时监测 Platform API 与 Runtime 引擎的核心吞吐 QPS、延迟分位（P95/P99）、状态码分布与沙箱水位。"
    >
      <template #actions>
        <BaseButton variant="secondary" @click="reloadDashboard">
          <BaseIcon name="refresh" size="sm" />
          刷新图表
        </BaseButton>

        <BaseButton variant="secondary" @click="toggleFullscreen">
          <BaseIcon :name="isFullscreen ? 'minimize' : 'maximize'" size="sm" />
          {{ isFullscreen ? "退出全屏" : "全屏看板" }}
        </BaseButton>

        <BaseButton variant="secondary" @click="openInNewTab">
          <BaseIcon name="globe" size="sm" />
          独立窗口打开
        </BaseButton>
      </template>
    </PageHeader>

    <div
      ref="iframeContainer"
      class="relative flex-1 w-full rounded-2xl border border-gray-200 dark:border-dark-800 bg-white dark:bg-dark-900 overflow-hidden shadow-xs flex flex-col min-h-[560px]"
    >
      <!-- 加载遮罩 -->
      <div
        v-if="iframeLoading"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/80 dark:bg-dark-900/80 backdrop-blur-xs transition-opacity duration-300"
      >
        <div class="flex items-center gap-3 text-primary-500">
          <BaseIcon name="activity" size="lg" class="animate-pulse" />
          <span class="text-sm font-medium text-gray-700 dark:text-dark-200">
            正在加载 Grafana 工业级指标大盘...
          </span>
        </div>
      </div>

      <!-- Grafana 嵌入 iframe -->
      <iframe
        :key="iframeKey"
        :src="dashboardEmbedUrl"
        class="w-full flex-1 border-0"
        allow="fullscreen"
        loading="lazy"
        @load="handleIframeLoaded"
      />
    </div>
  </section>
</template>
