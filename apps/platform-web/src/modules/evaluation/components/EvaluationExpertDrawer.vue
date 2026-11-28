<script setup lang="ts">
import { computed, nextTick, ref, toRef, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import ChatModelSelector from "@/modules/chat/components/ChatModelSelector.vue";
import { useEvalExpertChat } from "@/modules/evaluation/composables/useEvalExpertChat";
import type { CaseUpsertPayload } from "@/services/evaluation/studio";
import { getActivePinia } from "pinia";
import { useAuthStore } from "@/stores/auth";
import type { RuntimeModelItem } from "@/types/management";

const props = defineProps<{
  show: boolean;
  projectId: string;
  kind: "eval_copilot" | "eval_diagnosis";
  refId: string;
  defaultModelId: string;
  modelOptions?: Array<{ label: string; value: string; isBroken?: boolean }>;
  models?: RuntimeModelItem[];
}>();

const emit = defineEmits<{
  close: [];
  adoptCases: [items: CaseUpsertPayload[]];
  casesUpdated: [];
  trialRunUpdated: [];
}>();

const DEFAULT_DRAWER_WIDTH = 600;
const EXPANDED_DRAWER_WIDTH = 960;
const DRAWER_WIDTH_STORAGE_KEY = "pw_eval_expert_drawer_width";

const savedWidth =
  typeof window !== "undefined"
    ? Number(localStorage.getItem(DRAWER_WIDTH_STORAGE_KEY))
    : null;
const drawerWidth = ref<number>(
  savedWidth && savedWidth >= 460 ? savedWidth : DEFAULT_DRAWER_WIDTH,
);

watch(drawerWidth, (newW) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(DRAWER_WIDTH_STORAGE_KEY, String(newW));
  }
});

function toggleExpandedWidth() {
  drawerWidth.value =
    drawerWidth.value >= 800 ? DEFAULT_DRAWER_WIDTH : EXPANDED_DRAWER_WIDTH;
}

const activeView = ref<"chat" | "history">("chat");
const messagesContainer = ref<HTMLElement | null>(null);
const userAvatarUrl = computed(() =>
  getActivePinia() ? useAuthStore().userAvatar : "",
);

const projectIdRef = toRef(props, "projectId");
const kindRef = toRef(props, "kind");
const selectedModelId = ref(props.defaultModelId);

watch(
  () => props.defaultModelId,
  (val) => {
    if (!selectedModelId.value && val) selectedModelId.value = val;
  },
  { immediate: true },
);

const chat = useEvalExpertChat(projectIdRef, kindRef, selectedModelId, {
  onCasesMutated: () => emit("casesUpdated"),
  onTrialRunUpdated: () => emit("trialRunUpdated"),
});

// 优先复用完整的 RuntimeModelItem[] 给 ChatModelSelector；单元测试等只传 modelOptions 时做轻量兼容
const selectorModels = computed<RuntimeModelItem[]>(() => {
  if (props.models && props.models.length > 0) {
    return props.models;
  }
  return (props.modelOptions ?? [])
    .filter((m) => !m.isBroken)
    .map((opt) => ({
      id: opt.value,
      model: opt.label,
      display_name: opt.label,
      provider: "default",
      api_style: "openai-compatible",
      base_url: "",
      protocol: "openai-compatible",
      credential_configured: true,
      enabled: true,
      scope_type: "project",
    }));
});

const inputDraft = ref("");
const fileInputRef = ref<HTMLInputElement | null>(null);

const isCopilot = computed(() => props.kind === "eval_copilot");
const avatarSrc = computed(() =>
  isCopilot.value ? "/eval-copilot-avatar.png" : "/assistant-mascot.gif",
);
const title = computed(() =>
  isCopilot.value
    ? "AI 出题专家 · Eval Copilot"
    : "AI 白盒诊断专家 · Eval Diagnosis",
);
const subtitle = computed(() => {
  const scope = props.refId ? `关联 ${props.refId.slice(0, 8)} · ` : "";
  return isCopilot.value
    ? `${scope}多轮出题 · 资料提取 · 试跑与闭环修复`
    : `${scope}三层归因 · 瓶颈排查 · 改造建议`;
});

