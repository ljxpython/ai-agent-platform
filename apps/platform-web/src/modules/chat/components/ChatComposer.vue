<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  CHAT_ATTACHMENT_ACCEPT,
  type ChatAttachmentBlock,
} from "@/utils/chat-content";
import ChatAttachmentPreview from "./ChatAttachmentPreview.vue";
import ChatModelSelector from "./ChatModelSelector.vue";
import ThreadAccessPolicySelect from "./ThreadAccessPolicySelect.vue";
import type { RuntimeModelItem } from "@/types/management";
import type { AccessPolicy } from "@/services/threads/session.service";

const props = defineProps<{
  modelValue: string;
  attachments: ChatAttachmentBlock[];
  isRunning: boolean;
  hasBlockingInterrupt: boolean;
  canSendFreshMessage: boolean;
  cancelling: boolean;
  sendButtonLabel: string;
  canQueue?: boolean;
  hasQueuedItems?: boolean;
  compact?: boolean;
  focusMode?: boolean;
  models?: RuntimeModelItem[];
  selectedModelId?: string;
  defaultModelName?: string;
  placeholder?: string;
  projectId?: string;
  accessPolicy?: AccessPolicy;
  accessPolicyUpdating?: boolean;
  canWrite?: boolean;
  canSetPolicy?: boolean;
  canFullAccess?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  send: [];
  queue: [];
  cancel: [];
  "file-input-change": [event: Event];
  "composer-paste": [event: ClipboardEvent];
  "remove-attachment": [index: number];
  "update:selectedModelId": [value: string];
  "update:accessPolicy": [value: AccessPolicy];
  "change:accessPolicy": [value: AccessPolicy];
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const composerModel = computed({
  get: () => props.modelValue,
  set: (value: string) => emit("update:modelValue", value),
});

const isDenseMode = computed(() => Boolean(props.compact));
const isFocusMode = computed(() => Boolean(props.focusMode));

const composerCollapsedHeight = computed(() => {
  if (isDenseMode.value) {
    return 28;
  }

  return 32;
});
const composerMinHeight = computed(() => composerCollapsedHeight.value);
const composerMaxHeight = computed(() => {
  if (isFocusMode.value) {
    return 132;
  }

  if (isDenseMode.value) {
    return 112;
  }

  return 120;
});

const isQueueMode = computed(() => {
  return (props.isRunning || Boolean(props.hasQueuedItems)) && Boolean(props.canQueue);
});

const helperText = computed(() =>
  props.hasBlockingInterrupt
    ? "当前运行正在等待人工决策。你可以先编辑下一条消息草稿，处理完中断后再发送。"
    : isQueueMode.value
      ? composerModel.value.trim()
        ? "你可以按 Enter 或点击“补充要求”将新指令加入执行队列，按顺序执行。"
        : props.isRunning
          ? "Agent 正在实时输出。你可以输入补充指令排队发送，或点击“停止生成”。"
          : "当前队列中有待执行消息。你可以输入补充指令加入队列，等待自动执行。"
      : "",
);

function handleComposerPaste(event: ClipboardEvent) {
  emit("composer-paste", event);
}

function openFilePicker() {
  fileInputRef.value?.click();
}

function applyTextareaHeight(nextHeight: number) {
  const textarea = textareaRef.value;
  if (!textarea) {
    return;
  }

  textarea.style.height = `${nextHeight}px`;
}

function clampComposerHeight(nextHeight: number) {
  return Math.max(
    composerMinHeight.value,
    Math.min(nextHeight, composerMaxHeight.value),
  );
}

async function syncTextareaHeight() {
  await nextTick();

  const textarea = textareaRef.value;
  if (!textarea) {
    return;
  }

  textarea.style.height = "0px";
  const nextHeight =
    composerModel.value.trim().length === 0
      ? composerCollapsedHeight.value
      : clampComposerHeight(
          Math.max(composerCollapsedHeight.value, textarea.scrollHeight),
        );
  applyTextareaHeight(nextHeight);
}

watch(
  () => props.modelValue,
  async () => {
    await syncTextareaHeight();
  },
  { immediate: true },
);

watch(
  () => props.attachments.length,
  async () => {
    await syncTextareaHeight();
  },
);

watch(
  () => props.compact,
  async () => {
    await syncTextareaHeight();
  },
  { immediate: true },
);

watch(
  () => props.focusMode,
  async () => {
    await syncTextareaHeight();
  },
);

const canSubmitFreshOrQueue = computed(() => {
  if (props.cancelling || props.hasBlockingInterrupt) {
    return false;
  }
  const hasContent =
    composerModel.value.trim().length > 0 || props.attachments.length > 0;
  if (!hasContent) {
    return false;
  }
  if (props.canQueue) {
    return true;
  }
  return props.canSendFreshMessage;
});

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    if (event.isComposing) {
      return;
    }
    event.preventDefault();
    if (props.hasBlockingInterrupt || props.cancelling) {
      return;
    }
    const hasContent =
      composerModel.value.trim().length > 0 || props.attachments.length > 0;
    if (!hasContent) {
      return;
    }
    if (isQueueMode.value) {
      emit("queue");
    } else {
      if (props.canSendFreshMessage || props.canQueue) {
        emit("send");
      }
    }
  }
}

