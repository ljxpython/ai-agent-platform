<script setup lang="ts">
import { ref, computed } from "vue";
import ChatAgentStatusBar from "../src/modules/chat/components/ChatAgentStatusBar.vue";
import RunUsage from "../src/modules/chat/components/trajectory/RunUsage.vue";
import { deriveBudgetViewModel } from "../src/modules/chat/budget/view-model";
import type {
  BudgetNotice,
  BudgetSafetyError,
} from "../src/modules/chat/budget/types";
import type { SessionTurnState } from "../src/modules/chat/composables/useChatSession";

// 状态控制
const isRunning = ref(false);
const isInterrupted = ref(false);
const errorMessage = ref<string | undefined>(undefined);
const turnState = ref<SessionTurnState | undefined>(undefined);
const activeNotice = ref<BudgetNotice | null>(null);
const activeSafetyError = ref<BudgetSafetyError | null>(null);
const historicalStopCode = ref<string | null>(null);

// 用户输入与草稿联动
const userInput = ref("原始用户输入：请帮我分析这份超长财报");
const lastActionTriggered = ref<string>("");

// 计算当前 budget view model
const budget = computed(() => {
  return deriveBudgetViewModel(
    activeNotice.value,
    activeSafetyError.value,
    turnState.value || (isRunning.value ? "running" : "idle"),
    historicalStopCode.value as any,
  );
});

// 状态栏动作处理
function handleStatusBarAction(type: "adjust_draft" | "new_thread") {
  lastActionTriggered.value = type;
  if (type === "adjust_draft") {
    userInput.value = "已回填草稿：请帮我分析这份超长财报";
  }
}

function handleStatusBarCancel() {
  lastActionTriggered.value = "cancel";
}

// 用量面板控制
const selectedRunId = ref<string>("run-normal");
const runStatus = ref<string>("completed");

const runsList = ref([
  {
    run_id: "run-normal",
    status: "completed",
    created_at: "2026-10-09T10:00:00Z",
  },
  {
    run_id: "run-exhausted",
    status: "failed",
    created_at: "2026-10-09T10:05:00Z",
  },
  {
    run_id: "run-unverifiable",
    status: "failed",
    created_at: "2026-10-09T10:10:00Z",
  },
  {
    run_id: "run-natural-final",
    status: "completed",
    created_at: "2026-10-09T10:15:00Z",
  },
  {
    run_id: "run-disabled",
    status: "completed",
    created_at: "2026-10-09T10:20:00Z",
  },
]);

function handleSelectRun(runId: string) {
  selectedRunId.value = runId;
}

// 供 Playwright 自动化注入的全局控制函数
(window as any).__tokenBudgetTestController = {
  setRunning(val: boolean) {
    isRunning.value = val;
    turnState.value = val ? "running" : "idle";
  },
  setNotice(notice: BudgetNotice | null) {
    activeNotice.value = notice;
  },
  setSafetyError(error: BudgetSafetyError | null) {
    activeSafetyError.value = error;
    if (error) {
      errorMessage.value = error.message;
      turnState.value = "error";
      isRunning.value = false;
    } else {
      errorMessage.value = undefined;
    }
  },
  setHistoricalStopCode(code: string | null) {
    historicalStopCode.value = code;
    if (code) {
      turnState.value = "error";
      isRunning.value = false;
    }
  },
  setTurnState(state: SessionTurnState | undefined) {
    turnState.value = state;
  },
  reset() {
    isRunning.value = false;
    isInterrupted.value = false;
    errorMessage.value = undefined;
    turnState.value = undefined;
    activeNotice.value = null;
    activeSafetyError.value = null;
    historicalStopCode.value = null;
    userInput.value = "原始用户输入：请帮我分析这份超长财报";
    lastActionTriggered.value = "";
  },
};
</script>

