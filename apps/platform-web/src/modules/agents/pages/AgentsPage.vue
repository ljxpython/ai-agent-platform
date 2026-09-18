<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { listAgents } from "@/services/agents/agents.service";
import type { Agent } from "@/services/agents/types";

const router = useRouter();
const { activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();
const basePath = computed(
  () => `/workspace/projects/${encodeURIComponent(activeProjectId.value)}`,
);
const canCreate = computed(() =>
  can("project.assistant.write", activeProjectId.value),
);
const query = ref("");
const appliedQuery = ref("");
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const items = ref<Agent[]>([]);
const loading = ref(false);
const error = ref("");
let epoch = 0;

function avatarLetter(name: string) {
  return name.trim().charAt(0).toUpperCase() || "A";
}

async function load() {
  const requestEpoch = ++epoch;
  items.value = [];
  total.value = 0;
  error.value = "";
  loading.value = true;
  try {
    const result = await listAgents(activeProjectId.value, {
      query: appliedQuery.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    });
    if (requestEpoch === epoch) {
      items.value = result.items;
      total.value = result.total;
    }
  } catch (cause) {
    if (requestEpoch === epoch)
      error.value = cause instanceof Error ? cause.message : "读取失败";
  } finally {
    if (requestEpoch === epoch) loading.value = false;
  }
}
watch(
  activeProjectId,
  () => {
    page.value = 1;
    query.value = "";
    appliedQuery.value = "";
    void load();
  },
  { immediate: true },
);
watch([page, pageSize], () => {
  void load();
});
function search() {
  appliedQuery.value = query.value.trim();
  if (page.value === 1) void load();
  else page.value = 1;
}
onScopeDispose(() => {
  ++epoch;
});
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Agents"
      title="Agent 管理"
      description="管理项目内的智能体，可创建、查看配置并开始对话。"
    >
      <template #actions>
        <BaseButton
          v-if="canCreate"
          @click="router.push(`${basePath}/agents/new`)"
        >
          + 创建 Agent
        </BaseButton>
      </template>
    </PageHeader>
    <StateBanner
      v-if="error"
      variant="danger"
      title="读取失败"
      :description="error"
    />
    <SurfaceCard>
      <form
        class="mb-4 flex gap-3"
        @submit.prevent="search"
      >
        <input
          v-model="query"
          aria-label="搜索 Agent"
          class="pw-input flex-1"
          placeholder="搜索名称"
        >
        <BaseButton
          type="submit"
          variant="secondary"
          :disabled="loading"
        >
          搜索
        </BaseButton>
      </form>
      <p
        v-if="loading"
        role="status"
        class="py-8 text-center text-sm text-gray-500"
      >
        加载中…
      </p>
      <p
        v-else-if="!items.length"
        class="py-12 text-center text-gray-500"
      >
        {{ error ? "请重试读取列表" : "没有符合条件的 Agent" }}
      </p>
      <div
        v-else
        class="space-y-2"
      >
        <article
          v-for="agent in items"
          :key="agent.id"
          class="flex items-center gap-4 rounded-xl border border-gray-100 px-4 py-3 dark:border-dark-800 hover:bg-gray-50 dark:hover:bg-dark-900 transition-colors"
        >
          <!-- Avatar -->
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-100 text-sm font-bold text-primary-700 dark:bg-primary-950/40 dark:text-primary-300">
            {{ avatarLetter(agent.name) }}
          </div>
          <!-- 名称 + 描述 -->
          <div class="min-w-0 flex-1">
            <router-link
              :to="`${basePath}/agents/${agent.id}`"
              class="font-semibold text-gray-900 dark:text-white hover:underline"
            >
              {{ agent.name }}
            </router-link>
            <p class="mt-0.5 truncate text-xs text-gray-500 dark:text-dark-300">
              {{ agent.description || agent.graph_id }}
            </p>
          </div>
          <!-- Graph ID -->
          <span class="hidden shrink-0 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600 dark:bg-dark-800 dark:text-dark-200 sm:inline">
            {{ agent.graph_id }}
          </span>
          <!-- 状态 -->
          <StatusPill :tone="agent.status === 'active' ? 'success' : 'warning'">
            {{ agent.status === "active" ? "启用" : "停用" }}
          </StatusPill>
          <!-- 操作 -->
          <div class="flex shrink-0 gap-2">
            <BaseButton
              variant="secondary"
              @click="router.push(`${basePath}/agents/${agent.id}`)"
            >
              编辑配置
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="agent.status !== 'active' || !can('project.runtime.read')"
              @click="
                router.push({
                  path: `${basePath}/chat`,
                  query: { agentId: agent.id },
                })
              "
            >
              打开聊天
            </BaseButton>
          </div>
        </article>
      </div>
      <PaginationBar
        :total="total"
        :page="page"
        :page-size="pageSize"
        :disabled="loading"
        @update:page="page = $event"
        @update:page-size="
          pageSize = $event;
          page = 1;
        "
      />
    </SurfaceCard>
  </section>
</template>
