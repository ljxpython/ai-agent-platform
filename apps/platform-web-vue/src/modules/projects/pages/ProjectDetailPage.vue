<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listProjectMembers } from '@/services/members/members.service'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ManagementProjectMember } from '@/types/management'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'

function getRoleTone(role: string): 'info' | 'success' | 'warning' {
  if (role === 'admin') {
    return 'warning'
  }
  if (role === 'editor') {
    return 'info'
  }
  return 'success'
}

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()
const uiStore = useUiStore()

const projectId = computed(() =>
  typeof route.params.projectId === 'string' ? route.params.projectId.trim() : ''
)
const projectsUseRuntimeApi = computed(() => resolvePlatformClientScope('projects') === 'v2')
const activeProjects = computed(() =>
  projectsUseRuntimeApi.value ? workspaceStore.runtimeProjects : workspaceStore.projects
)
const activeProjectId = computed(() =>
  projectsUseRuntimeApi.value ? workspaceStore.runtimeProjectId : workspaceStore.currentProjectId
)

const project = computed(() =>
  activeProjects.value.find((item) => item.id === projectId.value) ?? null
)

const members = ref<ManagementProjectMember[]>([])
const loadingMembers = ref(false)
const membersError = ref('')

const stats = computed(() => [
  {
    label: '项目名称',
    value: project.value?.name || '未找到',
    hint: project.value?.id || '--',
    icon: 'folder',
    tone: 'primary'
  },
  {
    label: '成员数量',
    value: members.value.length,
    hint: '来自项目成员接口',
    icon: 'users',
    tone: 'success'
  },
  {
    label: '管理员',
    value: members.value.filter((item) => item.role === 'admin').length,
    hint: '当前项目 admin 角色成员',
    icon: 'shield',
    tone: 'warning'
  },
  {
    label: '当前工作区',
    value: activeProjectId.value === project.value?.id ? '已对齐' : '未对齐',
    hint:
      activeProjectId.value === project.value?.id
        ? '当前工作区已指向本项目'
        : '可在这里切换工作区项目',
    icon: 'project',
    tone: 'danger'
  }
])

async function handleCopyProjectId() {
  if (!project.value) {
    return
  }

  const copied = await copyText(project.value.id)
  uiStore.pushToast({
    type: copied ? 'success' : 'warning',
    title: copied ? '已复制项目 ID' : '复制失败',
    message: copied ? project.value.id : '当前环境不支持自动复制，请手动复制。'
  })
}

function focusProject() {
  if (!project.value) {
    return
  }

  if (projectsUseRuntimeApi.value) {
    workspaceStore.setRuntimeProjectId(project.value.id)
  } else {
    workspaceStore.setProjectId(project.value.id)
  }
  uiStore.pushToast({
    type: 'success',
    title: '已切换当前项目',
    message: project.value.name
  })
}

function openAudit() {
  if (!project.value) {
    return
  }

  if (projectsUseRuntimeApi.value) {
    workspaceStore.setRuntimeProjectId(project.value.id)
  } else {
    workspaceStore.setProjectId(project.value.id)
  }
  void router.push('/workspace/audit')
}

async function loadMembers() {
  if (!projectId.value) {
    members.value = []
    membersError.value = ''
    return
  }

  loadingMembers.value = true
  membersError.value = ''

  try {
    members.value = await listProjectMembers(
      projectId.value,
      undefined,
      projectsUseRuntimeApi.value ? { mode: 'runtime' } : undefined
    )
  } catch (loadError) {
    members.value = []
    membersError.value =
      loadError instanceof Error ? loadError.message : '项目成员加载失败'
  } finally {
    loadingMembers.value = false
  }
}

watch(
  () => projectId.value,
  () => {
    void loadMembers()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Projects"
      :title="project?.name || '项目详情'"
      description="项目详情页当前按真实后端能力收敛为概览入口，不硬造不存在的编辑接口。这里负责承接项目信息、成员预览和工作区跳转。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/projects')"
        >
          返回列表
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="!project"
          @click="handleCopyProjectId"
        >
          <BaseIcon
            name="copy"
            size="sm"
          />
          复制项目 ID
        </BaseButton>
        <BaseButton
          :disabled="!project"
          @click="focusProject"
        >
          <BaseIcon
            name="project"
            size="sm"
          />
          设为当前项目
        </BaseButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!project"
      icon="folder"
      title="未找到这个项目"
      description="当前工作区没有这条项目记录，或者你没有访问它的权限。"
    />

    <template v-else>
      <StateBanner
        v-if="membersError"
        title="项目成员加载失败"
        :description="membersError"
        variant="warning"
      />

      <div class="grid gap-4 xl:grid-cols-4">
        <MetricCard
          v-for="itemStat in stats"
          :key="itemStat.label"
          :label="itemStat.label"
          :value="itemStat.value"
          :hint="itemStat.hint"
          :icon="itemStat.icon"
          :tone="itemStat.tone"
        />
      </div>

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <SurfaceCard class="space-y-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                基础信息
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                旧版这里本来就是项目级入口，不承担复杂编辑。Vue 版保持这个口径，但把信息密度和入口动作做完整。
              </div>
            </div>
            <StatusPill tone="success">
              {{ project.status }}
            </StatusPill>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                项目 ID
              </div>
              <div class="mt-2 break-all text-sm font-semibold text-gray-900 dark:text-white">
                {{ project.id }}
              </div>
            </div>
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                短标识
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ shortId(project.id) }}
              </div>
            </div>
          </div>

          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              项目名称
            </div>
            <div class="mt-2 text-base font-semibold text-gray-900 dark:text-white">
              {{ project.name }}
            </div>
          </div>

          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              项目描述
            </div>
            <div class="mt-2 whitespace-pre-wrap text-sm leading-7 text-gray-700 dark:text-dark-100">
              {{ project.description || '暂无描述' }}
            </div>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseButton
              variant="secondary"
              @click="void router.push(`/workspace/projects/${projectId}/members`)"
            >
              <BaseIcon
                name="users"
                size="sm"
              />
              成员管理
            </BaseButton>
            <BaseButton
              variant="secondary"
              @click="openAudit"
            >
              <BaseIcon
                name="audit"
                size="sm"
              />
              查看审计
            </BaseButton>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-lg font-semibold text-gray-900 dark:text-white">
                成员预览
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                后续正式成员管理页会在这里继续展开。
              </div>
            </div>
            <BaseButton
              variant="ghost"
              :disabled="loadingMembers"
              @click="loadMembers"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              刷新成员
            </BaseButton>
          </div>

          <div
            v-if="loadingMembers"
            class="space-y-3"
          >
            <div
              v-for="index in 3"
              :key="index"
              class="pw-card-glass h-20 animate-pulse"
            />
          </div>

          <EmptyState
            v-else-if="members.length === 0"
            icon="users"
            title="当前没有可展示的成员"
            description="如果这是新项目，成员列表可能还没建立；后续进入成员管理页会补更完整的增删改流程。"
          />

          <div
            v-else
            class="space-y-3"
          >
            <div
              v-for="member in members"
              :key="member.user_id"
              class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-dark-700 dark:bg-dark-900/70"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ member.username }}
                  </div>
                  <div class="mt-1 break-all text-xs text-gray-500 dark:text-dark-300">
                    {{ member.user_id }}
                  </div>
                </div>
                <StatusPill :tone="getRoleTone(member.role)">
                  {{ member.role }}
                </StatusPill>
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>
    </template>
  </section>
</template>
