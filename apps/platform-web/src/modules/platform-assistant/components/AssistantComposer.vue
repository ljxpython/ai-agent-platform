<script setup lang="ts">
import { ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import ChatModelSelector from "@/modules/chat/components/ChatModelSelector.vue";
import type { RuntimeModelItem } from "@/types/management";

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    isRunning?: boolean;
    models?: RuntimeModelItem[];
    selectedModelId?: string;
    defaultModelId?: string;
    defaultModelName?: string;
    projectId?: string;
  }>(),
  {
    disabled: false,
    isRunning: false,
    models: () => [],
    selectedModelId: "",
    defaultModelId: "",
    defaultModelName: "",
    projectId: "",
  },
);

const emit = defineEmits<{
  (e: "send", text: string): void;
  (e: "stop"): void;
  (e: "update:selectedModelId", value: string): void;
}>();

const inputContent = ref("");

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    if (event.isComposing) return;
    event.preventDefault();
    if (props.isRunning || props.disabled) return;
    handleSend();
  }
}

function handleSend() {
  const trimmed = inputContent.value.trim();
  if (!trimmed || props.disabled || props.isRunning) return;
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
      class="relative flex flex-col bg-gray-50/80 dark:bg-dark-950/80 border border-gray-200 dark:border-dark-700 rounded-xl p-2.5 hover:border-sky-300 dark:hover:border-sky-700/60 focus-within:border-sky-500 focus-within:ring-2 focus-within:ring-sky-500/15 focus-within:bg-white dark:focus-within:bg-dark-900 transition-all duration-200"
    >
      <textarea
        v-model="inputContent"
        rows="3"
        class="w-full bg-transparent resize-none border-none outline-none ring-0 focus:outline-none focus:ring-0 focus:border-none p-1 text-xs text-gray-900 dark:text-white placeholder-gray-400"
        placeholder="咨询平台用法、排查异常、或探讨创意... (Enter 发送, Shift+Enter 换行)"
        :disabled="disabled"
        @keydown="handleKeyDown"
      />

      <div class="flex items-center justify-between pt-1 gap-2">
        <span class="text-[10px] text-gray-400 select-none truncate min-w-0">
          只读环境 · 生产写入须逐次审批
        </span>

        <div class="flex items-center gap-2 shrink-0">
          <!-- 渠道与模型选择器 -->
          <ChatModelSelector
            v-if="projectId && models && models.length > 0"
            :models="models"
            :project-id="projectId"
            :selected-model-id="selectedModelId"
            :default-model-id="defaultModelId"
            :default-model-name="defaultModelName"
            :disabled="isRunning || disabled"
            @update:selected-model-id="emit('update:selectedModelId', $event)"
          />

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
            :disabled="!inputContent.trim() || disabled"
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
