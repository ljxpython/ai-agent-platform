<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listAssistantsPage } from '@/services/assistants/assistants.service'
import { listAudit } from '@/services/audit/audit.service'
import { listProjectsPage } from '@/services/projects/projects.service'
import { listUsersPage } from '@/services/users/users.service'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementAssistant, ManagementAuditRow, ManagementProject } from '@/types/management'
import { formatDateTime } from '@/utils/format'

const workspaceStore = useWorkspaceStore()

const loading = ref(false)
const error = ref('')
const projectTotal = ref(0)
const userTotal = ref(0)
const assistantTotal = ref(0)
const auditTotal = ref(0)
const recentProjects = ref<ManagementProject[]>([])
const recentAuditRows = ref<ManagementAuditRow[]>([])
const currentProjectAssistants = ref<ManagementAssistant[]>([])

const currentProject = computed(() => workspaceStore.currentProject)
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
    hint: '来自管理端用户列表接口',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '助手总量',
    value: assistantTotal.value,
    hint: currentProject.value ? `当前项目 ${currentProject.value.name} 下的助手数量` : '先选择项目后再查看助手统计',
    icon: 'assistant',
    tone: 'warning'
  },
  {
    label: '审计记录',
    value: auditTotal.value,
    hint: '优先展示最近的管理端操作轨迹',
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

async function loadOverview() {
  loading.value = true
  error.value = ''

  const projectId = workspaceStore.currentProjectId
  const results = await Promise.allSettled([
    listProjectsPage({ limit: 6, offset: 0 }),
    listUsersPage({ limit: 6, offset: 0 }),
    listAudit(projectId || null, { limit: 6, offset: 0 }),
    projectId
      ? listAssistantsPage(projectId, { limit: 6, offset: 0 })
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
  () => workspaceStore.currentProjectId,
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
      title="Platform Workspace 总览"
      description="先把当前工作台的项目、成员、助手和最近操作压缩成一个真正能汇报的概览面板，而不是空壳页面。"
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

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.9fr)]">
      <SurfaceCard class="space-y-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="pw-page-eyebrow">
              Current Project
            </div>
            <h2 class="mt-2 text-xl font-semibold text-slate-900 dark:text-white">
              {{ currentProject?.name ?? '未选择项目' }}
            </h2>
          </div>
          <StatusPill :tone="currentProject ? 'info' : 'neutral'">
            {{ currentProject?.status ?? 'none' }}
          </StatusPill>
        </div>

        <p class="text-sm leading-7 text-slate-500 dark:text-dark-300">
          {{
            currentProject?.description ||
              '项目上下文会驱动 assistants、runtime、graphs、sql-agent 等后续页面，所以这里先把项目切换打透。'
          }}
        </p>

        <div class="grid gap-4 xl:grid-cols-2">
          <div class="pw-card bg-slate-50/90 p-4 dark:bg-dark-900">
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
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
                class="pw-card bg-white/80 p-3 dark:bg-dark-950/70"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-semibold text-slate-900 dark:text-white">
                    {{ project.name }}
                  </div>
                  <StatusPill :tone="project.status === 'active' ? 'success' : 'neutral'">
                    {{ project.status }}
                  </StatusPill>
                </div>
                <p class="mt-2 text-sm leading-6 text-slate-500 dark:text-dark-300">
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

          <div class="pw-card bg-slate-50/90 p-4 dark:bg-dark-900">
            <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
              <BaseIcon
                name="assistant"
                size="sm"
                class="text-primary-500"
              />
              当前项目助手
            </div>
            <div
              v-if="currentProjectAssistants.length"
              class="mt-4 space-y-3"
            >
              <div
                v-for="assistant in currentProjectAssistants.slice(0, 3)"
                :key="assistant.id"
                class="pw-card bg-white/80 p-3 dark:bg-dark-950/70"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="text-sm font-semibold text-slate-900 dark:text-white">
                    {{ assistant.name }}
                  </div>
                  <StatusPill :tone="assistant.status === 'active' ? 'success' : 'warning'">
                    {{ assistant.status }}
                  </StatusPill>
                </div>
                <p class="mt-2 text-sm leading-6 text-slate-500 dark:text-dark-300">
                  {{ assistant.description || '暂无描述' }}
                </p>
              </div>
            </div>
            <EmptyState
              v-else
              icon="assistant"
              :title="currentProject ? '当前项目还没有助手' : '请先选择项目'"
              :description="
                currentProject
                  ? '这个项目下暂时没有助手数据。'
                  : '先在顶部选择项目，再查看对应助手。'
              "
            />
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
          <BaseIcon
            name="activity"
            size="sm"
            class="text-primary-500"
          />
          最近管理动作
        </div>

        <div
          v-if="loading"
          class="text-sm text-slate-500 dark:text-dark-300"
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
            class="pw-card bg-slate-50/90 p-4 dark:bg-dark-900"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="text-sm font-semibold text-slate-900 dark:text-white">
                {{ row.action || row.path }}
              </div>
              <StatusPill :tone="getAuditTone(row.status_code)">
                {{ row.status_code }}
              </StatusPill>
            </div>
            <div class="mt-2 text-sm text-slate-500 dark:text-dark-300">
              {{ row.method }} · {{ row.path }}
            </div>
            <div class="mt-2 text-xs uppercase tracking-[0.14em] text-slate-400 dark:text-dark-400">
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