<template>
  <div
    class="min-h-screen bg-gray-50 dark:bg-dark-950 text-gray-900 dark:text-gray-100 p-4"
  >
    <header
      class="mb-4 pb-2 border-b border-gray-200 dark:border-dark-800 flex items-center justify-between"
    >
      <h1 class="text-sm font-bold text-blue-600 dark:text-blue-400">
        Token Budget E2E Fixture Workbench
      </h1>
      <span data-testid="last-action" class="text-xs text-gray-500">
        动作: {{ lastActionTriggered || "无" }}
      </span>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 左侧：状态栏与聊天交互仿真区 -->
      <section class="space-y-4">
        <h2
          class="text-xs font-semibold text-gray-500 uppercase tracking-wider"
        >
          ChatAgentStatusBar 演练区
        </h2>

        <!-- 状态栏实际挂载点 -->
        <div
          class="p-3 bg-white dark:bg-dark-900 rounded-lg shadow-sm border border-gray-200 dark:border-dark-800"
        >
          <ChatAgentStatusBar
            :is-running="isRunning"
            :is-interrupted="isInterrupted"
            :error="errorMessage"
            :turn-state="turnState"
            :budget="budget"
            @action="handleStatusBarAction"
            @cancel="handleStatusBarCancel"
          />
        </div>

        <!-- 用户对话输入框（验证额度耗尽不锁死、草稿回填） -->
        <div
          class="p-4 bg-white dark:bg-dark-900 rounded-lg shadow-sm border border-gray-200 dark:border-dark-800 space-y-2"
        >
          <label
            class="block text-xs font-medium text-gray-700 dark:text-gray-300"
          >
            对话输入框 (验证保留输入能力与草稿回填)
          </label>
          <textarea
            v-model="userInput"
            data-testid="chat-user-input"
            rows="3"
            class="w-full text-xs p-2.5 rounded border border-gray-300 dark:border-dark-700 bg-white dark:bg-dark-800 focus:ring-1 focus:ring-blue-500"
          ></textarea>
        </div>

        <!-- 快速测试控制面板 -->
        <div
          class="p-4 bg-white dark:bg-dark-900 rounded-lg shadow-sm border border-gray-200 dark:border-dark-800 space-y-2 text-xs"
        >
          <h3 class="font-medium text-gray-700 dark:text-gray-300">
            快速场景切换
          </h3>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              data-testid="btn-scenario-approaching"
              class="px-2.5 py-1 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 font-medium"
              @click="
                () => {
                  isRunning = true;
                  turnState = 'running';
                  activeNotice = {
                    version: 1,
                    type: 'runtime_budget_notice',
                    code: 'token_budget_approaching',
                    budget_scope: 'run',
                    unit: 'tokens_total',
                    limit: 100000,
                    used: 82000,
                    remaining: 18000,
                    action: 'continue',
                    message: 'Token budget approaching limit',
                  };
                  activeSafetyError = null;
                  historicalStopCode = null;
                }
              "
            >
              在途预警 (82%)
            </button>

            <button
              type="button"
              data-testid="btn-scenario-in-flight-exhausted"
              class="px-2.5 py-1 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 font-medium"
              @click="
                () => {
                  isRunning = true;
                  turnState = 'running';
                  activeNotice = {
                    version: 1,
                    type: 'runtime_budget_notice',
                    code: 'token_budget_exhausted',
                    budget_scope: 'run',
                    unit: 'tokens_total',
                    limit: 100000,
                    used: 102000,
                    remaining: 0,
                    action: 'stop',
                    message: 'Token budget exhausted',
                  };
                  activeSafetyError = null;
                  historicalStopCode = null;
                }
              "
            >
              在途硬停中 (Exhausted Notice)
            </button>

            <button
              type="button"
              data-testid="btn-scenario-terminal-exhausted"
              class="px-2.5 py-1 rounded bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 font-medium"
              @click="
                () => {
                  isRunning = false;
                  turnState = 'error';
                  activeSafetyError = {
                    code: 'runtime_token_budget_exhausted',
                    message: 'Native run token budget exhausted',
                  };
                  errorMessage = 'Native run token budget exhausted';
                }
              "
            >
              终态额度耗尽 (Terminal Error)
            </button>

            <button
              type="button"
              data-testid="btn-scenario-natural-final"
              class="px-2.5 py-1 rounded bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 font-medium"
              @click="
                () => {
                  isRunning = false;
                  turnState = 'idle';
                  activeNotice = null;
                  activeSafetyError = null;
                  historicalStopCode = null;
                  errorMessage = undefined;
                }
              "
            >
              自然完成 (Natural Success)
            </button>
          </div>
        </div>
      </section>

      <!-- 右侧：RunUsage 面板演练区 -->
      <section class="space-y-4">
        <h2
          class="text-xs font-semibold text-gray-500 uppercase tracking-wider"
        >
          RunUsage 面板与水位条演练区
        </h2>
        <div
          class="p-3 bg-white dark:bg-dark-900 rounded-lg shadow-sm border border-gray-200 dark:border-dark-800"
        >
          <RunUsage
            data-testid="test-run-usage"
            thread-id="thread-budget-e2e"
            :run-id="selectedRunId"
            :runs="runsList"
            :run-status="runStatus"
            @select-run="handleSelectRun"
          />
        </div>
      </section>
    </div>
  </div>
</template>
