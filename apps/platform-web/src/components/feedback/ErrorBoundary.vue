<script setup lang="ts">
import { ref, onErrorCaptured, computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { errorRingBuffer } from "@/services/observability/error-buffer";
import { copyDiagnosticPacket } from "@/services/observability/diagnostic-packet";

const props = withDefaults(
  defineProps<{
    fallbackTitle?: string;
    fallbackDescription?: string;
  }>(),
  {
    fallbackTitle: "视图遇到未处理异常",
    fallbackDescription:
      "很抱歉，当前视图在渲染过程中发生了不可恢复的错误，已阻止整站崩溃白屏。",
  },
);

const hasError = ref(false);
const capturedError = ref<unknown>(null);
const componentInfo = ref<string>("");
const isCopied = ref(false);
const showDetails = ref(false);

onErrorCaptured((err, _instance, info) => {
  hasError.value = true;
  capturedError.value = err;
  componentInfo.value = info;

  errorRingBuffer.push({
    type: "js_runtime",
    message: err instanceof Error ? err.message : String(err),
    stack: err instanceof Error ? err.stack : undefined,
    detail: { componentInfo: info },
  });

  return false; // 阻止错误向外冒泡导致整个 Vue 实例卸载
});

const errorMessage = computed(() => {
  if (!capturedError.value) return "未知错误";
  if (capturedError.value instanceof Error) return capturedError.value.message;
  if (typeof capturedError.value === "object")
    return JSON.stringify(capturedError.value);
  return String(capturedError.value);
});

const errorStack = computed(() => {
  if (capturedError.value instanceof Error && capturedError.value.stack) {
    return capturedError.value.stack;
  }
  return "";
});

function handleReload() {
  if (typeof window !== "undefined") {
    window.location.reload();
  }
}

function handleReset() {
  hasError.value = false;
  capturedError.value = null;
  componentInfo.value = "";
}

async function handleCopy() {
  const result = await copyDiagnosticPacket({
    error: capturedError.value,
    customMessage: `ErrorBoundary 捕获: ${errorMessage.value}`,
  });
  if (result.success) {
    isCopied.value = true;
    setTimeout(() => {
      isCopied.value = false;
    }, 2000);
  }
}
</script>

<template>
  <div
    v-if="hasError"
    class="flex min-h-[360px] w-full items-center justify-center p-6"
    data-testid="error-boundary-crash"
  >
    <div
      class="w-full max-w-xl rounded-2xl border border-rose-200 bg-white p-6 shadow-xl shadow-rose-500/5 dark:border-rose-900/60 dark:bg-dark-900"
    >
      <div class="flex items-start gap-4">
        <div
          class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-rose-200 bg-rose-50 text-rose-600 dark:border-rose-900/80 dark:bg-rose-950/40 dark:text-rose-400"
        >
          <BaseIcon name="alert" class="h-6 w-6" />
        </div>
        <div class="min-w-0 flex-1">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            {{ props.fallbackTitle }}
          </h3>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {{ props.fallbackDescription }}
          </p>

          <div
            class="mt-3.5 rounded-xl border border-rose-100 bg-rose-50/60 p-3 font-mono text-xs text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300 break-all select-all"
          >
            {{ errorMessage }}
          </div>

          <div v-if="errorStack" class="mt-2.5">
            <button
              type="button"
              class="text-xs font-medium text-gray-500 underline hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              @click="showDetails = !showDetails"
            >
              {{ showDetails ? "收起堆栈详情" : "展开堆栈详情" }}
            </button>
            <pre
              v-if="showDetails"
              class="mt-2 max-h-48 overflow-y-auto rounded-lg bg-gray-900 p-2.5 font-mono text-[11px] leading-relaxed text-gray-300 dark:bg-black/80"
              >{{ errorStack }}</pre
            >
          </div>

          <div class="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-xl bg-primary-600 px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              @click="handleReload"
            >
              <BaseIcon name="refresh" class="h-3.5 w-3.5" />
              重新加载页面
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-gray-200 dark:hover:bg-dark-700"
              data-testid="copy-diagnostic-btn"
              @click="handleCopy"
            >
              <BaseIcon
                :name="isCopied ? 'check' : 'copy'"
                class="h-3.5 w-3.5"
                :class="isCopied ? 'text-emerald-500' : ''"
              />
              {{ isCopied ? "✓ 已复制排障信息" : "📋 复制排障信息" }}
            </button>
            <button
              type="button"
              class="text-xs text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
              @click="handleReset"
            >
              尝试恢复
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <slot v-else />
</template>
