<script setup lang="ts">
import { ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  disabled?: boolean;
  isRunning?: boolean;
}>();

const emit = defineEmits<{
  (e: "send", text: string): void;
  (e: "stop"): void;
}>();

const inputContent = ref("");

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    handleSend();
  }
}

function handleSend() {
  const trimmed = inputContent.value.trim();
  if (!trimmed && !props.disabled) return;
  emit("send", trimmed);
  inputContent.value = "";
}
</script>

<template>
  <div
    class="flex flex-col gap-2 p-3 bg-white dark:bg-dark-900 border-t border-gray-200 dark:border-dark-800"
  >
    <!-- 上下文挂载插槽 (Context Pill) -->
    <slot name="context" />

    <!-- 输入区与控制按钮 -->
    <div
      class="relative flex flex-col bg-gray-50 dark:bg-dark-950 border border-gray-200 dark:border-dark-700 rounded-xl p-2 focus-within:border-sky-500 focus-within:ring-1 focus-within:ring-sky-500 transition-all"
    >
      <textarea
        v-model="inputContent"
        rows="3"
        class="w-full bg-transparent resize-none border-0 p-1 text-xs text-gray-900 dark:text-white placeholder-gray-400 focus:outline-hidden"
        placeholder="咨询平台用法、排查异常、或探讨创意... (Enter 发送, Shift+Enter 换行)"
        :disabled="isRunning"
        @keydown="handleKeyDown"
      />

      <div class="flex items-center justify-between pt-1">
        <span class="text-[10px] text-gray-400 select-none">
          只读环境 · 生产写入须逐次审批
        </span>

        <div class="flex items-center gap-2">
          <!-- 运行中停止按钮 -->
          <BaseButton
            v-if="isRunning"
            variant="ghost"
            size="sm"
            class="text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 text-xs py-1 px-2.5 h-auto"
            @click="emit('stop')"
          >
            <BaseIcon name="x" class="w-3.5 h-3.5 mr-1" />
            停止
          </BaseButton>

          <!-- 发送按钮 -->
          <BaseButton
            v-else
            variant="primary"
            size="sm"
            :disabled="!inputContent.trim() && !disabled"
            class="bg-sky-600 hover:bg-sky-700 text-white text-xs py-1 px-3 h-auto shadow-xs"
            @click="handleSend"
          >
            <svg
              class="w-3.5 h-3.5 mr-1 inline-block"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            发送
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>
