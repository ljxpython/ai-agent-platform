<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
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
const query = ref("");
const appliedQuery = ref("");
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const items = ref<Agent[]>([]);
const loading = ref(false);
const error = ref("");
let epoch = 0;
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
      description="自动展示项目已授权的智能体，无需手动创建。可查看配置并开始对话。"
    />
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
          class="pw-input"
          placeholder="搜索名称"
        ><BaseButton
          type="submit"
          :disabled="loading"
        >
          搜索
        </BaseButton>
      </form>
      <p
        v-if="loading"
        role="status"
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
        class="overflow-x-auto"
      >
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="border-b">
              <th class="p-3">
                名称
              </th>
              <th class="p-3">
                Graph
              </th>
              <th class="p-3">
                状态
              </th>
              <th class="p-3">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="agent in items"
              :key="agent.id"
              class="border-b border-gray-100 dark:border-dark-800"
            >
              <td class="p-3">
                <router-link
                  :to="`${basePath}/agents/${agent.id}`"
                  class="font-medium hover:underline"
                >
                  {{ agent.name }}
                </router-link>
                <p class="mt-1 text-xs text-gray-500">
                  {{ agent.description }}
                </p>
              </td>
              <td class="p-3">
                {{ agent.graph_id }}
              </td>
              <td class="p-3">
                {{ agent.status === "active" ? "启用" : "停用" }}
              </td>
              <td class="p-3">
                <BaseButton
                  variant="secondary"
                  :disabled="
                    agent.status !== 'active' || !can('project.runtime.read')
                  "
                  @click="
                    router.push({
                      path: `${basePath}/chat`,
                      query: { agentId: agent.id },
                    })
                  "
                >
                  打开聊天
                </BaseButton>
              </td>
            </tr>
          </tbody>
        </table>
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
