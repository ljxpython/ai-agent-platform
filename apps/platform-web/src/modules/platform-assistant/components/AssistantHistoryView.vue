<script setup lang="ts">
import { onMounted, ref } from "vue";
import type { AssistantThreadSummary } from "../types";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { createAssistantScopedClient } from "../services/client";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const store = usePlatformAssistantStore();

const threads = ref<AssistantThreadSummary[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

async function fetchHistory() {
  if (!store.boundProjectId) {
    try {
      await store.ensureBootstrap();
    } catch {
      return;
    }
  }

  loading.value = true;
  error.value = null;
  try {
    const client = createAssistantScopedClient(store.boundProjectId);
    const result = await client.threads.search({
      limit: 30,
      offset: 0,
      sortBy: "updated_at",
      sortOrder: "desc",
      metadata: {
        graph_id: "platform_assistant",
      },
    });

    const list: AssistantThreadSummary[] = [];
    if (Array.isArray(result)) {
      for (const item of result) {
        if (!item || typeof item !== "object") continue;
        const meta = (item.metadata || {}) as Record<string, unknown>;
        list.push({
          thread_id: item.thread_id,
          title: typeof meta.title === "string" ? meta.title : "平台助手",
          created_at: item.created_at || "",
          updated_at: item.updated_at || "",
        });
      }
    }
    threads.value = list;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "获取历史会话失败";
  } finally {
    loading.value = false;
  }
}

function handleSelectThread(threadId: string) {
  store.setActiveThreadId(threadId);
}

function handleNewSession() {
  store.newSession();
}

onMounted(() => {
  void fetchHistory();
});
</script>

<template>
  <div class="flex flex-col h-full bg-white dark:bg-dark-900">
    <!-- 顶栏操作区 -->
    <div
      class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-800"
    >
      <span
        class="text-xs font-bold text-gray-900 dark:text-white flex items-center gap-1.5"
      >
        <BaseIcon name="threads" class="w-4 h-4 text-sky-500" />
        历史对话列表
      </span>

      <BaseButton
        variant="primary"
        size="sm"
        class="bg-sky-600 hover:bg-sky-700 text-white text-xs py-1 px-2.5 h-auto"
        @click="handleNewSession"
      >
        <BaseIcon name="plus" class="w-3.5 h-3.5 mr-1" />
        开启新会话
      </BaseButton>
    </div>

    <!-- 列表内容 -->
    <div class="flex-1 overflow-y-auto p-3 space-y-2">
      <!-- 骨架屏 -->
      <div v-if="loading" class="space-y-2 py-4">
        <div
          v-for="i in 4"
          :key="i"
          class="h-14 bg-gray-100 dark:bg-dark-800 rounded-xl animate-pulse"
        />
      </div>

      <!-- 错误提示 -->
      <div
        v-else-if="error"
        class="p-4 text-center text-xs text-red-600 dark:text-red-400 space-y-2"
      >
        <p>{{ error }}</p>
        <BaseButton variant="secondary" size="sm" @click="fetchHistory">
          重试
        </BaseButton>
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="threads.length === 0"
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
          开启新会话，助手会自动保留会话记录与只读审计事实。
        </p>
      </div>

      <!-- 会话卡片列表 -->
      <div
        v-for="t in threads"
        :key="t.thread_id"
        class="group flex flex-col p-3 rounded-xl border border-gray-200/80 dark:border-dark-800 bg-white dark:bg-dark-900 hover:border-sky-300 dark:hover:border-sky-800 hover:bg-sky-50/40 dark:hover:bg-sky-950/20 cursor-pointer transition"
        :class="{
          'border-sky-500! bg-sky-50/60 dark:bg-sky-950/40':
            store.activeThreadId === t.thread_id,
        }"
        @click="handleSelectThread(t.thread_id)"
      >
        <div class="flex items-center justify-between text-xs">
          <span
            class="font-bold text-gray-900 dark:text-white truncate max-w-[280px]"
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
            class="text-[10px] text-sky-600 dark:text-sky-400 group-hover:underline"
          >
            进入对话 →
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
