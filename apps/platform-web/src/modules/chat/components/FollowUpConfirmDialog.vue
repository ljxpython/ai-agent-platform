<script setup lang="ts">
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";

defineProps<{
  show: boolean;
  suggestion: string;
  draft: string;
}>();

const emit = defineEmits<{
  close: [];
  confirm: [mode: "append" | "replace"];
}>();
</script>

<template>
  <BaseDialog
    :show="show"
    title="检测到未发送的草稿"
    width="narrow"
    @close="emit('close')"
  >
    <div class="space-y-3 py-1 text-xs text-gray-600 dark:text-dark-300">
      <p>
        输入框内已有未发送的文字，直接点击推荐问题将对其产生影响，请选择处理方式：
      </p>
      <div
        class="rounded-lg border border-gray-100 bg-gray-50/80 p-2.5 dark:border-dark-800 dark:bg-dark-900/60"
      >
        <div class="text-[11px] font-medium text-gray-400 dark:text-dark-400">
          当前草稿：
        </div>
        <div
          class="mt-0.5 line-clamp-2 font-mono text-[11px] text-gray-700 dark:text-dark-200"
        >
          {{ draft }}
        </div>
        <div
          class="mt-2 text-[11px] font-medium text-primary-600 dark:text-primary-400"
        >
          推荐追问：
        </div>
        <div
          class="mt-0.5 line-clamp-2 text-[11px] font-semibold text-gray-900 dark:text-white"
        >
          {{ suggestion }}
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <BaseButton variant="secondary" size="sm" @click="emit('close')">
          取消
        </BaseButton>
        <BaseButton
          variant="secondary"
          size="sm"
          @click="emit('confirm', 'append')"
        >
          追加并发送
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          @click="emit('confirm', 'replace')"
        >
          替换并发送
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>
