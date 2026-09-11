<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useAuthStore } from "@/stores/auth";
import { listAgents } from "@/services/agents/agents.service";
import type { Agent } from "@/services/agents/types";
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
const loading = ref(false);
const error = ref("");
let epoch = 0;

async function load() {
  const requestEpoch = ++epoch;
  const projectId = activeProjectId.value;
  agents.value = [];
  threads.value = [];
  agentTotal.value = null;
  error.value = "";
  loading.value = Boolean(projectId);
  if (!projectId) return;
  const service = createSessionService(
    createLanggraphAuthorizedFetch(),
    projectId,
  );
  const [agentResult, threadResult] = await Promise.allSettled([
    canReadAgents.value
      ? listAgents(projectId, { limit: 6 })
      : Promise.resolve(null),
    canReadChat.value ? service.list() : Promise.resolve(null),
  ]);
  if (requestEpoch !== epoch) return;
  const failed: string[] = [];
  if (agentResult.status === "fulfilled" && agentResult.value) {
    agents.value = agentResult.value.items;
    agentTotal.value = agentResult.value.total;
  } else if (agentResult.status === "rejected") failed.push("Agent");
  if (threadResult.status === "fulfilled" && threadResult.value)
    threads.value = threadResult.value.slice(0, 6);
  else if (threadResult.status === "rejected") failed.push("最近对话");
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
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto">
    <PageHeader
      eyebrow="Overview"
      title="工作区总览"
      description="从当前项目继续工作。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="load"
        >
          刷新
        </BaseButton>
      </template>
    </PageHeader>
    <StateBanner
      v-if="error"
      title="部分数据无法读取"
      :description="error"
      variant="warning"
    />
    <SurfaceCard>
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-semibold">
            {{ activeProject?.name || "选择一个项目" }}
          </h2>
          <p class="mt-2 text-sm text-gray-500">
            {{
              activeProject?.description || "使用顶部项目切换器选择工作项目。"
            }}
          </p>
        </div>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/projects"
        >
          查看项目 · {{ activeProjects.length }}
        </router-link>
      </div>
      <div
        v-if="activeProject"
        class="mt-5 flex flex-wrap gap-3"
      >
        <router-link
          v-if="canReadChat"
          class="pw-btn pw-btn-primary"
          :to="`${basePath}/chat`"
        >
          开始对话
        </router-link>
        <router-link
          v-if="canReadAgents"
          class="pw-btn pw-btn-secondary"
          :to="`${basePath}/agents`"
        >
          管理 Agents
        </router-link>
        <router-link
          v-if="canReadChat"
          class="pw-btn pw-btn-secondary"
          :to="`${basePath}/graphs`"
        >
          浏览 Graphs
        </router-link>
      </div>
    </SurfaceCard>
    <p
      v-if="loading"
      role="status"
      class="text-sm text-gray-500"
    >
      正在读取项目数据…
    </p>
    <div
      v-else-if="activeProject"
      class="grid gap-4 xl:grid-cols-2"
    >
      <SurfaceCard v-if="canReadAgents">
        <h2 class="mb-4 font-semibold">
          项目 Agents
          <span
            v-if="agentTotal !== null"
            class="text-gray-500"
          >· {{ agentTotal }}</span>
        </h2>
        <div
          v-if="agents.length"
          class="space-y-3"
        >
          <router-link
            v-for="agent in agents"
            :key="agent.id"
            :to="`${basePath}/agents/${agent.id}`"
            class="pw-card-subtle block p-4 hover:border-primary-300"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="font-medium">{{ agent.name }}</span><span class="text-xs text-gray-500">{{
                agent.status === "active" ? "启用" : "停用"
              }}</span>
            </div>
            <p class="mt-2 text-sm text-gray-500">
              {{ agent.description || agent.graph_id }}
            </p>
          </router-link>
        </div>
        <EmptyState
          v-else
          icon="assistant"
          :title="agentTotal === 0 ? '还没有 Agent' : 'Agent 数据暂不可用'"
          description="可在 Agent 管理中查看或创建配置。"
        />
      </SurfaceCard>
      <SurfaceCard v-if="canReadChat">
        <h2 class="mb-4 font-semibold">
          最近对话
        </h2>
        <div
          v-if="threads.length"
          class="space-y-3"
        >
          <router-link
            v-for="thread in threads"
            :key="thread.thread_id"
            :to="`${basePath}/chat/${thread.thread_id}`"
            class="pw-card-subtle block p-4 hover:border-primary-300"
          >
            <p class="truncate font-medium">
              {{ thread.metadata?.title || "未命名对话" }}
            </p>
            <p class="mt-2 text-xs text-gray-500">
              {{ formatDateTime(thread.updated_at) }}
            </p>
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
    </div>
  </section>
</template>
