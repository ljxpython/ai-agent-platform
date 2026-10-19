<script setup lang="ts">
import { ref, defineComponent, h, onMounted } from "vue";
import ErrorBoundary from "../src/components/feedback/ErrorBoundary.vue";
import ChatAgentStatusBar from "../src/modules/chat/components/ChatAgentStatusBar.vue";
import DiagnosticDetailModal from "../src/modules/chat/components/DiagnosticDetailModal.vue";
import { errorRingBuffer } from "../src/services/observability/error-buffer";

const mode = ref("crash");
const shouldCrash = ref(true);
const showDiagnosticModal = ref(false);
const trajectoryOpened = ref(false);

const CrashingComponent = defineComponent({
  name: "CrashingComponent",
  setup() {
    if (shouldCrash.value) {
      throw new Error(
        "E2E Fatal Crash: Simulated Render Exception (crypto.randomUUID is not a function)",
      );
    }
    return () =>
      h("div", { class: "p-4 text-emerald-600" }, "组件恢复正常运行");
  },
});

onMounted(() => {
  const params = new URLSearchParams(window.location.search);
  const m = params.get("mode");
  if (m) mode.value = m;

  // 预置 HTTP / Trace 失败记录到内存缓冲区
  errorRingBuffer.push({
    type: "http",
    status: 502,
    code: "runtime_execution_failed",
    requestId: "req-e2e-trace-9999-failed",
    url: "/api/runs/stream",
    message: "Remote docker sandbox container timed out after 10s",
  });
});

function switchMode(newMode: string) {
  mode.value = newMode;
  trajectoryOpened.value = false;
  showDiagnosticModal.value = false;
}
</script>

<template>
  <div
    class="min-h-screen p-8 bg-gray-50 dark:bg-dark-950 font-sans text-gray-900 dark:text-gray-100"
  >
    <!-- 顶部测试模式切换栏 -->
    <header
      class="mb-8 flex items-center justify-between border-b border-gray-200 pb-4 dark:border-dark-800"
    >
      <div>
        <h1 class="text-xl font-bold">前端可观测性与排障 E2E 验证工装</h1>
        <p class="text-xs text-gray-500">
          用于真实浏览器环境下的异常捕获、CrashScreen 防御与 Request ID
          诊断链路检验
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="px-3 py-1.5 text-xs rounded-lg border"
          :class="
            mode === 'crash'
              ? 'bg-primary-600 text-white border-primary-600'
              : 'bg-white border-gray-300 dark:bg-dark-800'
          "
          data-testid="btn-switch-crash"
          @click="switchMode('crash')"
        >
          模式 1: CrashScreen 崩溃防御
        </button>
        <button
          type="button"
          class="px-3 py-1.5 text-xs rounded-lg border"
          :class="
            mode === 'status'
              ? 'bg-primary-600 text-white border-primary-600'
              : 'bg-white border-gray-300 dark:bg-dark-800'
          "
          data-testid="btn-switch-status"
          @click="switchMode('status')"
        >
          模式 2: Chat 状态栏排障按钮
        </button>
      </div>
    </header>

    <!-- 模式 1: ErrorBoundary 崩溃卡片展示 -->
    <section v-if="mode === 'crash'" class="max-w-2xl mx-auto mt-12">
      <ErrorBoundary fallback-title="视图遇到未处理异常">
        <CrashingComponent />
      </ErrorBoundary>
    </section>

    <!-- 模式 2: 状态栏展示与排障模态窗交互 -->
    <section
      v-else-if="mode === 'status'"
      class="max-w-2xl mx-auto mt-12 space-y-6"
    >
      <div
        class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-dark-800 dark:bg-dark-900"
      >
        <h2 class="text-sm font-semibold mb-3 text-gray-700 dark:text-gray-300">
          智能体执行状态条 (模拟报错态)
        </h2>
        <ChatAgentStatusBar
          :is-running="false"
          :is-interrupted="false"
          error="runtime.execution_failed"
          @inspect-diagnostic="showDiagnosticModal = true"
        />
      </div>

      <!-- 模拟轨迹诊断视图联动成功面板 -->
      <div
        v-if="trajectoryOpened"
        class="p-5 rounded-xl border border-indigo-200 bg-indigo-50/70 dark:border-indigo-900/60 dark:bg-indigo-950/30 animate-in fade-in"
        data-testid="trajectory-diagnostic-view-target"
      >
        <div
          class="flex items-center gap-2.5 text-indigo-900 dark:text-indigo-200 font-semibold text-sm mb-1.5"
        >
          <svg
            class="size-4.5 text-indigo-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          已成功联动切换至轨迹视角 (Trajectory View - Diagnostics Inspector)
        </div>
        <p class="text-xs text-indigo-700 dark:text-indigo-300">
          视图模式:
          <code
            class="font-mono bg-indigo-100 dark:bg-indigo-900 px-1 py-0.5 rounded"
            >activeView = 'trajectory'</code
          >
          | 检查器标签:
          <code
            class="font-mono bg-indigo-100 dark:bg-indigo-900 px-1 py-0.5 rounded"
            >inspectorMode = 'diagnostics'</code
          >
        </p>
      </div>

      <!-- 就地排障详情模态窗 -->
      <DiagnosticDetailModal
        v-model:show="showDiagnosticModal"
        project-id="proj-e2e-demo"
        thread-id="thread-e2e-demo"
        run-id="run-e2e-8888"
        request-id="req-e2e-trace-9999-failed"
        error-code="provider_timeout"
        error="Model call timed out after 60s"
        :can-view-trajectory="true"
        @open-trajectory="trajectoryOpened = true"
      />
    </section>
  </div>
</template>
