<script setup lang="ts">
import { ref } from "vue";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import TrajectoryView from "../src/modules/chat/components/trajectory/TrajectoryView.vue";
import RuntimeModelEditor from "../src/modules/runtime/components/RuntimeModelEditor.vue";
import RuntimeModelDetailDialog from "../src/modules/runtime/components/RuntimeModelDetailDialog.vue";
import type { StoredRuntimeModel } from "../src/types/management";

const currentTab = ref<"trajectory" | "editor" | "dialog">("trajectory");

const messages = ref([
  new HumanMessage({ id: "h1", content: "请帮我分析一下财务报表" }),
  new AIMessage({
    id: "a1",
    content: "正在为您调取模型进行推理计算...",
    response_metadata: {
      token_usage: {
        input_tokens: 1200,
        output_tokens: 350,
      },
    },
  }),
]);

const runs = ref([
  {
    run_id: "run-demo-1",
    status: "completed",
    created_at: "2026-10-08T10:00:00Z",
  },
  {
    run_id: "run-demo-2",
    status: "completed",
    created_at: "2026-10-08T10:05:00Z",
  },
]);

const selectedRunId = ref("run-demo-1");

const mockEditingModel: StoredRuntimeModel = {
  id: "model-record-1",
  model: "claude-3-5-sonnet",
  display_name: "Claude 3.5 Sonnet (Prod)",
  provider: "anthropic",
  base_url: "https://api.anthropic.com",
  protocol: "anthropic",
  credential_configured: true,
  scope_type: "platform",
  enabled: true,
  pricing: {
    currency: "USD",
    basis: "per_million_tokens",
    input: "3.0000000000",
    output: "15.0000000000",
    cache_read: "0.3000000000",
    cache_write: "3.7500000000",
    cache_write_5m: "3.7500000000",
    cache_write_1h: "6.0000000000",
    version: "v-sample-uuid-1",
    source: "configured_catalog",
    updated_at: "2026-10-08T08:00:00Z",
  },
};

const showDetailDialog = ref(false);

function handleSelectRun(runId: string) {
  selectedRunId.value = runId;
}
</script>

<template>
  <div
    class="h-screen w-screen flex flex-col font-sans bg-gray-50 text-gray-900 dark:bg-dark-950 dark:text-gray-100"
  >
    <!-- E2E 控制栏 -->
    <header
      class="h-10 border-b border-gray-200 bg-white px-4 flex items-center justify-between dark:border-dark-800 dark:bg-dark-900 shrink-0 select-none"
    >
      <div class="flex items-center gap-2">
        <span class="font-bold text-xs text-blue-600 dark:text-blue-400"
          >Agent Usage E2E Fixture</span
        >
      </div>
      <div class="flex items-center gap-2">
        <button
          type="button"
          data-testid="tab-trajectory-btn"
          class="px-2.5 py-1 text-xs rounded border transition-colors"
          :class="
            currentTab === 'trajectory'
              ? 'bg-blue-50 text-blue-700 border-blue-200 font-semibold dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900'
              : 'bg-white border-gray-200 text-gray-600 dark:bg-dark-800 dark:border-dark-700 dark:text-gray-300'
          "
          @click="currentTab = 'trajectory'"
        >
          轨迹与用量 (Trajectory & Usage)
        </button>
        <button
          type="button"
          data-testid="tab-editor-btn"
          class="px-2.5 py-1 text-xs rounded border transition-colors"
          :class="
            currentTab === 'editor'
              ? 'bg-blue-50 text-blue-700 border-blue-200 font-semibold dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900'
              : 'bg-white border-gray-200 text-gray-600 dark:bg-dark-800 dark:border-dark-700 dark:text-gray-300'
          "
          @click="currentTab = 'editor'"
        >
          价格配置表单 (Model Pricing Editor)
        </button>
        <button
          type="button"
          data-testid="tab-dialog-btn"
          class="px-2.5 py-1 text-xs rounded border transition-colors"
          :class="
            currentTab === 'dialog'
              ? 'bg-blue-50 text-blue-700 border-blue-200 font-semibold dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900'
              : 'bg-white border-gray-200 text-gray-600 dark:bg-dark-800 dark:border-dark-700 dark:text-gray-300'
          "
          @click="
            currentTab = 'dialog';
            showDetailDialog = true;
          "
        >
          价格详情弹窗 (Model Detail Dialog)
        </button>
      </div>
    </header>

    <!-- 主展示区 -->
    <main class="flex-1 min-h-0 overflow-hidden relative">
      <!-- 1. TrajectoryView -->
      <div v-show="currentTab === 'trajectory'" class="h-full w-full">
        <TrajectoryView
          :messages="messages"
          :calls="[]"
          :is-running="false"
          project-id="project-demo-1"
          thread-id="thread-demo-1"
          :run-id="selectedRunId"
          :runs="runs"
          :can-read="true"
          run-status="completed"
          @select-run="handleSelectRun"
        />
      </div>

      <!-- 2. Model Pricing Editor -->
      <div
        v-if="currentTab === 'editor'"
        class="h-full w-full overflow-y-auto p-6 max-w-4xl mx-auto"
      >
        <RuntimeModelEditor
          :editing-model="mockEditingModel"
          initial-mode="edit"
        />
      </div>

      <!-- 3. Model Detail Dialog -->
      <div v-if="currentTab === 'dialog'" class="p-6">
        <button
          type="button"
          class="px-3 py-1.5 text-xs bg-blue-600 text-white rounded"
          @click="showDetailDialog = true"
        >
          重新打开详情弹窗
        </button>
        <RuntimeModelDetailDialog
          :show="showDetailDialog"
          :model="mockEditingModel"
          @close="showDetailDialog = false"
        />
      </div>
    </main>
  </div>
</template>