const quickPrompts = computed(() =>
  isCopilot.value
    ? [
        {
          icon: "📝",
          title: "设计多轮博弈 Case",
          desc: "读取题库与工具清单并生成草稿",
          text: `请先查看 suite_id=${props.refId} 现有考题与目标图工具清单，为我设计 1 道带动态追问的多轮博弈 Case 并写入草稿`,
        },
        {
          icon: "🧪",
          title: "巡检试跑与补建回归",
          desc: "排查最近一次试跑失败原因",
          text: `帮我检查 suite_id=${props.refId} 最近一次试跑或失败记录，指出可改进的考题或补建 1 道回归用例`,
        },
      ]
    : [
        {
          icon: "🔍",
          title: "三层白盒归因分析",
          desc: "Data / Retrieval / Reasoning Gap",
          text: `请读取 run_id=${props.refId} 的概览与失败用例证据，按 Data / Retrieval / Reasoning Gap 三层归因`,
        },
        {
          icon: "⚡",
          title: "耗时与工具瓶颈诊断",
          desc: "定位 TTFT 偏高或工具调用异常",
          text: `分析 run_id=${props.refId} 中 TTFT 偏高或工具调用异常的具体瓶颈并给出改造建议`,
        },
      ],
);

function scrollToBottom() {
  void nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

watch(
  () => {
    const list = chat.messages.value;
    const last = list[list.length - 1];
    return [list.length, last?.content?.length || 0];
  },
  () => scrollToBottom(),
);

watch(
  () => [props.kind, props.refId],
  () => {
    chat.reset(props.refId, { preserveLastThread: true });
    activeView.value = "chat";
    if (props.show) {
      void chat.initForContext(props.refId);
    }
  },
);

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      activeView.value = "chat";
      void chat.initForContext(props.refId);
    }
  },
  { immediate: true },
);

function handleNewSession() {
  chat.reset(props.refId);
  activeView.value = "chat";
}

function toggleHistoryView() {
  if (activeView.value === "chat") {
    activeView.value = "history";
    void chat.loadThreads(props.refId);
  } else {
    activeView.value = "chat";
  }
}

async function handleSelectHistoryThread(threadId: string) {
  await chat.selectThread(threadId, props.refId);
  activeView.value = "chat";
}

function triggerFilePicker() {
  fileInputRef.value?.click();
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement | null;
  if (target?.files?.length) {
    chat.addPendingFiles(target.files);
    target.value = "";
  }
}

async function submitPrompt(text?: string) {
  const payload = (text ?? inputDraft.value).trim();
  if (!payload) return;
  if (!text) inputDraft.value = "";
  await chat.send(payload, props.refId);
}

const trialIsRunning = computed(() =>
  ["queued", "running"].includes(chat.trialRunStatus.value),
);

const trialFinished = computed(() =>
  ["completed", "failed", "error", "cancelled"].includes(
    chat.trialRunStatus.value,
  ),
);
</script>

