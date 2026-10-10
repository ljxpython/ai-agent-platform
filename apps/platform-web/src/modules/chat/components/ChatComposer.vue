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
import { useI18n } from "vue-i18n";
import { useUiStore } from "@/stores/ui";
import {
  useVoiceInput,
  type VoiceInputErrorKind,
} from "../composables/useVoiceInput";
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
    canDictate?: boolean;
  }>(),
  {
    showSuggestions: true,
    turnState: "idle",
    canOpenUsage: false,
    planMode: false,
    planModeSupported: false,
    canDictate: false,
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

// --- 语音输入逻辑 ---
let i18nInstance: any = null;
try {
  i18nInstance = useI18n();
} catch {
  // 无 i18n 环境
}
const currentLocale = computed(() => i18nInstance?.locale?.value ?? "zh-CN");

function getI18nText(key: string, defaultText: string): string {
  if (i18nInstance?.t) {
    const val = i18nInstance.t(key);
    if (val && val !== key) return val;
  }
  return defaultText;
}

const baseDraft = ref("");
const lastEmittedVoiceDraft = ref<string | null>(null);
const voiceStatusNotice = ref("");

function combineVoiceDraft(base: string, finalVoice: string): string {
  if (!finalVoice) return base;
  if (!base) return finalVoice;
  if (/\s$/.test(base)) {
    return `${base}${finalVoice}`;
  }
  return `${base}\n${finalVoice}`;
}

const voiceInput = useVoiceInput({
  lang: currentLocale,
  onResult: ({ finalText }) => {
    handleVoiceResult(finalText);
  },
  onError: (kind, rawError) => {
    handleVoiceError(kind, rawError);
  },
  onEnd: (reason) => {
    handleVoiceEnd(reason);
  },
});

const isVoiceActive = computed(() => voiceInput.state.value !== "idle");

function handleVoiceResult(finalVoice: string) {
  if (!finalVoice) return;
  const nextVal = combineVoiceDraft(baseDraft.value, finalVoice);
  lastEmittedVoiceDraft.value = nextVal;
  emit("update:modelValue", nextVal);
}

function handleVoiceError(kind: VoiceInputErrorKind, _raw?: string) {
  if (kind === "cancelled" || kind === "no_speech") {
    return;
  }
  const errorKeyMap: Record<string, string> = {
    microphone_unavailable: "chat.voiceInput.micUnavailable",
    permission_denied: "chat.voiceInput.permissionDenied",
    unsupported_language: "chat.voiceInput.unsupportedLanguage",
    network: "chat.voiceInput.networkError",
  };
  const key = errorKeyMap[kind] || "chat.voiceInput.unknownError";
  const msg = getI18nText(key, "语音识别服务异常");

  try {
    const uiStore = useUiStore();
    uiStore.pushToast({ message: msg, type: "error" });
  } catch {
    // 无 pinia 或测试 mock
  }
}

function handleVoiceEnd(reason: "stop" | "cancel" | "natural" | "error") {
  lastEmittedVoiceDraft.value = null;
  if (reason === "natural") {
    const msg = getI18nText("chat.voiceInput.naturalEnded", "语音输入已结束");
    voiceStatusNotice.value = msg;
    setTimeout(() => {
      if (voiceStatusNotice.value === msg) {
        voiceStatusNotice.value = "";
      }
    }, 3000);
  }
}

function toggleVoiceInput() {
  if (voiceInput.state.value === "listening") {
    voiceInput.stop();
    return;
  }
  if (voiceInput.state.value === "starting") {
    voiceInput.cancel();
    return;
  }
  if (voiceInput.state.value === "stopping") {
    voiceInput.cancel();
    return;
  }
  if (!props.canDictate || isStopBlocked.value || props.isRunning) {
    return;
  }

  baseDraft.value = props.modelValue;
  lastEmittedVoiceDraft.value = null;
  voiceStatusNotice.value = "";
  voiceInput.start();
}

// 监听 props.modelValue：Self-Echo 守卫与外部修改抢占
watch(
  () => props.modelValue,
  (newVal) => {
    if (isVoiceActive.value) {
      if (
        lastEmittedVoiceDraft.value !== null &&
        newVal === lastEmittedVoiceDraft.value
      ) {
        // 自身 final 回流（Self-Echo），放行
        return;
      }
      // 外部修改，取消录音
      voiceInput.cancel();
    }
  },
);

// 门禁失效立即取消
watch(
  () => props.canDictate,
  (can) => {
    if (!can && isVoiceActive.value) {
      voiceInput.cancel();
    }
  },
);

function handleComposerInput() {
  if (isVoiceActive.value) {
    voiceInput.cancel();
  }
}

function handleComposerPaste(event: ClipboardEvent) {
  if (isVoiceActive.value) {
    voiceInput.cancel();
  }
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
  if (
    isStopBlocked.value ||
    props.hasBlockingInterrupt ||
    isVoiceActive.value
  ) {
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
    if (
      props.hasBlockingInterrupt ||
      isStopBlocked.value ||
      isVoiceActive.value
    ) {
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
  } else {
    if (isVoiceActive.value) {
      voiceInput.cancel();
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
  if (isVoiceActive.value) {
    voiceInput.cancel();
  }
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
        @input="handleComposerInput"
        @keydown="handleKeydown"
        @paste="handleComposerPaste"
      />

      <div class="mt-2">
        <div
          class="flex h-8 items-center justify-between gap-2 sm:flex-nowrap"
          :class="isFocusMode || props.compact ? '' : 'sm:gap-3'"
        >
          <div
            class="flex h-8 min-w-0 flex-1 items-center gap-2 overflow-x-hidden no-scrollbar scrollbar-none [&::-webkit-scrollbar]:hidden"
            :class="isFocusMode || props.compact ? 'gap-2' : 'gap-2.5'"
          >
            <!-- 拓展功能加号菜单（录音进行中隐藏避让） -->
            <div v-if="!isVoiceActive" class="relative inline-block text-left">
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

            <!-- 权限策略选择器（录音进行中隐藏避让） -->
            <ThreadAccessPolicySelect
              v-if="projectId && !isVoiceActive"
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

            <!-- 附件按钮（录音进行中隐藏避让） -->
            <button
              v-if="!isVoiceActive"
              type="button"
              class="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-gray-200/80 bg-white/90 px-2.5 text-xs font-medium text-gray-600 shadow-2xs hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white transition-colors"
              :disabled="isRunning || hasBlockingInterrupt || isStopBlocked"
              aria-label="上传附件（图片/文档）"
              @click="openFilePicker"
            >
              <BaseIcon name="paperclip" size="xs" />
              <span class="hidden sm:inline">附件</span>
            </button>

            <!-- 语音听写按钮（纯图标设计） -->
            <button
              v-if="voiceInput.isSupported.value"
              type="button"
              class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-xs font-medium shadow-2xs transition-all"
              :class="[
                voiceInput.state.value === 'listening'
                  ? 'border-rose-400 bg-rose-50 text-rose-600 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-400 animate-pulse'
                  : voiceInput.state.value === 'starting' ||
                      voiceInput.state.value === 'stopping'
                    ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300'
                    : 'border-gray-200/80 bg-white/90 text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white',
                !props.canDictate || isStopBlocked || isRunning
                  ? 'opacity-40 cursor-not-allowed'
                  : 'cursor-pointer',
              ]"
              :disabled="!props.canDictate || isStopBlocked || isRunning"
              :title="
                voiceInput.state.value === 'listening'
                  ? getI18nText('chat.voiceInput.stop', '停止听写')
                  : getI18nText('chat.voiceInput.start', '语音输入')
              "
              :aria-label="
                voiceInput.state.value === 'listening'
                  ? getI18nText('chat.voiceInput.stop', '停止听写')
                  : getI18nText('chat.voiceInput.start', '语音输入')
              "
              :aria-pressed="voiceInput.state.value === 'listening'"
              data-testid="composer-voice-input-btn"
              @click="toggleVoiceInput"
            >
              <BaseIcon name="mic" size="xs" />
            </button>

            <!-- 随行微胶囊：听写中展示声波动效与实时转写文字（弹性全宽） -->
            <div
              v-if="voiceInput.state.value !== 'idle'"
              data-testid="composer-voice-interim-box"
              role="status"
              aria-live="polite"
              class="flex-1 min-w-0 inline-flex h-8 items-center gap-1.5 rounded-lg border border-rose-200/70 bg-rose-50/70 px-2.5 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300 transition-all shadow-2xs overflow-hidden"
            >
              <span
                class="flex items-center gap-0.5 shrink-0"
                aria-hidden="true"
              >
                <span
                  class="inline-block h-2 w-0.5 rounded-full bg-rose-500 animate-pulse"
                />
                <span
                  class="inline-block h-3 w-0.5 rounded-full bg-rose-500 animate-pulse delay-75"
                />
                <span
                  class="inline-block h-1.5 w-0.5 rounded-full bg-rose-500 animate-pulse delay-150"
                />
              </span>
              <span
                v-if="voiceInput.interimText.value"
                class="flex-1 min-w-0 truncate font-normal text-slate-700 dark:text-slate-200"
              >
                {{ voiceInput.interimText.value }}
              </span>
              <span
                v-else
                class="flex-1 min-w-0 truncate font-medium text-rose-600 dark:text-rose-400"
              >
                {{
                  voiceInput.state.value === "starting"
                    ? getI18nText("chat.voiceInput.starting", "启动中...")
                    : voiceInput.state.value === "stopping"
                      ? getI18nText("chat.voiceInput.stopping", "收尾中...")
                      : getI18nText("chat.voiceInput.listening", "正在聆听...")
                }}
              </span>
              <button
                type="button"
                class="ml-0.5 shrink-0 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer"
                title="取消"
                aria-label="取消语音听写"
                @click="voiceInput.cancel()"
              >
                <svg
                  class="h-3 w-3"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </div>

            <!-- 自然结束弱提示（平滑退场） -->
            <div
              v-else-if="voiceStatusNotice"
              class="inline-flex h-8 items-center gap-1.5 rounded-lg bg-gray-50/90 px-2.5 text-xs text-gray-500 dark:bg-dark-800/80 dark:text-dark-400 transition-all shadow-2xs"
            >
              <span>ℹ️ {{ voiceStatusNotice }}</span>
            </div>

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
                :disabled="isStopBlocked || isVoiceActive"
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
