<script setup lang="ts">
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import AssistantChatView from "./AssistantChatView.vue";
import AssistantHistoryView from "./AssistantHistoryView.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const store = usePlatformAssistantStore();

function handleClose() {
  store.close();
}

function toggleView() {
  if (store.activeView === "chat") {
    store.switchView("history");
  } else {
    store.switchView("chat");
  }
}
</script>

<template>
  <BaseDrawer
    :show="store.isOpen"
    title="平台助手"
    width="wide"
    flush
    @close="handleClose"
  >
    <template #title>
      <div class="flex items-center gap-2">
        <div
          class="w-7 h-7 rounded-lg bg-sky-100 dark:bg-sky-950/80 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold text-xs shrink-0"
        >
          <BaseIcon name="sparkle" class="w-4 h-4" />
        </div>
        <div class="truncate">
          <h2 class="text-xs font-bold text-gray-900 dark:text-white truncate">
            平台助手
          </h2>
          <p class="text-[10px] text-gray-400 truncate">
            智能排障 · 架构指导 · 只读数据分析
          </p>
        </div>
      </div>
    </template>

    <template #header-actions>
      <!-- 切换 历史 / 对话 按钮 -->
      <button
        type="button"
        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 dark:border-dark-700 hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-700 dark:text-dark-200 transition cursor-pointer"
        :title="
          store.activeView === 'chat' ? '查看历史对话列表' : '返回当前对话'
        "
        @click="toggleView"
      >
        <BaseIcon
          :name="store.activeView === 'chat' ? 'threads' : 'chat'"
          class="w-3.5 h-3.5 text-sky-500"
        />
        <span>{{ store.activeView === "chat" ? "历史会话" : "返回对话" }}</span>
      </button>
    </template>

    <!-- 抽屉内容区 (双视图平滑切换) -->
    <div class="h-full flex flex-col">
      <AssistantChatView v-if="store.activeView === 'chat'" />
      <AssistantHistoryView v-else />
    </div>
  </BaseDrawer>
</template>
