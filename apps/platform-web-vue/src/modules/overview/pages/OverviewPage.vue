<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import PageHeader from '@/components/layout/PageHeader.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import GuidePanel from '@/components/platform/GuidePanel.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listAssistantsPage } from '@/services/assistants/assistants.service'
import { listAudit } from '@/services/audit/audit.service'
import { listProjectsPage } from '@/services/projects/projects.service'
import { listUsersPage } from '@/services/users/users.service'
import type { ManagementAssistant, ManagementAuditRow, ManagementProject } from '@/types/management'
import { formatDateTime } from '@/utils/format'

const { workspaceStore, activeProjectId, activeProject } = useWorkspaceProjectContext()

const loading = ref(false)
const error = ref('')
const projectTotal = ref(0)
const userTotal = ref(0)
const assistantTotal = ref(0)
const auditTotal = ref(0)
const recentProjects = ref<ManagementProject[]>([])
const recentAuditRows = ref<ManagementAuditRow[]>([])
const currentProjectAssistants = ref<ManagementAssistant[]>([])

const currentProject = activeProject
const assistantProject = activeProject
const stats = computed(() => [
  {
    label: '项目总量',
    value: projectTotal.value,
    hint: currentProject.value ? `当前聚焦：${currentProject.value.name}` : '还没有选中的项目上下文',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '成员总量',
    value: userTotal.value,
    hint: '当前来自正式控制面的用户目录',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '助手总量',
    value: assistantTotal.value,
    hint: assistantProject.value
      ? `当前助手上下文 ${assistantProject.value.name} 下的助手数量`
      : '先选择助手上下文项目后再查看助手统计',
    icon: 'assistant',
    tone: 'warning'
  },
  {
    label: '审计记录',
    value: auditTotal.value,
    hint: '优先展示正式控制面的最近操作轨迹',
    icon: 'activity',
    tone: 'danger'
  }
])

function getAuditTone(statusCode: number): 'success' | 'warning' | 'danger' {
  if (statusCode >= 500) {
    return 'danger'
  }

  if (statusCode >= 400) {
    return 'warning'
  }

  return 'success'
}

async function ensureOverviewRuntimeContext() {
  if (workspaceStore.projects.length > 0) {
    return
  }

  await workspaceStore.hydrateContext()
}

async function loadOverview() {
  loading.value = true
  error.value = ''

  await ensureOverviewRuntimeContext()
  const auditProjectId = activeProjectId.value
  const assistantProjectId = activeProjectId.value
  const results = await Promise.allSettled([
    listProjectsPage({ limit: 6, offset: 0 }),
    listUsersPage({ limit: 6, offset: 0 }),
    listAudit(auditProjectId || null, { limit: 6, offset: 0 }),
    assistantProjectId
      ? listAssistantsPage(assistantProjectId, { limit: 6, offset: 0 })
      : Promise.resolve({ items: [], total: 0 })
  ])

  const failedSections: string[] = []
  const [projectsResult, usersResult, auditResult, assistantsResult] = results

  if (projectsResult.status === 'fulfilled') {
    projectTotal.value = projectsResult.value.total
    recentProjects.value = projectsResult.value.items
  } else {
    failedSections.push('项目')
    projectTotal.value = 0
    recentProjects.value = []
  }

  if (usersResult.status === 'fulfilled') {
    userTotal.value = usersResult.value.total
  } else {
    failedSections.push('用户')
    userTotal.value = 0
  }

  if (auditResult.status === 'fulfilled') {
    auditTotal.value = auditResult.value.total
    recentAuditRows.value = auditResult.value.items
  } else {
    failedSections.push('审计')
    auditTotal.value = 0
    recentAuditRows.value = []
  }

  if (assistantsResult.status === 'fulfilled') {
    assistantTotal.value = assistantsResult.value.total
    currentProjectAssistants.value = assistantsResult.value.items
  } else {
    failedSections.push('助手')
    assistantTotal.value = 0
    currentProjectAssistants.value = []
  }

  if (failedSections.length > 0) {
    error.value = `部分概览数据加载失败：${failedSections.join('、')}`
  }

  loading.value = false
}