onMounted(async () => {
  await syncTextareaHeight();
});

defineExpose({
  focus: () => textareaRef.value?.focus(),
});
</script>

<template>
  <div
    class="pw-chat-composer-wrap transition-all duration-200"
    :class="
      isFocusMode
        ? 'px-3 pb-2 pt-1 md:px-4'
        : props.compact
          ? 'px-3 pb-2 pt-1 md:px-4'
          : ''
    "
  >
    <div
      class="pw-chat-composer transition-all duration-200 focus-within:border-primary-500/80 focus-within:ring-2 focus-within:ring-primary-500/15 focus-within:shadow-md"
      :class="isFocusMode ? 'max-w-[780px]' : ''"
    >
      <div
        v-if="attachments.length > 0"
        class="mb-4 flex flex-wrap gap-3"
      >
        <ChatAttachmentPreview
          v-for="(attachment, index) in attachments"
          :key="`composer-attachment-${index}`"
          :block="attachment"
          removable
          @remove="emit('remove-attachment', index)"
        />
      </div>

      <textarea
        ref="textareaRef"
        v-model="composerModel"
        :rows="1"
        class="pw-input resize-none border-0 bg-transparent px-0 py-0 shadow-none focus:ring-0"
        :class="[
          isDenseMode
            ? 'min-h-[28px] max-h-[112px] overflow-y-auto text-sm leading-6'
            : 'min-h-[32px] max-h-[120px] overflow-y-auto text-sm leading-6',
          isFocusMode ? 'text-sm leading-6' : '',
        ]"
        :placeholder="props.placeholder || '输入消息，Enter 发送，Shift + Enter 换行。'"
        aria-label="消息草稿"
        @keydown="handleKeydown"
        @paste="handleComposerPaste"
      />

      <div class="mt-2 space-y-1.5 transition-all duration-200">
        <div
          class="flex flex-wrap items-center justify-between gap-2 transition-all duration-200 sm:flex-nowrap"
          :class="isFocusMode || props.compact ? '' : 'sm:gap-3'"
        >
          <div
            class="flex min-w-0 basis-full items-center gap-2 overflow-x-auto pb-1 sm:basis-auto"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <ThreadAccessPolicySelect
              v-if="projectId"
              :model-value="accessPolicy || 'review'"
              :disabled="isRunning || hasBlockingInterrupt || canSetPolicy === false || canWrite === false"
              :loading="accessPolicyUpdating"
              :can-write="canWrite !== false"
              :can-full-access="canFullAccess"
              @update:model-value="emit('update:accessPolicy', $event)"
              @change="emit('change:accessPolicy', $event)"
            />
            <button
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-gray-200/80 bg-white/90 px-2.5 text-xs font-medium text-gray-600 shadow-2xs hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white transition-colors"
              :disabled="isRunning || hasBlockingInterrupt"
              aria-label="上传附件（图片/文档）"
              @click="openFilePicker"
            >
              <BaseIcon
                name="paperclip"
                size="xs"
              />
              <span class="hidden sm:inline">附件</span>
            </button>
            <input
              ref="fileInputRef"
              type="file"
              class="hidden"
              multiple
              :accept="CHAT_ATTACHMENT_ACCEPT"
              @change="emit('file-input-change', $event)"
            >
          </div>

          <div
            class="ml-auto flex shrink-0 items-center gap-2"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <ChatModelSelector
              v-if="models && projectId"
              :models="models"
              :project-id="projectId"
              :selected-model-id="selectedModelId"
              :default-model-name="defaultModelName"
              :disabled="isRunning || hasBlockingInterrupt"
              @update:selected-model-id="emit('update:selectedModelId', $event)"
            />
            <!-- 排队模式且有输入：支持一键补充要求排队，并保留停止按钮（若处于运行中） -->
            <template v-if="isQueueMode && composerModel.trim().length > 0">
              <span class="hidden md:inline-flex items-center gap-1 text-[11px] text-gray-400 dark:text-dark-400 font-mono select-none">
                <kbd class="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 text-[10px] dark:border-dark-700 dark:bg-dark-800">↵</kbd>
                <span>排队</span>
              </span>
              <button
                type="button"
                class="flex h-8 items-center gap-1.5 rounded-full bg-blue-600 px-3 text-xs font-medium text-white shadow-xs transition-all hover:bg-blue-700 active:scale-95 disabled:opacity-50"
                :disabled="cancelling"
                title="排队加入执行队列"
                @click="emit('queue')"
              >
                <BaseIcon
                  name="sparkle"
                  size="xs"
                />
                <span>补充要求</span>
              </button>
              <button
                v-if="isRunning"
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-xs transition-all duration-150 hover:bg-red-600 active:scale-90 disabled:opacity-35"
                :disabled="cancelling"
                :title="cancelling ? '停止中...' : '停止生成'"
                @click="emit('cancel')"
              >
                <BaseIcon
                  name="x"
                  size="xs"
                />
                <span class="sr-only">停止生成</span>
              </button>
            </template>

            <!-- 运行中但无输入：仅展示停止生成按钮 -->
            <template v-else-if="isRunning">
              <button
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-xs transition-all duration-150 hover:bg-red-600 active:scale-90 disabled:opacity-35"
                :disabled="cancelling"
                :title="cancelling ? '停止中...' : '停止生成'"
                @click="emit('cancel')"
              >
                <BaseIcon
                  name="x"
                  size="xs"
                />
                <span class="sr-only">{{ cancelling ? '停止中...' : '停止生成' }}</span>
              </button>
            </template>

            <!-- 常规非运行状态：发送按钮 -->
            <template v-else>
              <span class="hidden md:inline-flex items-center gap-1 text-[11px] text-gray-400 dark:text-dark-400 font-mono select-none">
                <kbd class="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 text-[10px] dark:border-dark-700 dark:bg-dark-800">↵</kbd>
                <span>发送</span>
              </span>
              <button
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500 text-white shadow-xs transition-all duration-150 hover:bg-blue-600 active:scale-90 disabled:opacity-35 disabled:cursor-not-allowed dark:bg-blue-600 dark:hover:bg-blue-500 shadow-blue-500/25"
                :disabled="!canSubmitFreshOrQueue"
                :title="sendButtonLabel"
                :aria-label="sendButtonLabel"
                @click="emit('send')"
              >
                <svg
                  class="h-4 w-4 fill-none stroke-current stroke-[2.5]"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M12 19V5m0 0l-6 6m6-6l6 6"
                  />
                </svg>
                <span class="sr-only">{{ sendButtonLabel }}</span>
              </button>
            </template>
          </div>
        </div>

        <p
          v-if="!isFocusMode && helperText"
          class="px-0.5 text-[11px] leading-5 text-gray-400 dark:text-dark-400"
        >
          {{ helperText }}
        </p>
      </div>
    </div>
  </div>
</template>
