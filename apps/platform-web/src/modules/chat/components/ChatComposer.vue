<script setup lang="ts">
import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type CSSProperties,
} from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  CHAT_ATTACHMENT_ACCEPT,
  type ChatAttachmentBlock,
} from "@/utils/chat-content";
import ChatAttachmentPreview from "./ChatAttachmentPreview.vue";
import ChatModelSelector from "./ChatModelSelector.vue";
import ThreadAccessPolicySelect from "./ThreadAccessPolicySelect.vue";
import ComposerSuggestions from "./ComposerSuggestions.vue";
import type { RuntimeModelItem } from "@/types/management";
import type { AccessPolicy } from "@/services/threads/session.service";
import type { SessionTurnState } from "../composables/useChatSession";

const props = withDefaults(
  defineProps<{
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
    defaultModelId?: string;
    defaultModelName?: string;
    placeholder?: string;
    footerText?: string;
    projectId?: string;
    accessPolicy?: AccessPolicy;
    accessPolicyUpdating?: boolean;
    canWrite?: boolean;
    canSetPolicy?: boolean;
    canFullAccess?: boolean;
    showSuggestions?: boolean;
    turnState?: SessionTurnState;
    canOpenUsage?: boolean;
    planMode?: boolean;
    planModeSupported?: boolean;
  }>(),
  {
    showSuggestions: true,
    turnState: "idle",
    canOpenUsage: false,
    planMode: false,
    planModeSupported: false,
  },
);

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
  "select-suggestion": [prompt: string];
  "open-usage": [];
  "update:planMode": [value: boolean];
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
  return (
    (props.isRunning || Boolean(props.hasQueuedItems)) &&
    Boolean(props.canQueue)
  );
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

const isStopBlocked = computed(() => {
  return (
    props.cancelling ||
    props.turnState === "stopping" ||
    props.turnState === "stop_unconfirmed"
  );
});

