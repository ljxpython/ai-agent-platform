<script setup lang="ts">
import { ref } from "vue";
import type { AssistantAttachedContext } from "../types";
import BaseIcon from "@/components/base/BaseIcon.vue";

defineProps<{
  context: AssistantAttachedContext;
}>();

const emit = defineEmits<{
  (e: "remove"): void;
}>();

const isPreviewOpen = ref(false);

function togglePreview() {
  isPreviewOpen.value = !isPreviewOpen.value;
}
</script>

<template>
  <div
    class="flex flex-col bg-amber-50/90 dark:bg-amber-950/40 border border-amber-200/90 dark:border-amber-800/60 rounded-xl p-2.5 text-xs text-amber-900 dark:text-amber-200 shadow-2xs transition-all"
  >
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-200/80 dark:bg-amber-800 text-amber-900 dark:text-amber-100 shrink-0"
        >
          错误现场
        </span>
        <span class="font-medium truncate" :title="context.title">
          {{ context.title }}
        </span>
        <span
          v-if="context.traceId"
          class="hidden sm:inline-block font-mono text-[11px] text-amber-700/80 dark:text-amber-400/80 truncate max-w-[120px]"
          :title="context.traceId"
        >
          trace:{{ context.traceId.slice(0, 8) }}
        </span>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          class="px-2 py-0.5 rounded text-[11px] font-medium text-amber-800 dark:text-amber-300 hover:bg-amber-200/50 dark:hover:bg-amber-900/50 transition"
          @click="togglePreview"
        >
          {{ isPreviewOpen ? "收起详情" : "预览详情" }}
        </button>
        <button
          type="button"
          class="p-1 rounded text-amber-600 hover:text-amber-900 dark:text-amber-400 dark:hover:text-amber-100 hover:bg-amber-200/60 dark:hover:bg-amber-800/60 transition"
          title="移除此上下文"
          @click="emit('remove')"
        >
          <BaseIcon name="x" class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- 展开详情预览 -->
    <div
      v-if="isPreviewOpen"
      class="mt-2 pt-2 border-t border-amber-200/60 dark:border-amber-800/40 text-[11px] font-mono leading-relaxed"
    >
      <div
        v-if="context.summary"
        class="mb-1 text-amber-800 dark:text-amber-300 font-sans"
      >
        {{ context.summary }}
      </div>
      <pre
        class="max-h-48 overflow-y-auto p-2 bg-white/80 dark:bg-dark-900/80 rounded border border-amber-100 dark:border-dark-800 text-gray-700 dark:text-dark-300 whitespace-pre-wrap break-all"
        >{{ context.diagnosticMarkdown }}</pre
      >
    </div>
  </div>
</template>
