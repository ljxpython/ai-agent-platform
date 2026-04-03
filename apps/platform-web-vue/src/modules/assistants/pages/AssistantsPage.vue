<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listAssistantsPage } from '@/services/assistants/assistants.service'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementAssistant } from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'

const workspaceStore = useWorkspaceStore()

const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const error = ref('')
const total = ref(0)
const items = ref<ManagementAssistant[]>([])

const currentProject = computed(() => workspaceStore.currentProject)
const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const syncIssueCount = computed(() => items.value.filter((item) => item.sync_status !== 'synced').length)
const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProject.value?.name || '未选择',
    hint: '助手列表严格跟随当前 project 上下文',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '助手数量',
    value: total.value,
    hint: '当前项目下返回的助手总量',
    icon: 'assistant',
    tone: 'success'
  },
  {
    label: '同步异常',
    value: syncIssueCount.value,
    hint: 'sync_status 不为 synced 的助手',
    icon: 'activity',
    tone: 'warning'
  },
  {
    label: '已启用',
    value: activeCount.value,
    hint: '状态为 active 的助手',
    icon: 'sparkle',
    tone: 'danger'
  }
])

async function loadAssistants() {
  const projectId = workspaceStore.currentProjectId
  if (!projectId) {
    items.value = []
    total.value = 0
    error.value = ''
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''

  try {
    const payload = await listAssistantsPage(projectId, {
      limit: 50,
      offset: 0,
      query: query.value
    })

    items.value = payload.items
    total.value = payload.total
  } catch (loadError) {
    items.value = []
    total.value = 0
    error.value = loadError instanceof Error ? loadError.message : '助手列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  void loadAssistants()
}

watch(
  () => workspaceStore.currentProjectId,
  () => {
    void loadAssistants()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Assistants"
      title="助手管理"
      description="Agent 是汇报里的重点，所以这页先把项目上下文、助手列表和同步状态做成像样的后台页。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="!currentProject"
          @click="loadAssistants"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="助手列表加载失败"
      :description="error"
      variant="danger"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="助手是项目级资源，不带 project 上下文去查只会把接口边界搞乱。先通过顶部项目切换器选中项目，再进入这里。"
    />

    <TablePageLayout v-else>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
            <div class="relative">
              <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-dark-400">
                <BaseIcon
                  name="search"
                  size="sm"
                />
              </div>
              <BaseInput
                v-model="queryInput"
                class="pl-10"
                :placeholder="`在 ${currentProject.name} 下搜索助手`"
              />
            </div>
            <BaseButton @click="applyFilters">
              应用筛选
            </BaseButton>
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <div
          v-if="loading"
          class="p-6 text-sm text-slate-500 dark:text-dark-300"
        >
          正在加载助手列表...
        </div>

        <div
          v-else-if="items.length"
          class="pw-table-wrapper"
        >
          <table class="pw-table">
            <thead>
              <tr>
                <th>助手</th>
                <th>Graph</th>
                <th>同步状态</th>
                <th>运行状态</th>
                <th>最近同步</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="assistant in items"
                :key="assistant.id"
              >
                <td>
                  <div class="flex items-start gap-3">
                    <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300">
                      <BaseIcon
                        name="assistant"
                        size="sm"
                      />
                    </div>
                    <div>
                      <div class="font-semibold text-slate-900 dark:text-white">
                        {{ assistant.name }}
                      </div>
                      <div class="mt-1 text-sm leading-6 text-slate-500 dark:text-dark-300">
                        {{ assistant.description || '暂无描述' }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ assistant.graph_id || '未绑定' }}
                </td>
                <td>
                  <StatusPill :tone="assistant.sync_status === 'synced' ? 'success' : 'warning'">
                    {{ assistant.sync_status }}
                  </StatusPill>
                </td>
                <td>
                  <StatusPill :tone="assistant.status === 'active' ? 'success' : 'warning'">
                    {{ assistant.status }}
                  </StatusPill>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ formatDateTime(assistant.last_synced_at || assistant.updated_at) }}
                </td>
                <td class="text-slate-400 dark:text-dark-400">
                  {{ shortId(assistant.id) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          icon="assistant"
          title="当前项目还没有助手"
          description="接口已经接通了，只是这个项目下暂时没有可展示的数据。后续新建助手和详情页可以直接挂在这里继续做。"
        />
      </template>
    </TablePageLayout>
  </section>
</template>
