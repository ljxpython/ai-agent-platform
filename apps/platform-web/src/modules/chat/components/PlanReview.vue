<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import type { PendingPlanReview } from "../plan-review";
import { renderMarkdown } from "@/utils/markdown";

const props = withDefaults(
  defineProps<{
    review?: PendingPlanReview | null;
    disabled?: boolean;
    readOnly?: boolean;
  }>(),
  {
    review: null,
    disabled: false,
    readOnly: false,
  },
);

const emit = defineEmits<{
  approve: [];
  "request-changes": [feedback: string];
  abandon: [];
}>();

const isRequestingChanges = ref(false);
const feedback = ref("");
const copied = ref(false);
let copyTimeout: ReturnType<typeof setTimeout> | null = null;

watch(
  () => props.review?.id,
  () => {
    isRequestingChanges.value = false;
    feedback.value = "";
  },
);

const renderedMarkdown = computed(() => {
  if (!props.review?.markdown)
    return '<p class="text-gray-400 dark:text-dark-400 italic">计划正文为空</p>';
  return renderMarkdown(props.review.markdown);
});

const feedbackLength = computed(() => feedback.value.length);
const isFeedbackValid = computed(
  () => feedback.value.trim().length >= 1 && feedbackLength.value <= 2000,
);

const allowedDecisions = computed(() => props.review?.allowedDecisions ?? []);
const canApprove = computed(() => allowedDecisions.value.includes("approve"));
const canRequestChanges = computed(() =>
  allowedDecisions.value.includes("request_changes"),
);
const canAbandon = computed(() => allowedDecisions.value.includes("abandon"));
const hasSupportedDecisions = computed(
  () => canApprove.value || canRequestChanges.value || canAbandon.value,
);

const shortHash = computed(() => {
  const hash = props.review?.contentHash || "";
  if (!hash) return "";
  return hash.length > 16 ? `${hash.slice(0, 16)}…` : hash;
});

async function handleCopy() {
  if (!props.review?.markdown) return;
  try {
    await navigator.clipboard.writeText(props.review.markdown);
    copied.value = true;
    if (copyTimeout) clearTimeout(copyTimeout);
    copyTimeout = setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // 忽略剪贴板访问异常
  }
}

function handleStartRequestChanges() {
  isRequestingChanges.value = true;
}

function handleCancelRequestChanges() {
  isRequestingChanges.value = false;
  feedback.value = "";
}

function handleSubmitChanges() {
  if (!isFeedbackValid.value || props.disabled) return;
  emit("request-changes", feedback.value.trim());
}

function handleApprove() {
  if (props.disabled) return;
  emit("approve");
}

function handleAbandon() {
  if (props.disabled) return;
  emit("abandon");
}
</script>

