<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { usePlatformAssistantSession } from "../composables/usePlatformAssistantSession";
import AssistantComposer from "./AssistantComposer.vue";
import AssistantContextPill from "./AssistantContextPill.vue";
import AssistantApprovalCard from "./AssistantApprovalCard.vue";
import EvidenceDetailDrawer from "./EvidenceDetailDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const store = usePlatformAssistantStore();
const session = usePlatformAssistantSession();

const messagesContainer = ref<HTMLElement | null>(null);

// 自动滚动到底部
function scrollToBottom() {
  void nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

watch(
  () => session.messages.value.length,
  () => scrollToBottom(),
);

// 监听当前激活的 threadId 变化自动加载
watch(
  () => store.activeThreadId,
  (newId) => {
    if (newId) {
      void session.loadThread(newId);
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
 * 将答复文本中的 [证据:UUID] 正则转换为带 data-evidence-id 属性的交互式按钮 HTML
 */
function renderMessageHtml(content: string): string {
  if (!content) return "";
  // 转义基础 HTML 字符防 XSS
  const escaped = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 将 [证据:UUID] 转换为交互 Badge
  return escaped.replace(
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
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50/50 dark:bg-dark-950/50">
    <!-- 顶部状态栏: 项目作用域锁 Tag & 新建按钮 -->
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
          class="inline-flex items-center gap-1 text-[11px] text-gray-500 hover:text-sky-600 dark:text-dark-400 dark:hover:text-sky-400 font-medium transition"
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
      <div
        v-for="msg in session.messages.value"
        :key="msg.id"
        class="flex flex-col space-y-1"
        :class="msg.role === 'user' ? 'items-end' : 'items-start'"
      >
        <!-- 角色名称微标 -->
        <span class="text-[10px] text-gray-400 font-medium px-1">
          {{ msg.role === "user" ? "我" : "平台助手" }}
        </span>

        <!-- 气泡内容 -->
        <div
          v-if="msg.role === 'user'"
          class="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed bg-sky-600 text-white shadow-xs rounded-tr-xs whitespace-pre-wrap break-words"
        >
          {{ msg.content }}
        </div>

        <div
          v-else-if="msg.role === 'assistant'"
          class="max-w-[90%] rounded-2xl px-4 py-3 text-xs leading-relaxed bg-white dark:bg-dark-900 border border-gray-200/90 dark:border-dark-800 text-gray-800 dark:text-dark-100 shadow-2xs rounded-tl-xs whitespace-pre-wrap break-words"
          v-html="renderMessageHtml(msg.content)"
        />

        <!-- 工具执行消息卡片 (如果存在且未折叠) -->
        <div
          v-else-if="msg.role === 'tool' && msg.evidence_id"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-dark-800 text-[11px] text-gray-600 dark:text-dark-300 font-mono"
        >
          <span>🛠️ 工具已执行 · </span>
          <button
            type="button"
            class="text-sky-600 dark:text-sky-400 font-bold hover:underline"
            :data-evidence-id="msg.evidence_id"
          >
            查看证据 #{{ msg.evidence_id.slice(0, 8) }}
          </button>
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

      <!-- 运行中指示器 -->
      <div
        v-if="session.turnStatus.value === 'running'"
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
