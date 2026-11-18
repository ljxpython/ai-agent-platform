<script setup lang="ts">
import { ref, watch } from "vue";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { usePlatformAssistantSession } from "../composables/usePlatformAssistantSession";
import AssistantChatView from "./AssistantChatView.vue";
import AssistantHistoryView from "./AssistantHistoryView.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const store = usePlatformAssistantStore();
const session = usePlatformAssistantSession();

const DEFAULT_DRAWER_WIDTH = 580;
const EXPANDED_DRAWER_WIDTH = 960;

const savedWidth =
  typeof window !== "undefined"
    ? Number(localStorage.getItem("pw_assistant_drawer_width"))
    : null;
const drawerWidth = ref<number>(
  savedWidth && savedWidth >= 420 ? savedWidth : DEFAULT_DRAWER_WIDTH,
);

watch(drawerWidth, (newW) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("pw_assistant_drawer_width", String(newW));
  }
});

function toggleExpandedWidth() {
  if (drawerWidth.value >= 800) {
    drawerWidth.value = DEFAULT_DRAWER_WIDTH;
  } else {
    drawerWidth.value = EXPANDED_DRAWER_WIDTH;
  }
}

function handleClose() {
  store.close();
}

function handleNewSession() {
  session.startNewSession();
  store.switchView("chat");
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
    :resizable="true"
    :custom-width="drawerWidth"
    :min-width="420"
    flush
    @close="handleClose"
    @update:custom-width="drawerWidth = $event"
  >
    <template #title>
      <div class="flex items-center gap-2.5">
        <div class="relative w-7 h-7 shrink-0">
          <img
            src="/assistant-mascot.gif"
            alt="平台助手"
            class="w-full h-full object-contain drop-shadow-xs"
          />
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
      <div class="flex items-center gap-1.5">
        <!-- 切换 宽屏 / 标准 按钮 -->
        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 dark:border-dark-700 hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-700 dark:text-dark-200 transition cursor-pointer"
          :title="
            drawerWidth >= 800
              ? '收起为标准宽度 (580px)'
              : '展开为宽屏模式 (960px)'
          "
          data-testid="assistant-toggle-width-btn"
          @click="toggleExpandedWidth"
        >
          <BaseIcon
            :name="drawerWidth >= 800 ? 'minimize' : 'maximize'"
            class="w-3.5 h-3.5 text-sky-500"
          />
          <span class="hidden sm:inline">{{
            drawerWidth >= 800 ? "标准" : "宽屏"
          }}</span>
        </button>

        <!-- 开启新会话按钮 -->
        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-sky-50 hover:bg-sky-100 dark:bg-sky-950/80 dark:hover:bg-sky-900 border border-sky-200 dark:border-sky-800 text-sky-700 dark:text-sky-300 transition cursor-pointer"
          title="重置并开启全新会话"
          data-testid="assistant-new-thread-btn"
          @click="handleNewSession"
        >
          <BaseIcon
            name="plus"
            class="w-3.5 h-3.5 text-sky-600 dark:text-sky-400"
          />
          <span>新会话</span>
        </button>

        <!-- 切换 历史 / 对话 按钮 -->
        <button
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 dark:border-dark-700 hover:bg-gray-100 dark:hover:bg-dark-800 text-gray-700 dark:text-dark-200 transition cursor-pointer"
          :title="
            store.activeView === 'chat' ? '查看历史对话列表' : '返回当前对话'
          "
          data-testid="assistant-history-btn"
          @click="toggleView"
        >
          <BaseIcon
            :name="store.activeView === 'chat' ? 'threads' : 'chat'"
            class="w-3.5 h-3.5 text-sky-500"
          />
          <span>{{
            store.activeView === "chat" ? "历史会话" : "返回对话"
          }}</span>
        </button>
      </div>
    </template>

    <!-- 抽屉内容区 (双视图平滑切换) -->
    <div class="h-full flex flex-col">
      <AssistantChatView v-if="store.activeView === 'chat'" />
      <AssistantHistoryView v-else />
    </div>
  </BaseDrawer>
</template>