<template>
  <div
    v-if="review"
    role="region"
    aria-label="执行计划审批"
    data-testid="plan-review-card"
    class="relative mx-auto my-3 w-full max-w-3xl overflow-hidden rounded-2xl border border-indigo-200/80 bg-gradient-to-b from-indigo-50/40 to-white shadow-sm transition-all dark:border-indigo-900/50 dark:from-indigo-950/20 dark:to-dark-900"
  >
    <!-- 顶部状态栏 -->
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 bg-white/70 px-4 py-3 dark:border-indigo-950/60 dark:bg-dark-900/70"
    >
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="inline-flex h-6 items-center gap-1.5 rounded-full bg-indigo-100 px-2.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300"
        >
          <BaseIcon name="sparkle" size="xs" />
          <span>执行计划确认</span>
        </span>
        <span
          class="inline-flex items-center rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-mono text-gray-600 dark:bg-dark-800 dark:text-dark-300"
          title="计划版本号"
        >
          v{{ review.revision }}
        </span>
        <span
          v-if="shortHash"
          class="inline-flex items-center text-[10px] font-mono text-gray-400 dark:text-dark-400"
          :title="review.contentHash"
        >
          {{ shortHash }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          :title="copied ? '已复制' : '复制 Markdown 正文'"
          @click="handleCopy"
        >
          <BaseIcon :name="copied ? 'check' : 'copy'" size="xs" />
          <span>{{ copied ? "已复制" : "复制正文" }}</span>
        </button>
      </div>
    </div>

    <!-- 计划标题与正文 -->
    <div class="p-4 sm:p-5">
      <h3
        v-if="review.title"
        class="mb-3 text-base font-bold text-gray-900 dark:text-white"
        data-testid="plan-review-title"
      >
        {{ review.title }}
      </h3>

      <!-- Markdown 正文 (限制最大高度并允许局部滚动，支持 64 KiB 大文本安全展示) -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div
        class="prose prose-sm max-w-none max-h-96 overflow-y-auto rounded-xl border border-gray-100 bg-white/80 p-3.5 text-xs text-gray-800 shadow-2xs dark:border-dark-800/80 dark:bg-dark-950/60 dark:text-gray-200"
        data-testid="plan-review-content"
        v-html="renderedMarkdown"
      />

      <!-- 不支持的决策告警 -->
      <div
        v-if="!hasSupportedDecisions && !readOnly"
        role="alert"
        class="mt-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300"
      >
        <BaseIcon
          name="alert"
          size="xs"
          class="shrink-0 text-amber-600 dark:text-amber-400"
        />
        <span>当前计划包含不受支持的审批指令，请刷新会话同步最新状态。</span>
      </div>

      <!-- 修改建议输入区 (Request Changes 模式) -->
      <div
        v-if="isRequestingChanges && !readOnly"
        class="mt-4 space-y-2 rounded-xl border border-amber-200/80 bg-amber-50/40 p-3.5 dark:border-amber-900/50 dark:bg-amber-950/20"
        data-testid="plan-review-feedback-container"
      >
        <div
          class="flex items-center justify-between text-xs font-medium text-amber-900 dark:text-amber-200"
        >
          <span>请输入修改建议或补充要求 (1–2000 字符)</span>
          <span
            class="text-[11px] font-mono"
            :class="
              feedbackLength > 2000
                ? 'text-red-600 font-bold'
                : 'text-gray-400 dark:text-dark-400'
            "
          >
            {{ feedbackLength }} / 2000
          </span>
        </div>
        <textarea
          v-model="feedback"
          data-testid="plan-review-feedback-input"
          rows="3"
          placeholder="请具体指出哪些步骤需要调整、补充或重新规划..."
          class="pw-input w-full resize-y text-xs text-gray-900 dark:text-gray-100 placeholder:text-gray-400"
          :disabled="disabled"
        />
        <div class="flex items-center justify-end gap-2 pt-1">
          <BaseButton
            size="sm"
            variant="secondary"
            data-testid="plan-review-cancel-changes-btn"
            :disabled="disabled"
            @click="handleCancelRequestChanges"
          >
            取消
          </BaseButton>
          <BaseButton
            size="sm"
            variant="primary"
            data-testid="plan-review-submit-changes-btn"
            :disabled="disabled || !isFeedbackValid"
            @click="handleSubmitChanges"
          >
            提交修改意见
          </BaseButton>
        </div>
      </div>

      <!-- 操作按钮栏 -->
      <div
        v-if="!readOnly && !isRequestingChanges && hasSupportedDecisions"
        class="mt-4 flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-dark-800"
      >
        <div class="flex items-center gap-2">
          <BaseButton
            v-if="canAbandon"
            size="sm"
            variant="danger"
            data-testid="plan-review-abandon-btn"
            :disabled="disabled"
            @click="handleAbandon"
          >
            放弃计划
          </BaseButton>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <BaseButton
            v-if="canRequestChanges"
            size="sm"
            variant="secondary"
            data-testid="plan-review-request-changes-btn"
            :disabled="disabled"
            @click="handleStartRequestChanges"
          >
            请求修改
          </BaseButton>

          <BaseButton
            v-if="canApprove"
            size="sm"
            variant="primary"
            data-testid="plan-review-approve-btn"
            :disabled="disabled"
            @click="handleApprove"
          >
            批准并开始执行
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>
