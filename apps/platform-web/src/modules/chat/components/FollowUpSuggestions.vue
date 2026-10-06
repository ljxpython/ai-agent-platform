<script setup lang="ts">
import { ref } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import FollowUpConfirmDialog from "./FollowUpConfirmDialog.vue";

const props = withDefaults(
  defineProps<{
    suggestions: readonly string[];
    loading?: boolean;
    draft?: string;
    disabled?: boolean;
  }>(),
  {
    loading: false,
    draft: "",
    disabled: false,
  },
);

const emit = defineEmits<{
  select: [prompt: string, mode: "direct" | "append" | "replace"];
  dismiss: [];
}>();

const showConfirm = ref(false);
const pendingSuggestion = ref("");

function handleItemClick(suggestion: string) {
  if (props.disabled) return;
  const currentDraft = (props.draft || "").trim();
  if (currentDraft) {
    pendingSuggestion.value = suggestion;
    showConfirm.value = true;
    return;
  }
  emit("select", suggestion, "direct");
}

function handleConfirm(mode: "append" | "replace") {
  const prompt = pendingSuggestion.value;
  showConfirm.value = false;
  pendingSuggestion.value = "";
  if (prompt) {
    emit("select", prompt, mode);
  }
}
</script>

<template>
  <div
    v-if="loading || suggestions.length > 0"
    role="region"
    aria-label="推荐追问"
    class="pw-followup-suggestions mt-3 flex max-w-[780px] flex-wrap items-center gap-1.5 transition-all duration-200"
    data-testid="followup-suggestions"
  >
    <!-- 加载骨架屏：微型紧凑胶囊，防止视口突跳 (Zero-CLS) -->
    <template v-if="loading">
      <div
        class="inline-flex h-7 items-center gap-1.5 rounded-full border border-gray-200/60 bg-gray-50/70 px-3 py-1 text-xs text-gray-400 backdrop-blur-xs dark:border-dark-800/80 dark:bg-dark-900/60 dark:text-dark-400"
        data-testid="followup-loading"
      >
        <span
          class="inline-block h-2 w-2 animate-ping rounded-full bg-primary-500/70"
        />
        <span class="text-[11px]">正在探索相关追问...</span>
      </div>
    </template>

    <!-- 建议胶囊列表 -->
    <template v-else>
      <button
        v-for="(suggestion, index) in suggestions"
        :key="`suggestion-${index}`"
        type="button"
        class="group/chip inline-flex h-auto max-w-full cursor-pointer items-center gap-1.5 rounded-full border border-gray-200/80 bg-white/90 px-3 py-1.5 text-left text-xs font-normal text-gray-700 shadow-2xs transition-all hover:border-primary-400 hover:bg-primary-50/40 hover:text-primary-700 hover:shadow-xs active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 dark:border-dark-700/80 dark:bg-dark-800/80 dark:text-dark-200 dark:hover:border-primary-500/70 dark:hover:bg-primary-950/40 dark:hover:text-primary-300"
        :disabled="disabled"
        @click="handleItemClick(suggestion)"
      >
        <BaseIcon
          name="sparkle"
          size="xs"
          class="shrink-0 text-primary-500 transition-transform group-hover/chip:rotate-12 dark:text-primary-400"
        />
        <span class="break-words line-clamp-2 leading-relaxed">
          {{ suggestion }}
        </span>
      </button>

      <!-- 主动关闭按钮 (Dismiss) -->
      <button
        type="button"
        class="inline-flex h-7 w-7 items-center justify-center rounded-full border border-gray-200/80 bg-white/80 text-gray-400 shadow-2xs transition-colors hover:border-gray-300 hover:bg-gray-100 hover:text-gray-600 dark:border-dark-700 dark:bg-dark-800/80 dark:text-dark-400 dark:hover:bg-dark-700 dark:hover:text-dark-200"
        title="关闭推荐问题"
        aria-label="关闭推荐问题"
        @click="emit('dismiss')"
      >
        <BaseIcon name="x" size="xs" />
      </button>
    </template>

    <!-- 草稿冲突确认弹窗 -->
    <FollowUpConfirmDialog
      :show="showConfirm"
      :suggestion="pendingSuggestion"
      :draft="draft || ''"
      @close="showConfirm = false"
      @confirm="handleConfirm"
    />
  </div>
</template>