watch(
  activeProjectId,
  () => {
    void loadOverview()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Overview"
      title="Agent Platform Console 总览"
      description="把当前工作台的项目、成员、助手和最近操作压缩成一张可直接汇报的概览面板。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadOverview"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新概览
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="概览存在部分缺口"
      :description="error"
      variant="warning"
    />

    <GuidePanel
      guide-id="overview-demo-path"
      title="建议演示路径"
      description="如果你要快速演示当前成果，优先按这个顺序走：1. 选项目 2. 打开 SQL Agent 或 Chat 3. 查看 Testcase 生成 / 文档链路 4. 回到 Resources 看沉淀的 UI 模板。"
      tone="success"
    >
      <template #actions>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/sql-agent"
        >
          去 SQL Agent
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/chat"
        >
          去 Chat
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/testcase/generate"
        >
          去 Testcase Generate
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/resources"
        >
          去 Resources
        </router-link>
      </template>
    </GuidePanel>

    <div class="grid gap-3 xl:grid-cols-4">
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

    <div class="grid gap-4 xl:items-start xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.9fr)]">
      <SurfaceCard class="space-y-4">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="pw-page-eyebrow">
              Current Project
            </div>
            <h2 class="mt-2 text-xl font-semibold text-gray-900 dark:text-white">
              {{ currentProject?.name ?? '未选择项目' }}
            </h2>
          </div>
          <StatusPill :tone="currentProject ? 'info' : 'neutral'">
            {{ currentProject?.status ?? 'none' }}
          </StatusPill>
        </div>

        <p class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          {{
            currentProject?.description ||
              '这里展示的是当前工作区项目上下文，后续治理页和工作台页面都会沿用这套统一项目口径。'
          }}
        </p>

        <div class="grid gap-3 xl:items-start xl:grid-cols-2">
          <div class="pw-card-subtle p-4">
            <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <BaseIcon
                name="folder"
                size="sm"
                class="text-primary-500"
              />
              最近项目
            </div>
            <div
              v-if="recentProjects.length"
              class="mt-4 space-y-3"
            >
              <div
                v-for="project in recentProjects.slice(0, 3)"
                :key="project.id"
                class="pw-card border-gray-200 p-3"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ project.name }}
                  </div>
                  <StatusPill :tone="project.status === 'active' ? 'success' : 'neutral'">
                    {{ project.status }}
                  </StatusPill>
                </div>
                <p class="mt-2 text-sm leading-6 text-gray-500 dark:text-dark-300">
                  {{ project.description || '暂无描述' }}
                </p>
              </div>
            </div>
            <EmptyState
              v-else
              icon="folder"
              title="暂无项目数据"
              description="当前还没有拿到可展示的项目摘要。"
            />
          </div>

          <div class="pw-card-subtle p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <BaseIcon
                  name="assistant"
                  size="sm"
                  class="text-primary-500"
                />
                当前项目助手
              </div>
              <StatusPill :tone="assistantProject ? 'info' : 'neutral'">
                {{ assistantProject?.name || '未选择' }}
              </StatusPill>
            </div>
            <div
              v-if="currentProjectAssistants.length"
              class="mt-4 space-y-3"
            >
              <div
                v-for="assistant in currentProjectAssistants.slice(0, 3)"
                :key="assistant.id"
                class="pw-card border-gray-200 p-3"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ assistant.name }}
                  </div>
                  <StatusPill :tone="assistant.status === 'active' ? 'success' : 'warning'">
                    {{ assistant.status }}
                  </StatusPill>
                </div>
                <p class="mt-2 text-sm leading-6 text-gray-500 dark:text-dark-300">
                  {{ assistant.description || '暂无描述' }}
                </p>
              </div>
            </div>
            <EmptyState
              v-else
              icon="assistant"
              :title="assistantProject ? '当前助手上下文还没有助手' : '请先选择助手上下文项目'"
              :description="
                assistantProject
                  ? '这个助手上下文项目下暂时没有助手数据。'
                  : '先在顶部切换器里选择对应项目，再查看助手摘要。'
              "
            />
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="activity"
            size="sm"
            class="text-primary-500"
          />
          最近管理动作
        </div>

        <div
          v-if="loading"
          class="text-sm text-gray-500 dark:text-dark-300"
        >
          正在加载总览数据...
        </div>

        <div
          v-else-if="recentAuditRows.length"
          class="space-y-3"
        >
          <div
            v-for="row in recentAuditRows"
            :key="row.id"
            class="pw-card-subtle p-4"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ row.action || row.path }}
              </div>
              <StatusPill :tone="getAuditTone(row.status_code)">
                {{ row.status_code }}
              </StatusPill>
            </div>
            <div class="mt-2 text-sm text-gray-500 dark:text-dark-300">
              {{ row.method }} · {{ row.path }}
            </div>
            <div class="mt-2 text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
              {{ formatDateTime(row.created_at) }}
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          icon="activity"
          title="最近没有可展示的动作"
          description="审计列表为空时，这里也不会胡编数据。后面 audit 页面会承接更完整的筛选和追踪。"
        />
      </SurfaceCard>
    </div>
  </section>
</template>
