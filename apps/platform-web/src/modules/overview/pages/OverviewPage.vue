<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useAuthStore } from "@/stores/auth";
import { listAgents } from "@/services/agents/agents.service";
import type { Agent } from "@/services/agents/types";
import { listRuntimeTools } from "@/services/runtime/runtime.service";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import { formatDateTime } from "@/utils/format";

const { activeProjectId, activeProject, activeProjects } =
  useWorkspaceProjectContext();
const auth = useAuthStore();
const { can } = useAuthorization();

const canReadAgents = computed(() => can("project.assistant.read"));
const canReadChat = computed(() => can("project.runtime.read"));
const basePath = computed(
  () => `/workspace/projects/${encodeURIComponent(activeProjectId.value)}`,
);

const agents = ref<Agent[]>([]);
const threads = ref<ChatThread[]>([]);
const agentTotal = ref<number | null>(null);
const toolsTotal = ref<number | null>(null);
const loading = ref(false);
const error = ref("");
let epoch = 0;

function formatRelativeTime(value?: string | null): string {
  if (!value) return "--";
  const date = new Date(value);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (Number.isNaN(diffMs)) return value;
  if (diffMs < 0) return "刚刚";
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "刚刚";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} 天前`;
  return formatDateTime(value);
}

async function load() {
  const requestEpoch = ++epoch;
  const projectId = activeProjectId.value;
  agents.value = [];
  threads.value = [];
  agentTotal.value = null;
  toolsTotal.value = null;
  error.value = "";
  loading.value = Boolean(projectId);
  if (!projectId) return;

  const service = createSessionService(
    createLanggraphAuthorizedFetch(),
    projectId,
  );

  const [agentResult, threadResult, toolResult] = await Promise.allSettled([
    canReadAgents.value
      ? listAgents(projectId, { limit: 6 })
      : Promise.resolve(null),
    canReadChat.value ? service.list() : Promise.resolve(null),
    canReadChat.value ? listRuntimeTools(projectId) : Promise.resolve(null),
  ]);

  if (requestEpoch !== epoch) return;

  const failed: string[] = [];
  if (agentResult.status === "fulfilled" && agentResult.value) {
    agents.value = agentResult.value.items;
    agentTotal.value = agentResult.value.total;
  } else if (agentResult.status === "rejected") {
    failed.push("Agent");
  }

  if (threadResult.status === "fulfilled" && threadResult.value) {
    threads.value = threadResult.value.slice(0, 6);
  } else if (threadResult.status === "rejected") {
    failed.push("最近对话");
  }

  if (toolResult.status === "fulfilled" && toolResult.value) {
    toolsTotal.value = toolResult.value.count;
  }

  error.value = failed.length ? `${failed.join("、")}读取失败，请重试。` : "";
  loading.value = false;
}

watch(
  [activeProjectId, () => auth.sessionEpoch, canReadAgents, canReadChat],
  () => {
    void load();
  },
  { immediate: true },
);

onScopeDispose(() => {
  ++epoch;
});
</script>

<template>
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto space-y-4">
    <!-- 紧凑 Header：无废话副标题，操作收敛至右上角 -->
    <PageHeader eyebrow="Overview" title="工作区总览" description="" compact>
      <template #actions>
        <router-link
          v-if="can('platform.config.read')"
          class="pw-btn pw-btn-secondary gap-1.5"
          to="/workspace/control-plane"
        >
          <BaseIcon name="shield" size="sm" />
          <span>平台治理</span>
        </router-link>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          class="gap-1.5"
          @click="load"
        >
          <BaseIcon
            name="refresh"
            size="sm"
            :class="{ 'animate-spin': loading }"
          />
          <span>刷新</span>
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="部分数据无法读取"
      :description="error"
      variant="warning"
    />

    <!-- 4 联核心指标看板 -->
    <div
      v-if="activeProject"
      class="grid grid-cols-2 gap-3.5 sm:grid-cols-2 lg:grid-cols-4"
    >
      <MetricCard
        label="项目 Agents"
        :value="agentTotal ?? agents.length"
        hint="当前项目已挂载智能体"
        icon="assistant"
        tone="primary"
      />
      <MetricCard
        label="活跃会话"
        :value="threads.length"
        hint="近期待恢复对话工作流"
        icon="chat"
        tone="success"
      />
      <MetricCard
        label="装配工具"
        :value="toolsTotal !== null ? toolsTotal : '--'"
        hint="已就绪 MCP 与技能工具"
        icon="runtime"
        tone="warning"
      />
      <MetricCard
        label="运行时引擎"
        value="LangGraph"
        hint="Runtime 在线 · 探针就绪"
        icon="activity"
        tone="success"
      />
    </div>

    <!-- 项目快速开工横幅 Hero -->
    <SurfaceCard>
      <StateBanner
        v-if="!canReadChat"
        title="尚未获得项目对话权限"
        description="平台治理身份不自动包含项目访问资格。请选择已加入的项目，或联系项目管理员添加成员并授予执行权限。"
        variant="info"
        class="mb-3"
      />

      <div
        class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between"
      >
        <div class="flex items-start gap-3.5">
          <div
            class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300"
          >
            <BaseIcon name="folder" size="md" />
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <h2
                class="truncate text-lg font-bold text-gray-950 dark:text-white"
              >
                {{ activeProject?.name || "选择一个项目" }}
              </h2>
              <span
                v-if="activeProject"
                class="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
              >
                <span
                  class="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"
                />
                就绪
              </span>
            </div>
            <p
              class="mt-1 line-clamp-1 text-sm text-gray-500 dark:text-dark-300"
            >
              {{
                activeProject?.description || "使用顶部项目切换器选择工作项目。"
              }}
            </p>
          </div>
        </div>

        <div v-if="activeProject" class="flex flex-wrap items-center gap-2.5">
          <router-link
            v-if="canReadChat"
            class="pw-btn pw-btn-primary gap-1.5 shadow-sm"
            :to="`${basePath}/chat`"
          >
            <BaseIcon name="plus" size="sm" />
            <span>开始对话</span>
          </router-link>
          <router-link
            v-if="canReadAgents"
            class="pw-btn pw-btn-secondary gap-1.5"
            :to="`${basePath}/agents`"
          >
            <BaseIcon name="assistant" size="sm" />
            <span>管理 Agents</span>
          </router-link>
          <router-link
            v-if="canReadChat"
            class="pw-btn pw-btn-secondary gap-1.5"
            :to="`${basePath}/graphs`"
          >
            <BaseIcon name="graph" size="sm" />
            <span>浏览 Graphs</span>
          </router-link>
          <router-link
            class="pw-btn pw-btn-secondary gap-1.5"
            to="/workspace/projects"
          >
            <BaseIcon name="project" size="sm" />
            <span>切换项目 · {{ activeProjects.length }}</span>
          </router-link>
        </div>
      </div>
    </SurfaceCard>

    <p
      v-if="loading"
      role="status"
      class="text-sm text-gray-500 py-4 text-center"
    >
      正在读取项目数据…
    </p>

    <!-- 主辅双栏工作流：左栏最近会话 (7fr)，右栏主力 Agents (5fr) -->
    <div v-else-if="activeProject" class="grid gap-4 xl:grid-cols-12">
      <!-- 左栏：最近对话流 -->
      <SurfaceCard v-if="canReadChat" class="xl:col-span-7 flex flex-col">
        <div class="mb-3.5 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <BaseIcon name="chat" size="sm" class="text-primary-500" />
            <h3 class="font-semibold text-gray-900 dark:text-white">
              最近对话
            </h3>
          </div>
          <router-link
            :to="`${basePath}/chat`"
            class="text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
          >
            进入 Chat 工作台 →
          </router-link>
        </div>

        <div v-if="threads.length" class="space-y-2.5">
          <router-link
            v-for="thread in threads"
            :key="thread.thread_id"
            :to="`${basePath}/chat/${thread.thread_id}`"
            class="pw-card-subtle group flex items-center justify-between p-3.5 hover:border-primary-300 hover:shadow-sm transition-all duration-200"
          >
            <div class="min-w-0 flex-1 pr-3">
              <p
                class="truncate font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors"
              >
                {{ thread.metadata?.title || "未命名对话" }}
              </p>
              <div
                class="mt-1 flex items-center gap-2 text-xs text-gray-400 dark:text-dark-400"
              >
                <span>{{ formatRelativeTime(thread.updated_at) }}</span>
                <span>·</span>
                <span
                  class="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400"
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  可恢复
                </span>
              </div>
            </div>
            <BaseIcon
              name="chevron-right"
              size="sm"
              class="text-gray-400 group-hover:text-primary-500 group-hover:translate-x-0.5 transition-all"
            />
          </router-link>
        </div>
        <EmptyState
          v-else
          icon="chat"
          :title="
            error.includes('最近对话') ? '最近对话暂不可用' : '还没有对话'
          "
          description="选择 Agent 或 Graph 开始新的对话。"
        />
      </SurfaceCard>

      <!-- 右栏：项目 Agents 矩阵 -->
      <SurfaceCard v-if="canReadAgents" class="xl:col-span-5 flex flex-col">
        <div class="mb-3.5 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <BaseIcon name="assistant" size="sm" class="text-primary-500" />
            <h3 class="font-semibold text-gray-900 dark:text-white">
              项目 Agents
              <span
                v-if="agentTotal !== null"
                class="text-xs font-normal text-gray-500 ml-1"
                >({{ agentTotal }})</span
              >
            </h3>
          </div>
          <router-link
            :to="`${basePath}/agents`"
            class="text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
          >
            管理 Agents →
          </router-link>
        </div>

        <div v-if="agents.length" class="space-y-2.5">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="pw-card-subtle group flex items-center justify-between p-3.5 hover:border-primary-300 hover:shadow-sm transition-all duration-200"
          >
            <router-link
              :to="`${basePath}/agents/${agent.id}`"
              class="min-w-0 flex-1 pr-2"
            >
              <div class="flex items-center gap-2">
                <span
                  class="truncate font-medium text-gray-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors"
                >
                  {{ agent.name }}
                </span>
                <span
                  class="shrink-0 inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded"
                  :class="
                    agent.status === 'active'
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                      : 'bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-dark-300'
                  "
                >
                  {{ agent.status === "active" ? "启用" : "停用" }}
                </span>
              </div>
              <div class="mt-1 flex flex-wrap items-center gap-2">
                <span
                  v-if="agent.context?.model_id"
                  class="font-mono text-[10px] bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-dark-300 px-1.5 py-0.5 rounded"
                >
                  {{ agent.context.model_id }}
                </span>
                <span class="truncate text-xs text-gray-500 dark:text-dark-300">
                  {{ agent.description || agent.graph_id }}
                </span>
              </div>
            </router-link>

            <!-- 快捷立即对话按钮 -->
            <router-link
              v-if="canReadChat"
              :to="`${basePath}/chat?agent=${encodeURIComponent(agent.id)}`"
              title="使用该 Agent 发起对话"
              class="shrink-0 flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-primary-50 hover:text-primary-600 dark:hover:bg-primary-950/50 dark:hover:text-primary-300 transition-colors"
            >
              <BaseIcon name="sparkle" size="sm" />
            </router-link>
          </div>
        </div>
        <EmptyState
          v-else
          icon="assistant"
          :title="agentTotal === 0 ? '还没有 Agent' : 'Agent 数据暂不可用'"
          description="可在 Agent 管理中查看或创建配置。"
        />
      </SurfaceCard>
    </div>
  </section>
</template>
