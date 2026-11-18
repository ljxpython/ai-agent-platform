<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { usePlatformAssistantSession } from "../composables/usePlatformAssistantSession";
import { useAuthStore } from "@/stores/auth";
import AssistantComposer from "./AssistantComposer.vue";
import AssistantContextPill from "./AssistantContextPill.vue";
import AssistantApprovalCard from "./AssistantApprovalCard.vue";
import EvidenceDetailDrawer from "./EvidenceDetailDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { renderMarkdown } from "@/utils/markdown";

const store = usePlatformAssistantStore();
const session = usePlatformAssistantSession();
const authStore = useAuthStore();

const messagesContainer = ref<HTMLElement | null>(null);

const hasActiveAssistantMessage = computed(() => {
  const list = session.messages.value;
  return list.some((m) => m.role === "assistant");
});

// 自动滚动到底部
function scrollToBottom() {
  void nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

// 监听消息条数与最新内容长度变动，打字机实时滚动跟随
watch(
  () => {
    const list = session.messages.value;
    const last = list[list.length - 1];
    return [list.length, last?.content?.length || 0];
  },
  () => scrollToBottom(),
);

// 监听当前激活的 threadId 变化自动加载
watch(
  () => store.activeThreadId,
  (newId) => {
    if (newId) {
      if (newId !== session.threadId.value) {
        void session.loadThread(newId);
      }
    } else if (session.threadId.value) {
      session.startNewSession();
    }
  },
  { immediate: true },
);

async function handleSendMessage(text: string) {
  if (store.loading) return;
  if (["running", "awaiting_review"].includes(session.turnStatus.value)) return;
  const ctx = store.attachedContext;
  await session.sendMessage(text, ctx);
  if (
    ctx &&
    store.attachedContext === ctx &&
    ["idle", "awaiting_review"].includes(session.turnStatus.value)
  ) {
    store.clearAttachedContext();
  }
}

function handleDecision(decision: "approve" | "reject") {
  void session.submitReview(decision);
}

/**
 * 将答复 Markdown 转换为标准 HTML，支持 Markdown 表格、加粗、列表、代码块，
 * 并将 [证据:UUID] 正则转换为带 data-evidence-id 属性的交互式按钮 HTML
 */
function renderMessageHtml(content: string): string {
  if (!content) return "";
  // 1. 使用平台标准 markdown-it 渲染（自带 table 响应式封装与代码高亮）
  const rendered = renderMarkdown(content);

  // 2. 将 [证据:UUID] 转换为交互 Badge
  return rendered.replace(
    /\[证据:([a-f0-9-]{36})\]/g,
    (_, id: string) =>
      `<button type="button" class="assistant-evidence-badge inline-flex items-center gap-1 px-1.5 py-0.5 mx-1 rounded text-[11px] font-mono font-bold bg-sky-50 hover:bg-sky-100 dark:bg-sky-950/80 dark:hover:bg-sky-900 border border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 cursor-pointer transition select-none" data-evidence-id="${id}" title="查看该证据的真实只读事实">📎 证据:${id.slice(0, 8)}</button>`,
  );
}

/**
 * 欢迎页面的快捷引导提示
 */
const quickPrompts = [
  {
    icon: "🔍",
    title: "排查最近报错",
    desc: "提供 thread_id 或报错信息诊断",
    text: "你能帮我排查一次失败的 Run 报错吗？需要我提供什么信息？",
  },
  {
    icon: "📚",
    title: "平台核心能力",
    desc: "查阅平台使用指南与工具手册",
    text: "平台内置了哪些核心能力和排障工具？",
  },
  {
    icon: "📊",
    title: "探查只读数据",
    desc: "查看当前可查询的只读数据源",
    text: "当前账号有哪些可以执行只读 SQL 查询的数据源？",
  },
  {
    icon: "⚡",
    title: "转为评测集",
    desc: "了解对话沉淀为用例的流程",
    text: "如何把一段业务对话沉淀转化为自动化评测集？",
  },
];

function handleQuickPrompt(text: string) {
  handleSendMessage(text);
}

/**
 * 事件委托：捕获消息气泡内点击的证据 Badge
 */
function handleMessageClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  const badge = target?.closest("[data-evidence-id]") as HTMLElement | null;
  if (badge) {
    const evidenceId = badge.getAttribute("data-evidence-id");
    if (evidenceId) {
      session.evidenceLookup.openEvidence(evidenceId);
    }
  }
}

/**
 * 解析并生成工具卡片的摘要信息与命中状态
 */