const canSubmitFreshOrQueue = computed(() => {
  if (isStopBlocked.value || props.hasBlockingInterrupt) {
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
    if (props.hasBlockingInterrupt || isStopBlocked.value) {
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

const shouldShowSuggestions = computed(
  () =>
    (props.showSuggestions ?? true) &&
    !props.isRunning &&
    !props.hasBlockingInterrupt &&
    !isStopBlocked.value &&
    !composerModel.value.trim(),
);

function handleSelectSuggestion(prompt: string) {
  composerModel.value = prompt;
  nextTick(async () => {
    textareaRef.value?.focus();
    await syncTextareaHeight();
  });
  emit("select-suggestion", prompt);
}

const featureMenuOpen = ref(false);
const featureMenuTriggerRef = ref<HTMLButtonElement | null>(null);
const featureDropdownRef = ref<HTMLElement | null>(null);
const featureDropdownStyle = ref<CSSProperties>({});

function updateFeatureMenuPosition() {
  if (!featureMenuOpen.value || !featureMenuTriggerRef.value) return;
  const rect = featureMenuTriggerRef.value.getBoundingClientRect();
  const dropdownWidth = 230;
  featureDropdownStyle.value = {
    position: "fixed",
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - dropdownWidth - 12))}px`,
    bottom: `${Math.max(12, window.innerHeight - rect.top + 8)}px`,
    width: `${dropdownWidth}px`,
    zIndex: 9999,
  };
}

function toggleFeatureMenu() {
  if (props.isRunning || props.hasBlockingInterrupt || isStopBlocked.value)
    return;
  featureMenuOpen.value = !featureMenuOpen.value;
  if (featureMenuOpen.value) {
    nextTick(() => updateFeatureMenuPosition());
  }
}

function togglePlanModeFromMenu() {
  emit("update:planMode", !props.planMode);
  featureMenuOpen.value = false;
}

function handlePointerDownOutside(event: PointerEvent) {
  if (!featureMenuOpen.value) return;
  const target = event.target as Node | null;
  if (
    featureMenuTriggerRef.value?.contains(target) ||
    featureDropdownRef.value?.contains(target)
  ) {
    return;
  }
  featureMenuOpen.value = false;
}

onMounted(async () => {
  await syncTextareaHeight();
  document.addEventListener("pointerdown", handlePointerDownOutside);
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", handlePointerDownOutside);
});

defineExpose({
  focus: () => textareaRef.value?.focus(),
});
</script>

<template>
  <div
    class="pw-chat-composer-wrap shrink-0"
    :class="
      isFocusMode
        ? 'px-3 pb-2 pt-1 md:px-4'
        : props.compact
          ? 'px-3 pb-1.5 pt-1 md:px-4'
          : ''
    "
  >
    <div
      v-if="$slots['top-tray']"
      class="mx-auto w-full max-w-4xl px-3 lg:max-w-5xl"
      :class="isFocusMode ? '!max-w-[780px]' : ''"
    >
      <slot name="top-tray" />
    </div>

    <!-- 灵感建议胶囊栏（支持小惊喜撒花与一键填入） -->
    <div
      v-if="shouldShowSuggestions"
      class="mx-auto mb-1.5 w-full max-w-4xl px-3 lg:max-w-5xl"
      :class="isFocusMode ? '!max-w-[780px]' : ''"
      data-testid="composer-suggestions-container"
    >
      <ComposerSuggestions
        :disabled="isRunning"
        @select="handleSelectSuggestion"
      />
    </div>

    <div
      class="pw-chat-composer transition-[border-color,box-shadow] duration-150 focus-within:border-gray-300 focus-within:shadow-md dark:focus-within:border-dark-600"
      :class="isFocusMode ? 'max-w-[780px]' : ''"
    >
      <div v-if="attachments.length > 0" class="mb-4 flex flex-wrap gap-3">
        <ChatAttachmentPreview
          v-for="(attachment, index) in attachments"
          :key="`composer-attachment-${index}`"
          :block="attachment"
          removable
          @remove="emit('remove-attachment', index)"
        />
      </div>

      <!-- 规划模式常驻胶囊徽章 -->
      <div v-if="props.planMode" class="mb-2 flex items-center">
        <div
          data-testid="plan-mode-active-pill"
          class="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-800 dark:border-sky-500/30 dark:bg-sky-950/60 dark:text-sky-200 shadow-2xs"
        >
          <span>📋 规划模式已启用 (Plan Mode)</span>
          <button
            type="button"
            class="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full hover:bg-sky-200 dark:hover:bg-sky-800 text-sky-600 dark:text-sky-300 transition-colors cursor-pointer"
            title="取消本次规划模式"
            aria-label="取消本次规划模式"
            @click="emit('update:planMode', false)"
          >
            <span class="text-xs leading-none">✕</span>
          </button>
        </div>
      </div>

      <textarea
        ref="textareaRef"
        v-model="composerModel"
        :rows="1"
        class="pw-input !transition-none resize-none border-0 bg-transparent shadow-none focus:ring-0"
        :class="[
          isDenseMode
            ? 'min-h-[28px] max-h-[112px] overflow-y-auto px-1 py-1 text-sm leading-5'
            : 'min-h-[32px] max-h-[120px] overflow-y-auto px-1 py-1.5 text-sm leading-5',
          isFocusMode ? 'text-sm leading-5' : '',
        ]"
        :placeholder="
          props.placeholder || '输入消息，Enter 发送，Shift + Enter 换行。'
        "
        aria-label="消息草稿"
        @keydown="handleKeydown"
        @paste="handleComposerPaste"
      />

      <div class="mt-2">
        <div
          class="flex h-8 items-center justify-between gap-2 sm:flex-nowrap"
          :class="isFocusMode || props.compact ? '' : 'sm:gap-3'"
        >
          <div
            class="flex h-8 min-w-0 items-center gap-2 overflow-x-auto no-scrollbar"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <!-- 拓展功能加号菜单（参考谷歌输入框交互） -->
            <div class="relative inline-block text-left">
              <button
                ref="featureMenuTriggerRef"
                type="button"
                data-testid="composer-feature-menu-btn"
                class="inline-flex h-8 shrink-0 items-center justify-center gap-1 rounded-lg border px-2 text-xs font-medium transition-colors"
                :class="[
                  props.planMode
                    ? 'border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-600 dark:bg-sky-950/60 dark:text-sky-200'
                    : 'border-gray-200/80 bg-white/90 text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white',
                  isRunning || hasBlockingInterrupt || isStopBlocked
                    ? 'opacity-50 cursor-not-allowed'
                    : 'cursor-pointer',
                ]"
                :disabled="isRunning || hasBlockingInterrupt || isStopBlocked"
                title="功能扩展"
                aria-label="功能扩展"
                @click="toggleFeatureMenu"
              >
                <svg
                  class="h-3.5 w-3.5 transition-transform duration-150"
                  :class="featureMenuOpen ? 'rotate-45' : ''"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
            </div>

            <ThreadAccessPolicySelect
              v-if="projectId"
              :model-value="accessPolicy || 'review'"
              :disabled="
                isRunning ||
                hasBlockingInterrupt ||
                isStopBlocked ||
                canSetPolicy === false ||
                canWrite === false
              "
              :loading="accessPolicyUpdating"
              :can-write="canWrite !== false"
              :can-full-access="canFullAccess"
              @update:model-value="emit('update:accessPolicy', $event)"
              @change="emit('change:accessPolicy', $event)"
            />
            <button
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-gray-200/80 bg-white/90 px-2.5 text-xs font-medium text-gray-600 shadow-2xs hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white transition-colors"
              :disabled="isRunning || hasBlockingInterrupt || isStopBlocked"
              aria-label="上传附件（图片/文档）"
              @click="openFilePicker"
            >
              <BaseIcon name="paperclip" size="xs" />
              <span class="hidden sm:inline">附件</span>
            </button>
            <input
              ref="fileInputRef"
              type="file"
              class="hidden"
              multiple
              :accept="CHAT_ATTACHMENT_ACCEPT"
              @change="emit('file-input-change', $event)"
            />
          </div>

          <div
            class="ml-auto flex h-8 shrink-0 items-center gap-2"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <ChatModelSelector
              v-if="models && projectId"
              :models="models"
              :project-id="projectId"
              :selected-model-id="selectedModelId"
              :default-model-id="defaultModelId"
              :default-model-name="defaultModelName"
              :disabled="isRunning || hasBlockingInterrupt || isStopBlocked"
              @update:selected-model-id="emit('update:selectedModelId', $event)"
            />
            <!-- 排队模式且有输入：支持一键补充要求排队，并保留停止按钮（若处于运行中） -->
            <template v-if="isQueueMode && composerModel.trim().length > 0">
              <span
                class="hidden md:inline-flex items-center gap-1 text-[11px] text-gray-400 dark:text-dark-400 font-mono select-none"
              >
                <kbd
                  class="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 text-[10px] dark:border-dark-700 dark:bg-dark-800"
                  >↵</kbd
                >
                <span>排队</span>
              </span>
              <button
                type="button"
                class="flex h-8 items-center gap-1.5 rounded-full bg-blue-600 px-3 text-xs font-medium text-white shadow-xs transition-all hover:bg-blue-700 active:scale-95 disabled:opacity-50"
                :disabled="isStopBlocked"
                title="排队加入执行队列"
                @click="emit('queue')"
              >
                <BaseIcon name="sparkle" size="xs" />
                <span>补充要求</span>
              </button>
              <button
                v-if="isRunning"
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-xs transition-all duration-150 hover:bg-red-600 active:scale-90 disabled:opacity-35"
                :disabled="isStopBlocked"
                :title="isStopBlocked ? '停止中...' : '停止生成'"
                @click="emit('cancel')"
              >
                <BaseIcon name="x" size="xs" />
                <span class="sr-only">停止生成</span>
              </button>
            </template>

            <!-- 运行中但无输入：仅展示停止生成按钮 -->
            <template v-else-if="isRunning">
              <button
                type="button"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-xs transition-all duration-150 hover:bg-red-600 active:scale-90 disabled:opacity-35"
                :disabled="isStopBlocked"
                :title="isStopBlocked ? '停止中...' : '停止生成'"
                @click="emit('cancel')"
              >
                <BaseIcon name="x" size="xs" />
                <span class="sr-only">{{
                  isStopBlocked ? "停止中..." : "停止生成"
                }}</span>
              </button>
            </template>

            <!-- 常规非运行状态：发送按钮 -->
            <template v-else>
              <span
                class="hidden md:inline-flex items-center gap-1 text-[11px] text-gray-400 dark:text-dark-400 font-mono select-none"
              >
                <kbd
                  class="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 text-[10px] dark:border-dark-700 dark:bg-dark-800"
                  >↵</kbd
                >
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
      </div>
    </div>

    <div
      v-if="!isFocusMode"
      class="mx-auto mt-1 flex h-4 w-full max-w-4xl lg:max-w-5xl items-center justify-center gap-1.5 px-2 text-center font-mono text-[11px] leading-4 text-gray-400 select-none dark:text-dark-400"
    >
      <span
        class="truncate"
        :class="
          canOpenUsage && footerText
            ? 'cursor-pointer hover:text-gray-600 dark:hover:text-dark-200 transition-colors'
            : ''
        "
        @click="canOpenUsage && footerText ? $emit('open-usage') : undefined"
      >
        {{ helperText || footerText || "" }}
      </span>
      <button
        v-if="!helperText && footerText && canOpenUsage"
        type="button"
        class="inline-flex items-center gap-0.5 text-primary-600 hover:text-primary-700 hover:underline dark:text-primary-400 dark:hover:text-primary-300 font-medium transition-colors cursor-pointer"
        title="查看详细用量与成本账单"
        @click="$emit('open-usage')"
      >
        <span>明细</span>
        <span class="text-[10px]">↗</span>
      </button>
    </div>

    <!-- 功能菜单浮层 (Teleport 到 body，彻底解耦容器 overflow 与 stacking context) -->
    <Teleport to="body">
      <div
        v-if="featureMenuOpen"
        ref="featureDropdownRef"
        :style="featureDropdownStyle"
        data-testid="composer-feature-dropdown"
        class="rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl dark:border-dark-700 dark:bg-dark-800 animate-in fade-in zoom-in-95 duration-100"
      >
        <button
          v-if="planModeSupported"
          type="button"
          data-testid="feature-toggle-plan-mode"
          class="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition-colors hover:bg-gray-100 dark:hover:bg-dark-700/80 cursor-pointer"
          @click="togglePlanModeFromMenu"
        >
          <div
            class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border"
            :class="
              props.planMode
                ? 'border-sky-500 bg-sky-500 text-white'
                : 'border-gray-300 dark:border-dark-600'
            "
          >
            <svg
              v-if="props.planMode"
              class="h-3 w-3 stroke-current stroke-2 fill-none"
              viewBox="0 0 24 24"
            >
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div
              class="font-medium text-gray-900 dark:text-white flex items-center justify-between"
            >
              <span>先规划 (Plan Mode)</span>
              <span class="text-[10px] text-sky-600 dark:text-sky-400 font-mono"
                >单次</span
              >
            </div>
            <p
              class="mt-0.5 text-[11px] leading-3.5 text-gray-400 dark:text-dark-400"
            >
              先行调研并制定计划，待审阅批准后再执行
            </p>
          </div>
        </button>
        <div
          v-else
          class="px-2.5 py-2 text-[11px] text-gray-400 dark:text-dark-500"
        >
          当前 Agent 暂无可用扩展功能
        </div>
      </div>
    </Teleport>
  </div>
</template>
