<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
import { listProjectsPage } from '@/services/projects/projects.service'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementProject } from '@/types/management'
import { shortId } from '@/utils/format'

const workspaceStore = useWorkspaceStore()

const queryInput = ref('')
const query = ref('')
const loading = ref(false)
const error = ref('')
const total = ref(0)
const items = ref<ManagementProject[]>([])

const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const stats = computed(() => [
  {
    label: '当前结果',
    value: items.value.length,
    hint: query.value ? `按关键词“${query.value}”筛选` : '展示最近返回的项目列表',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '项目总量',
    value: total.value,
    hint: '来自管理端项目分页接口',
    icon: 'overview',
    tone: 'success'
  },
  {
    label: '活跃项目',
    value: activeCount.value,
    hint: '当前结果集中状态为 active 的项目',
    icon: 'activity',
    tone: 'warning'
  }
])

async function loadProjects() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listProjectsPage({
      limit: 50,
      offset: 0,
      query: query.value
    })

    items.value = payload.items
    total.value = payload.total
  } catch (loadError) {
    items.value = []
    total.value = 0
    error.value = loadError instanceof Error ? loadError.message : '项目列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  void loadProjects()
}

function resetFilters() {
  queryInput.value = ''
  query.value = ''
  void loadProjects()
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Projects"
      title="项目管理"
      description="项目页先作为新视觉基座的样板列表页，重点验证筛选栏、统计卡片、表格容器和当前项目高亮。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadProjects"
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
      title="项目列表加载失败"
      :description="error"
      variant="danger"
    />

    <div class="grid gap-4 xl:grid-cols-3">
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

    <TablePageLayout>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto_auto]">
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
                placeholder="按项目名或描述搜索"
              />
            </div>
            <BaseButton
              variant="secondary"
              @click="resetFilters"
            >
              重置
            </BaseButton>
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
          正在加载项目列表...
        </div>

        <div
          v-else-if="items.length"
          class="pw-table-wrapper"
        >
          <table class="pw-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>描述</th>
                <th>状态</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="project in items"
                :key="project.id"
              >
                <td>
                  <div class="flex items-start gap-3">
                    <div class="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300">
                      <BaseIcon
                        name="folder"
                        size="sm"
                      />
                    </div>
                    <div>
                      <div class="text-sm font-semibold text-slate-900 dark:text-white">
                        {{ project.name }}
                      </div>
                      <div
                        v-if="workspaceStore.currentProjectId === project.id"
                        class="mt-1 text-xs uppercase tracking-[0.14em] text-primary-600 dark:text-primary-300"
                      >
                        当前工作台项目
                      </div>
                    </div>
                  </div>
                </td>
                <td class="max-w-[420px]">
                  <div class="leading-6 text-slate-500 dark:text-dark-300">
                    {{ project.description || '暂无描述' }}
                  </div>
                </td>
                <td>
                  <StatusPill :tone="project.status === 'active' ? 'success' : 'neutral'">
                    {{ project.status }}
                  </StatusPill>
                </td>
                <td class="text-slate-400 dark:text-dark-400">
                  {{ shortId(project.id) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          icon="folder"
          title="没有找到项目"
          description="当前筛选条件下没有项目数据。后续创建、详情和成员管理会在这张列表页母版上继续展开。"
        />
      </template>
    </TablePageLayout>
  </section>
</template>