function getToolCardSummary(evidenceId: string) {
  const ev = session.evidenceLookup.evidenceMap.value.get(evidenceId);
  if (!ev) {
    return {
      name: "内部工具",
      status: "事实已记录",
      isHit: true,
    };
  }

  let name = "内部工具";
  switch (ev.operation) {
    case "documents":
      name = "文档检索";
      break;
    case "source":
      name = "源码快照";
      break;
    case "sql_query":
      name = "数据库查询";
      break;
    case "logs":
      name = "日志排查";
      break;
    case "public_search":
      name = "公开检索";
      break;
  }

  let isHit = true;
  let statusText = "已完成";

  if (ev.operation === "sql_query") {
    const rows = Array.isArray(ev.data?.rows) ? ev.data.rows : [];
    const count = ev.data?.row_count ?? rows.length;
    isHit = count > 0;
    statusText = isHit ? `${count} 行数据` : "0 行记录";
  } else if (["documents", "source", "public_search"].includes(ev.operation)) {
    const sources = Array.isArray(ev.data?.sources) ? ev.data.sources : [];
    isHit = sources.length > 0;
    statusText = isHit ? `命中 ${sources.length} 条` : "未命中 (0匹配)";
  }

  return {
    name,
    status: statusText,
    isHit,
  };
}
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50/50 dark:bg-dark-950/50">
    <!-- 错误横幅提示 -->
    <div
      v-if="session.errorBanner.value"
      class="p-2.5 mx-3 mt-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-300 text-xs flex items-center justify-between"
    >
      <div class="flex min-w-0 items-center gap-2">
        <BaseIcon name="alert" class="w-4 h-4 shrink-0 text-red-500" />
        <span class="min-w-0 break-all">{{ session.errorBanner.value }}</span>
      </div>
      <button
        type="button"
        class="shrink-0 text-red-500 hover:text-red-700 text-xs font-bold"
        @click="session.errorBanner.value = null"
      >
        ✕
      </button>
    </div>

    <!-- 消息流区域 -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto p-4 space-y-4"
      @click="handleMessageClick"
    >
      <!-- 空白引导与快捷提问卡片 -->
      <div
        v-if="session.messages.value.length === 0"
        class="flex flex-col items-center justify-center h-full py-8 text-center text-gray-400 dark:text-dark-500 space-y-3"
      >
        <!-- 可爱 AI 动图大立绘 -->
        <div class="relative w-24 h-24 mx-auto -mb-1 select-none">
          <img
            src="/assistant-mascot.gif"
            alt="平台助手"
            class="w-full h-full object-contain drop-shadow-md"
          />
        </div>

        <div class="space-y-1">
          <h3 class="text-sm font-bold text-gray-800 dark:text-dark-100">
            你好！我是平台助手 👋
          </h3>
          <p
            class="text-xs max-w-xs text-gray-500 dark:text-dark-400 leading-relaxed mx-auto"
          >
            按当前权限读取诊断、用户指南和数据，帮助你排查问题。
          </p>
        </div>

        <!-- 快捷引导提问卡片组 -->
        <div
          class="w-full max-w-md pt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-left"
        >
          <button
            v-for="(prompt, idx) in quickPrompts"
            :key="idx"
            type="button"
            class="p-2.5 rounded-xl bg-white dark:bg-dark-900 border border-gray-200/80 dark:border-dark-800 hover:border-sky-300 dark:hover:border-sky-700 shadow-2xs hover:shadow-xs transition-all text-xs text-gray-700 dark:text-dark-200 flex items-start gap-2.5 group cursor-pointer"
            @click="handleQuickPrompt(prompt.text)"
          >
            <span class="text-sm shrink-0 pt-0.5">{{ prompt.icon }}</span>
            <div class="flex-1 min-w-0">
              <div
                class="font-medium text-[11px] group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors truncate"
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

      <!-- 消息气泡循环 -->
      <div v-for="msg in session.messages.value" :key="msg.id" class="w-full">
        <!-- 1. 用户消息 (右侧靠齐，带用户头像) -->
        <div
          v-if="msg.role === 'user'"
          class="flex items-start justify-end gap-2.5 max-w-[88%] ml-auto"
        >
          <div class="flex flex-col items-end space-y-1">
            <span class="text-[10px] text-gray-400 font-medium px-1">我</span>
            <div
              class="rounded-2xl rounded-tr-xs px-3.5 py-2.5 text-xs leading-relaxed bg-sky-600 text-white shadow-xs whitespace-pre-wrap break-words"
            >
              {{ msg.content }}
            </div>
          </div>
          <!-- 用户头像 (展示高颜值个性化头像) -->
          <div
            class="w-8 h-8 rounded-full shrink-0 overflow-hidden ring-1 ring-white/80 dark:ring-dark-800 shadow-xs select-none bg-sky-100 dark:bg-sky-950"
            title="我"
          >
            <img
              :src="authStore.userAvatar"
              alt="我"
              class="w-full h-full object-cover"
            />
          </div>
        </div>

        <!-- 2. 平台助手消息 (左侧靠齐，带超可爱的助手小机器人头像与流式气泡) -->
        <div
          v-else-if="msg.role === 'assistant'"
          class="flex items-start gap-2.5 max-w-[92%]"
        >
          <!-- 可爱的助手小头像 (使用吉祥物动图) -->
          <div
            class="w-8 h-8 rounded-full shrink-0 p-0.5 bg-gradient-to-tr from-sky-200 via-indigo-200 to-purple-200 dark:from-sky-950 dark:to-purple-950 flex items-center justify-center shadow-xs ring-1 ring-sky-300/40 dark:ring-sky-500/20 select-none overflow-hidden"
            title="平台助手小精灵"
          >
            <img
              src="/assistant-mascot.gif"
              alt="AI"
              class="w-full h-full object-contain scale-110 drop-shadow-xs"
            />
          </div>

          <div class="flex flex-col space-y-1 flex-1 min-w-0">
            <div class="flex items-center gap-1.5 px-1">
              <span
                class="text-[10px] text-gray-500 dark:text-dark-400 font-semibold"
                >平台助手</span
              >
              <span
                class="inline-flex items-center px-1 rounded text-[9px] font-mono bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
                >AI</span
              >
            </div>

            <!-- 如果已有文本内容，展示流式打字气泡 (支持 Markdown 表格与富文本) -->
            <div
              v-if="msg.content"
              class="pw-markdown rounded-2xl rounded-tl-xs px-4 py-3 text-xs leading-relaxed bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 text-gray-800 dark:text-dark-100 shadow-2xs break-words overflow-x-auto"
              v-html="renderMessageHtml(msg.content)"
            />

            <!-- 如果内容尚为空且在运行中，展示跳动的打字思考动画（避免空白扁方框） -->
            <div
              v-else
              class="rounded-2xl rounded-tl-xs px-3.5 py-2.5 text-xs bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 shadow-2xs inline-flex items-center gap-2 self-start"
            >
              <div class="flex items-center gap-1 py-0.5">
                <span
                  class="w-1.5 h-1.5 rounded-full bg-sky-500 animate-bounce"
                  style="animation-delay: 0ms"
                ></span>
                <span
                  class="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce"
                  style="animation-delay: 150ms"
                ></span>
                <span
                  class="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce"
                  style="animation-delay: 300ms"
                ></span>
              </div>
              <span
                class="text-[11px] text-gray-400 dark:text-dark-400 font-medium"
                >小助手思考中...</span
              >
            </div>
          </div>
        </div>

        <!-- 3. 工具执行消息卡片 -->
        <div
          v-else-if="msg.role === 'tool' && msg.evidence_id"
          class="flex items-center gap-2 pl-10 pt-1"
        >
          <div
            class="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-gray-100/90 dark:bg-dark-800/90 border border-gray-200/60 dark:border-dark-700/60 text-[11px] text-gray-600 dark:text-dark-300 font-mono shadow-2xs"
          >
            <span
              class="flex items-center gap-1 font-medium text-gray-700 dark:text-dark-200"
            >
              <span>🛠️</span>
              <span>{{ getToolCardSummary(msg.evidence_id).name }}</span>
            </span>

            <span
              class="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium"
              :class="
                getToolCardSummary(msg.evidence_id).isHit
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/80 dark:text-emerald-300'
                  : 'bg-amber-50 text-amber-700 dark:bg-amber-950/80 dark:text-amber-300'
              "
            >
              {{ getToolCardSummary(msg.evidence_id).status }}
            </span>

            <span class="text-gray-300 dark:text-dark-600">|</span>

            <button
              type="button"
              class="text-sky-600 dark:text-sky-400 font-bold hover:underline cursor-pointer"
              :data-evidence-id="msg.evidence_id"
            >
              查看证据 #{{ msg.evidence_id.slice(0, 8) }}
            </button>
          </div>
        </div>
      </div>

      <!-- 待审批 HITL 卡片 -->
      <div v-if="session.pendingReview.value" class="pt-2">
        <AssistantApprovalCard
          :review="session.pendingReview.value"
          :disabled="session.turnStatus.value === 'running'"
          @decision="handleDecision"
        />
      </div>

      <!-- 运行中指示器 (仅当尚未挂载任何助手气泡时兜底展示) -->
      <div
        v-if="
          session.turnStatus.value === 'running' && !hasActiveAssistantMessage
        "
        class="flex items-center gap-2 text-xs text-sky-600 dark:text-sky-400 py-1"
      >
        <BaseIcon name="refresh" class="w-3.5 h-3.5 animate-spin" />
        <span>正在分析数据并组织回答...</span>
      </div>
    </div>

    <!-- 底部输入栏 Composer -->
    <AssistantComposer
      :is-running="session.turnStatus.value === 'running'"
      :disabled="
        store.loading || session.turnStatus.value === 'awaiting_review'
      "
      @send="handleSendMessage"
      @stop="session.stopCurrentRun"
    >
      <template #context>
        <AssistantContextPill
          v-if="store.hasAttachedContext && store.attachedContext"
          :context="store.attachedContext"
          @remove="store.clearAttachedContext"
        />
      </template>
    </AssistantComposer>

    <!-- 证据二级详情抽屉 -->
    <EvidenceDetailDrawer
      :is-open="session.evidenceLookup.isEvidenceDrawerOpen.value"
      :evidence="session.evidenceLookup.activeEvidence.value"
      @close="session.evidenceLookup.closeEvidence"
    />
  </div>
</template>
