<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { usePlatformAssistantSession } from "../composables/usePlatformAssistantSession";
import AssistantComposer from "./AssistantComposer.vue";
import AssistantContextPill from "./AssistantContextPill.vue";
import AssistantApprovalCard from "./AssistantApprovalCard.vue";
import EvidenceDetailDrawer from "./EvidenceDetailDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { renderMarkdown } from "@/utils/markdown";

const store = usePlatformAssistantStore();
const session = usePlatformAssistantSession();

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
    } else {
      session.startNewSession();
    }
  },
  { immediate: true },
);

function handleSendMessage(text: string) {
  const ctx = store.attachedContext;
  void session.sendMessage(text, ctx);
  // 发送后自动清除已挂载的上下文
  if (ctx) {
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
    <!-- 顶部状态栏: 项目作用域锁 Tag & 历史/新建按钮 -->
    <div
      class="flex items-center justify-between px-4 py-2 bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-dark-800 text-xs shrink-0"
    >
      <div class="flex items-center gap-2">
        <span
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border"
          :class="
            store.isPersonalProject
              ? 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800'
              : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800'
          "
        >
          <BaseIcon
            :name="store.isPersonalProject ? 'user' : 'branch'"
            class="w-3 h-3"
          />
          {{
            store.isPersonalProject ? "个人助手作用域" : "业务项目安全作用域"
          }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-1 text-[11px] text-gray-500 hover:text-sky-600 dark:text-dark-400 dark:hover:text-sky-400 font-medium transition cursor-pointer"
          @click="store.switchView('history')"
        >
          <BaseIcon name="threads" class="w-3.5 h-3.5" />
          历史会话
        </button>
        <span class="text-gray-300 dark:text-dark-700">|</span>
        <button
          type="button"
          class="inline-flex items-center gap-1 text-[11px] text-gray-500 hover:text-sky-600 dark:text-dark-400 dark:hover:text-sky-400 font-medium transition cursor-pointer"
          @click="session.startNewSession"
        >
          <BaseIcon name="plus" class="w-3.5 h-3.5" />
          开启新会话
        </button>
      </div>
    </div>

    <!-- 错误横幅提示 -->
    <div
      v-if="session.errorBanner.value"
      class="p-2.5 mx-3 mt-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-300 text-xs flex items-center justify-between"
    >
      <div class="flex items-center gap-2">
        <BaseIcon name="alert" class="w-4 h-4 shrink-0 text-red-500" />
        <span>{{ session.errorBanner.value }}</span>
      </div>
      <button
        type="button"
        class="text-red-500 hover:text-red-700 text-xs font-bold"
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
      <!-- 空白引导 -->
      <div
        v-if="session.messages.value.length === 0"
        class="flex flex-col items-center justify-center h-full py-12 text-center text-gray-400 dark:text-dark-500 space-y-3"
      >
        <div
          class="w-12 h-12 rounded-2xl bg-sky-50 dark:bg-sky-950/60 border border-sky-100 dark:border-sky-900 flex items-center justify-center text-sky-600 dark:text-sky-400"
        >
          <BaseIcon name="sparkle" class="w-6 h-6" />
        </div>
        <p class="text-sm font-semibold text-gray-700 dark:text-dark-200">
          平台内置只读助手
        </p>
        <p
          class="text-xs max-w-xs text-gray-500 dark:text-dark-400 leading-relaxed"
        >
          您可以咨询平台架构与用法、查阅官方操作手册、提供报错信息协助定位诊断、或由助手编写只读
          SQL 检索数据库事实。
        </p>
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
          <!-- 用户头像 -->
          <div
            class="w-8 h-8 rounded-full shrink-0 bg-gradient-to-tr from-sky-500 to-blue-600 flex items-center justify-center text-white shadow-xs ring-1 ring-white/60 dark:ring-dark-800"
            title="我"
          >
            <BaseIcon name="user" class="w-4 h-4" />
          </div>
        </div>

        <!-- 2. 平台助手消息 (左侧靠齐，带超可爱的助手小机器人头像与流式气泡) -->
        <div
          v-else-if="msg.role === 'assistant'"
          class="flex items-start gap-2.5 max-w-[92%]"
        >
          <!-- 可爱的助手小机器人头像 -->
          <div
            class="w-8 h-8 rounded-full shrink-0 bg-gradient-to-tr from-sky-400 via-indigo-500 to-purple-500 p-1 flex items-center justify-center shadow-xs ring-1 ring-sky-300/40 dark:ring-sky-500/20 select-none"
            title="平台助手小精灵"
          >
            <svg
              viewBox="0 0 36 36"
              fill="none"
              class="w-full h-full text-white drop-shadow-xs"
              xmlns="http://www.w3.org/2000/svg"
            >
              <!-- 顶部天线与红宝石 -->
              <line
                x1="18"
                y1="5"
                x2="18"
                y2="9"
                stroke="white"
                stroke-width="2"
                stroke-linecap="round"
              />
              <circle cx="18" cy="4" r="2.2" fill="#F43F5E" />
              <!-- 机器人脸部圆角 -->
              <rect
                x="5"
                y="9"
                width="26"
                height="20"
                rx="7"
                fill="white"
                fill-opacity="0.95"
              />
              <!-- 两侧可爱耳机 -->
              <rect
                x="2.5"
                y="15"
                width="3"
                height="8"
                rx="1.5"
                fill="#38BDF8"
              />
              <rect
                x="30.5"
                y="15"
                width="3"
                height="8"
                rx="1.5"
                fill="#A855F7"
              />
              <!-- 萌萌大眼睛 -->
              <circle cx="13" cy="18" r="3.2" fill="#0284C7" />
              <circle cx="14.2" cy="17" r="1.1" fill="white" />
              <circle cx="23" cy="18" r="3.2" fill="#0284C7" />
              <circle cx="24.2" cy="17" r="1.1" fill="white" />
              <!-- 微笑小弧线 -->
              <path
                d="M15.5 23.5C16.8 24.8 19.2 24.8 20.5 23.5"
                stroke="#0284C7"
                stroke-width="1.6"
                stroke-linecap="round"
              />
              <!-- 腮红 -->
              <circle
                cx="9"
                cy="21"
                r="1.6"
                fill="#FDA4AF"
                fill-opacity="0.9"
              />
              <circle
                cx="27"
                cy="21"
                r="1.6"
                fill="#FDA4AF"
                fill-opacity="0.9"
              />
            </svg>
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
      :disabled="session.turnStatus.value === 'awaiting_review'"
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