<template>
  <BaseDrawer
    :show="show"
    :title="title"
    :resizable="true"
    :custom-width="drawerWidth"
    :min-width="460"
    flush
    @close="emit('close')"
    @update:custom-width="drawerWidth = $event"
  >
    <template #title>
      <div class="flex items-center gap-2.5 min-w-0">
        <div
          class="relative w-8 h-8 rounded-full shrink-0 overflow-hidden bg-emerald-50 dark:bg-emerald-950/50 ring-1 ring-emerald-200 dark:ring-emerald-800/60 p-0.5"
        >
          <img
            :src="avatarSrc"
            :alt="title"
            class="w-full h-full object-contain drop-shadow-2xs"
          />
        </div>
        <div class="min-w-0">
          <h2 class="text-xs font-bold text-gray-900 dark:text-white truncate">
            {{ title }}
          </h2>
          <p class="text-[10px] text-gray-400 truncate">
            {{ subtitle }}
          </p>
        </div>
      </div>
    </template>

    <template #header-actions>
      <div class="flex items-center gap-1.5">
        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 dark:border-dark-700 hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-700 dark:text-dark-200 transition cursor-pointer"
          :title="
            drawerWidth >= 800
              ? '收起为标准宽度 (600px)'
              : '展开为宽屏模式 (960px)'
          "
          data-testid="expert-toggle-width-btn"
          @click="toggleExpandedWidth"
        >
          <BaseIcon
            :name="drawerWidth >= 800 ? 'minimize' : 'maximize'"
            class="w-3.5 h-3.5 text-emerald-500"
          />
          <span class="hidden sm:inline">{{
            drawerWidth >= 800 ? "标准" : "宽屏"
          }}</span>
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/80 dark:hover:bg-emerald-900 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 transition cursor-pointer"
          title="开启全新会话"
          data-testid="expert-new-thread-btn"
          @click="handleNewSession"
        >
          <BaseIcon
            name="plus"
            class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400"
          />
          <span>新会话</span>
        </button>

        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 dark:border-dark-700 hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-700 dark:text-dark-200 transition cursor-pointer"
          :title="activeView === 'chat' ? '查看历史会话列表' : '返回当前对话'"
          data-testid="expert-history-btn"
          @click="toggleHistoryView"
        >
          <BaseIcon
            :name="activeView === 'chat' ? 'threads' : 'chat'"
            class="w-3.5 h-3.5 text-emerald-500"
          />
          <span>{{ activeView === "chat" ? "历史会话" : "返回对话" }}</span>
          <span
            v-if="activeView === 'chat' && chat.threads.value.length > 0"
            class="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] bg-gray-100 dark:bg-dark-800 text-gray-500 dark:text-dark-300"
          >
            {{ chat.threads.value.length }}
          </span>
        </button>
      </div>
    </template>

    <!-- 历史会话列表视图（对齐平台助手 AssistantHistoryView） -->
    <div
      v-if="activeView === 'history'"
      class="flex flex-col h-full bg-white dark:bg-dark-900"
    >
      <div
        class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-800"
      >
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-600 dark:text-dark-400 dark:hover:text-emerald-400 font-medium transition cursor-pointer"
            @click="activeView = 'chat'"
          >
            <BaseIcon name="chevron-left" class="w-4 h-4" />
            返回对话
          </button>
          <span class="text-gray-300 dark:text-dark-700">|</span>
          <span
            class="text-xs font-bold text-gray-900 dark:text-white flex items-center gap-1.5"
          >
            <BaseIcon name="threads" class="w-3.5 h-3.5 text-emerald-500" />
            历史会话
          </span>
        </div>

        <BaseButton
          variant="primary"
          size="sm"
          class="text-xs py-1 px-2.5 h-auto"
          @click="handleNewSession"
        >
          <BaseIcon name="plus" class="w-3.5 h-3.5 mr-1" />
          开启新会话
        </BaseButton>
      </div>

      <div class="flex-1 overflow-y-auto p-3 space-y-2">
        <div v-if="chat.loadingThreads.value" class="space-y-2 py-4">
          <div
            v-for="i in 4"
            :key="i"
            class="h-14 bg-gray-100 dark:bg-dark-800 rounded-xl animate-pulse"
          />
        </div>

        <div
          v-else-if="chat.threads.value.length === 0"
          class="flex flex-col items-center justify-center py-16 text-center text-gray-400 space-y-2"
        >
          <BaseIcon
            name="chat"
            class="w-10 h-10 text-gray-300 dark:text-dark-700"
          />
          <p class="text-xs font-medium text-gray-600 dark:text-dark-400">
            暂无历史对话记录
          </p>
          <p class="text-[11px] text-gray-400">
            发送首条消息后，系统会自动保存本专家会话记录。
          </p>
        </div>

        <div
          v-for="t in chat.threads.value"
          :key="t.thread_id"
          data-testid="expert-history-item"
          class="group flex flex-col p-3 rounded-xl border border-gray-200/80 dark:border-dark-800 bg-white dark:bg-dark-900 hover:border-emerald-300 dark:hover:border-emerald-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-950/20 cursor-pointer transition"
          :class="{
            'border-emerald-500! bg-emerald-50/60 dark:bg-emerald-950/40':
              chat.threadId.value === t.thread_id,
          }"
          @click="handleSelectHistoryThread(t.thread_id)"
        >
          <div class="flex items-center justify-between gap-2 text-xs">
            <span
              class="font-bold text-gray-900 dark:text-white truncate max-w-[340px]"
            >
              {{ t.title }}
            </span>
            <span class="text-[10px] text-gray-400 shrink-0">
              {{
                t.updated_at ? new Date(t.updated_at).toLocaleDateString() : ""
              }}
            </span>
          </div>
          <div
            class="mt-1 flex items-center justify-between text-[11px] text-gray-400 font-mono"
          >
            <span class="truncate">ID: {{ t.thread_id.slice(0, 12) }}...</span>
            <span
              class="text-[10px] text-emerald-600 dark:text-emerald-400 group-hover:underline"
            >
              进入对话 →
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 主对话视图 -->
    <div v-else class="flex flex-col h-full bg-white dark:bg-dark-900">
      <!-- 试跑状态横幅 -->
      <div
        v-if="chat.activeTrialRunId.value"
        class="mx-4 mt-3 flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/60 dark:bg-emerald-950/20 text-xs"
      >
        <div class="flex items-center gap-2">
          <span class="font-mono font-semibold"
            >试跑 #{{ chat.activeTrialRunId.value.slice(0, 8) }}</span
          >
          <StatusPill :tone="trialIsRunning ? 'info' : 'neutral'">
            {{ chat.trialRunStatus.value || "queued" }}
          </StatusPill>
          <span v-if="chat.trialRunSummary.value" class="text-gray-500">
            {{ chat.trialRunSummary.value }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <BaseButton
            v-if="trialIsRunning"
            size="sm"
            variant="danger"
            @click="chat.abortActiveTrialRun()"
          >
            终止当前评测
          </BaseButton>
          <BaseButton
            v-if="trialFinished"
            size="sm"
            variant="primary"
            :disabled="chat.streaming.value"
            @click="
              submitPrompt(
                `试跑 run_id=${chat.activeTrialRunId.value} 已结束（状态：${chat.trialRunStatus.value}），请调用 get_run_progress_and_evidence 分析结果；若因 Case 写法瑕疵失败请提出修复。`,
              )
            "
          >
            让专家查看结果
          </BaseButton>
        </div>
      </div>

      <div v-if="chat.error.value" class="px-4 pt-3">
        <StateBanner
          variant="danger"
          title="专家对话执行异常"
          :description="chat.error.value"
        />
      </div>

      <!-- 消息流区域 -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-4">
        <!-- 空态欢迎页 -->
        <div
          v-if="chat.messages.value.length === 0"
          class="flex flex-col items-center justify-center h-full py-6 text-center text-gray-400 dark:text-dark-500 space-y-3"
        >
          <div class="relative w-24 h-24 mx-auto -mb-1 select-none">
            <img
              :src="avatarSrc"
              :alt="title"
              class="w-full h-full object-contain drop-shadow-md"
            />
          </div>

          <div class="space-y-1">
            <h3 class="text-sm font-bold text-gray-800 dark:text-dark-100">
              你好！我是{{ isCopilot ? " AI 出题专家" : " AI 白盒诊断专家" }} 👋
            </h3>
            <p
              class="text-xs max-w-sm text-gray-500 dark:text-dark-400 leading-relaxed mx-auto"
            >
              {{
                isCopilot
                  ? "支持上传参考资料、设计多轮博弈考题、入库草稿并一键试跑闭环修复。"
                  : "按三层归因排查失败证据、分析性能瓶颈并给出可落地改造建议。"
              }}
            </p>
          </div>

          <div
            class="w-full max-w-lg pt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-left"
          >
            <button
              v-for="(prompt, idx) in quickPrompts"
              :key="idx"
              type="button"
              class="p-2.5 rounded-xl bg-white dark:bg-dark-900 border border-gray-200/80 dark:border-dark-800 hover:border-emerald-300 dark:hover:border-emerald-700 shadow-2xs hover:shadow-xs transition-all text-xs text-gray-700 dark:text-dark-200 flex items-start gap-2.5 group cursor-pointer"
              @click="submitPrompt(prompt.text)"
            >
              <span class="text-sm shrink-0 pt-0.5">{{ prompt.icon }}</span>
              <div class="flex-1 min-w-0">
                <div
                  class="font-medium text-[11px] group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors truncate"
                >
                  {{ prompt.title }}
                </div>
                <div class="text-[10px] text-gray-400 truncate mt-0.5">
                  {{ prompt.desc }}
                </div>
              </div>
            </button>
          </div>
        </div>

        <!-- 消息气泡列表 -->
        <div v-for="msg in chat.messages.value" :key="msg.id" class="w-full">
          <!-- 用户消息 -->
          <div
            v-if="msg.role === 'user'"
            class="flex items-start justify-end gap-2.5 max-w-[88%] ml-auto"
          >
            <div class="flex flex-col items-end space-y-1">
              <span class="text-[10px] text-gray-400 font-medium px-1">我</span>
              <div
                v-if="msg.attachments && msg.attachments.length"
                class="flex flex-wrap justify-end gap-1.5"
              >
                <span
                  v-for="fname in msg.attachments"
                  :key="fname"
                  class="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 text-[11px] font-mono text-emerald-700 dark:text-emerald-300"
                >
                  📎 {{ fname }}
                </span>
              </div>
              <div
                class="rounded-2xl rounded-tr-xs px-3.5 py-2.5 text-xs leading-relaxed bg-emerald-600 text-white shadow-xs whitespace-pre-wrap break-words"
              >
                {{ msg.content }}
              </div>
            </div>
            <div
              class="w-8 h-8 rounded-full shrink-0 overflow-hidden ring-1 ring-white/80 dark:ring-dark-800 shadow-xs select-none bg-emerald-100 dark:bg-emerald-950 flex items-center justify-center text-[11px] font-bold text-emerald-700 dark:text-emerald-300"
              title="我"
            >
              <img
                v-if="userAvatarUrl"
                :src="userAvatarUrl"
                alt="我"
                class="w-full h-full object-cover"
              />
              <span v-else>我</span>
            </div>
          </div>

          <!-- 专家消息 -->
          <div v-else class="flex items-start gap-2.5 max-w-[94%]">
            <div
              class="w-8 h-8 rounded-full shrink-0 p-0.5 bg-gradient-to-tr from-emerald-100 via-teal-100 to-sky-100 dark:from-emerald-950 dark:to-teal-950 flex items-center justify-center shadow-xs ring-1 ring-emerald-300/40 dark:ring-emerald-500/20 select-none overflow-hidden"
              :title="title"
            >
              <img
                :src="avatarSrc"
                :alt="title"
                class="w-full h-full object-contain scale-105"
              />
            </div>

            <div class="flex flex-col space-y-1 flex-1 min-w-0">
              <div class="flex items-center gap-1.5 px-1">
                <span
                  class="text-[10px] text-gray-500 dark:text-dark-400 font-semibold"
                  >{{ title }}</span
                >
                <span
                  class="inline-flex items-center px-1 rounded text-[9px] font-mono bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  >AI</span
                >
              </div>

              <div
                v-if="msg.content"
                class="rounded-2xl rounded-tl-xs px-4 py-3 text-xs leading-relaxed bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 text-gray-800 dark:text-dark-100 shadow-2xs break-words overflow-x-auto"
              >
                <MarkdownContent :content="msg.content" />
              </div>

              <div
                v-else
                class="rounded-2xl rounded-tl-xs px-3.5 py-2.5 text-xs bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 shadow-2xs inline-flex items-center gap-2 self-start"
              >
                <div class="flex items-center gap-1 py-0.5">
                  <span
                    class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-bounce"
                    style="animation-delay: 0ms"
                  />
                  <span
                    class="w-1.5 h-1.5 rounded-full bg-teal-500 animate-bounce"
                    style="animation-delay: 150ms"
                  />
                  <span
                    class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-bounce"
                    style="animation-delay: 300ms"
                  />
                </div>
                <span
                  class="text-[11px] text-gray-400 dark:text-dark-400 font-medium"
                  >正在读取规范/资料并调用工具处理...</span
                >
              </div>

              <div
                v-if="msg.candidates && msg.candidates.length > 0"
                class="mt-1.5 px-3 py-2 rounded-xl border border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/50 dark:bg-emerald-950/20 flex items-center justify-between gap-2 text-xs"
              >
                <span
                  class="font-semibold text-emerald-700 dark:text-emerald-400"
                >
                  识别到 {{ msg.candidates.length }} 道候选考题
                </span>
                <BaseButton
                  size="sm"
                  variant="primary"
                  @click="emit('adoptCases', msg.candidates!)"
                >
                  一键写入当前题库草稿
                </BaseButton>
              </div>
            </div>
          </div>
        </div>

        <!-- HITL 审批卡片 -->
        <div
          v-if="chat.pendingInterrupts.value.length > 0"
          class="p-3 rounded-xl border-2 border-amber-400/80 dark:border-amber-600 bg-amber-50/70 dark:bg-amber-950/25 space-y-2 text-xs"
        >
          <div class="font-semibold text-amber-800 dark:text-amber-300">
            需要你的授权确认（HITL）
          </div>
          <div
            v-for="item in chat.pendingInterrupts.value"
            :key="item.id"
            class="space-y-1 text-[11px] text-gray-700 dark:text-dark-200"
          >
            <div>
              操作工具：<span class="font-mono font-semibold">{{
                item.actionName
              }}</span>
            </div>
            <div>{{ item.description }}</div>
            <pre
              class="p-2 rounded bg-white/80 dark:bg-dark-900 border border-amber-200 dark:border-dark-700 overflow-x-auto text-[11px]"
              >{{ item.argsSummary }}</pre
            >
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <BaseButton
              size="sm"
              variant="secondary"
              :disabled="chat.streaming.value"
              @click="chat.respondInterrupt('reject')"
            >
              拒绝
            </BaseButton>
            <BaseButton
              size="sm"
              variant="primary"
              :disabled="chat.streaming.value"
              @click="chat.respondInterrupt('approve')"
            >
              允许执行
            </BaseButton>
          </div>
        </div>
      </div>

      <!-- 底部输入与模型选择区 -->
      <div
        class="px-4 py-3 border-t border-gray-100 dark:border-dark-800 bg-gray-50/60 dark:bg-dark-900/90 space-y-2"
      >
        <div
          v-if="
            chat.pendingFiles.value.length > 0 ||
            chat.uploadedMaterials.value.length > 0
          "
          class="flex flex-wrap gap-1.5 text-[11px]"
        >
          <span
            v-for="f in chat.pendingFiles.value"
            :key="`pending-${f.name}`"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
          >
            待发: {{ f.name }}
            <button
              type="button"
              class="hover:text-red-500 ml-0.5 cursor-pointer"
              @click="chat.removePendingFile(f.name)"
            >
              ×
            </button>
          </span>
          <span
            v-for="u in chat.uploadedMaterials.value"
            :key="`uploaded-${u.path}`"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-800 text-gray-600 dark:text-dark-300"
          >
            已传: {{ u.fileName }}
          </span>
        </div>

        <div class="flex items-center gap-2">
          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept=".txt,.md,.csv,.json,.pdf,.docx,.yaml,.yml"
            class="hidden"
            @change="handleFileChange"
          />
          <BaseButton
            v-if="isCopilot"
            size="sm"
            variant="secondary"
            :disabled="
              chat.streaming.value || chat.pendingInterrupts.value.length > 0
            "
            @click="triggerFilePicker"
          >
            + 资料
          </BaseButton>
          <div class="flex-1">
            <BaseInput
              v-model="inputDraft"
              :disabled="chat.pendingInterrupts.value.length > 0"
              :placeholder="
                chat.pendingInterrupts.value.length > 0
                  ? '请先在上方点击「允许执行」或「拒绝」完成授权...'
                  : '输入需求、上传参考资料或排障追问，回车发送...'
              "
              @keyup.enter="submitPrompt()"
            />
          </div>
          <BaseButton
            variant="primary"
            :disabled="
              chat.streaming.value ||
              chat.pendingInterrupts.value.length > 0 ||
              !inputDraft.trim()
            "
            @click="submitPrompt()"
          >
            {{ chat.streaming.value ? "执行中..." : "发送" }}
          </BaseButton>
        </div>

        <!-- 底部工具栏：直接复用 ChatModelSelector -->
        <div class="flex items-center justify-between gap-2 pt-0.5">
          <ChatModelSelector
            v-if="selectorModels.length > 0"
            v-model:selected-model-id="selectedModelId"
            :models="selectorModels"
            :default-model-id="defaultModelId"
            :project-id="projectId"
            :disabled="chat.streaming.value"
          />
          <span v-else class="text-[11px] text-gray-400">
            未检测到可用模型
          </span>
          <span class="text-[10px] text-gray-400 hidden sm:inline">
            支持左边缘拖拽拉伸或点击右上角「宽屏」
          </span>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>
