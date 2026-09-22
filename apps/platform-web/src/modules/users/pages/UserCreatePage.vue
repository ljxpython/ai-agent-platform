<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { formatPlatformRoleLabel } from '@/services/auth/permissions'
import { createUser } from '@/services/users/users.service'
import { getProjectAccess, listProjects } from '@/services/projects/projects.service'
import { upsertProjectMember } from '@/services/members/members.service'
import type { ManagementProject, ManagementUser, PlatformRole, ProjectRole } from '@/types/management'

interface ProjectAssignment {
  id: string
  projectId: string
  role: ProjectRole
  canBind: boolean
  checking: boolean
  error: string
}

const router = useRouter()
const authorization = useAuthorization()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const platformRole = ref<PlatformRole | ''>('')
const submitting = ref(false)
const error = ref('')
const notice = ref('')
const createdUser = ref<ManagementUser | null>(null)
const projects = ref<ManagementProject[]>([])
const projectAssignments = ref<ProjectAssignment[]>([])

const projectRoleOptions: Array<{ value: ProjectRole; label: string }> = [
  { value: 'project_executor', label: '项目执行者' },
  { value: 'project_editor', label: '项目编辑者' },
  { value: 'project_admin', label: '项目管理员' }
]

const platformRoleOptions: Array<{ value: PlatformRole | ''; label: string }> = [
  { value: '', label: '无平台角色' },
  { value: 'platform_viewer', label: formatPlatformRoleLabel('platform_viewer') },
  { value: 'platform_operator', label: formatPlatformRoleLabel('platform_operator') },
  { value: 'platform_super_admin', label: formatPlatformRoleLabel('platform_super_admin') }
]

function addProjectAssignment() {
  projectAssignments.value.push({
    id: `pa-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    projectId: '',
    role: 'project_executor',
    canBind: true,
    checking: false,
    error: ''
  })
}

function removeProjectAssignment(index: number) {
  projectAssignments.value.splice(index, 1)
}

function getAvailableProjectOptions(currentProjectId: string) {
  const selectedOtherProjectIds = new Set(
    projectAssignments.value
      .map((item) => item.projectId)
      .filter((id) => id && id !== currentProjectId)
  )

  return [
    { value: '', label: '请选择项目' },
    ...projects.value
      .filter((project) => !selectedOtherProjectIds.has(project.id))
      .map((project) => ({ value: project.id, label: project.name }))
  ]
}

async function onProjectChange(assignment: ProjectAssignment) {
  assignment.error = ''
  assignment.canBind = true
  if (!assignment.projectId) return

  assignment.checking = true
  try {
    const access = await getProjectAccess(assignment.projectId)
    assignment.canBind = access.permissions.includes('project.member.write')
    if (!assignment.canBind) {
      assignment.error = '你没有该项目的成员管理权限，创建后需由该项目管理员将其加入。'
    }
  } catch {
    assignment.error = '无法确认该项目成员管理权限'
  } finally {
    assignment.checking = false
  }
}

onMounted(async () => {
  try {
    projects.value = await listProjects()
  } catch {
    // 项目读取失败不阻断基础创建
  }
})

const normalizedUsername = computed(() => username.value.trim())
const assignedProjectCount = computed(() => projectAssignments.value.filter((i) => i.projectId).length)

const requestPreview = computed(() => ({
  username: normalizedUsername.value,
  password: password.value ? '********' : '',
  platform_roles: platformRole.value ? [platformRole.value] : [],
  is_super_admin: platformRole.value === 'platform_super_admin',
  projects: projectAssignments.value
    .filter((item) => item.projectId)
    .map((item) => {
      const proj = projects.value.find((p) => p.id === item.projectId)
      return {
        project_id: item.projectId,
        project_name: proj?.name || item.projectId,
        role: item.role
      }
    })
}))

const stats = computed(() => [
  {
    label: '用户名长度',
    value: normalizedUsername.value.length,
    hint: '后端限制 1-64 个字符',
    icon: 'user',
    tone: normalizedUsername.value.length > 0 ? 'success' : 'warning'
  },
  {
    label: '密码长度',
    value: password.value.length,
    hint: !password.value
      ? '必须至少 8 位'
      : password.value.length < 8
        ? '必须至少 8 位'
        : confirmPassword.value && password.value !== confirmPassword.value
          ? '两次密码不一致'
          : '必须至少 8 位',
    icon: 'lock',
    tone: password.value.length >= 8 && (!confirmPassword.value || password.value === confirmPassword.value) ? 'success' : 'danger'
  },
  {
    label: '关联项目',
    value: `${assignedProjectCount.value} 个`,
    hint: assignedProjectCount.value === 0 ? '支持创建时多选项目' : '创建成功后将自动批量加入',
    icon: 'folder',
    tone: assignedProjectCount.value > 0 ? 'primary' : 'neutral'
  }
])

const submitButtonText = computed(() => {
  if (submitting.value) return '创建与分配中...'
  if (!authorization.can('platform.user.create')) return '当前账号只读'
  if (assignedProjectCount.value > 0) {
    return `创建用户并加入 ${assignedProjectCount.value} 个项目`
  }
  return '创建用户'
})

async function handleSubmit() {
  if (createdUser.value || submitting.value) return
  if (!authorization.can('platform.user.create')) {
    error.value = '当前账号没有创建用户的权限'
    return
  }

  if (!normalizedUsername.value) {
    error.value = '用户名不能为空'
    return
  }

  if (password.value.length < 8) {
    error.value = '密码至少需要 8 个字符'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  const emptyAssignment = projectAssignments.value.find((item) => !item.projectId)
  if (emptyAssignment) {
    error.value = '请为添加的项目行选择具体项目，或删除未选择的项目行'
    return
  }

  const forbiddenAssignments = projectAssignments.value.filter((item) => !item.canBind)
  if (forbiddenAssignments.length > 0) {
    error.value = '选中的项目中包含你没有成员管理权限的项目，请移除后再提交'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const created = await createUser({
      username: normalizedUsername.value,
      password: password.value,
      platform_roles: platformRole.value ? [platformRole.value] : [],
      is_super_admin: platformRole.value === 'platform_super_admin'
    })

    createdUser.value = created
    password.value = ''
    confirmPassword.value = ''

    if (projectAssignments.value.length === 0) {
      notice.value = `已成功创建用户：${created.username}。`
      setTimeout(() => {
        void router.push('/workspace/users')
      }, 1200)
      return
    }

    const bindResults = await Promise.allSettled(
      projectAssignments.value.map(async (item) => {
        await upsertProjectMember({
          projectId: item.projectId,
          userId: created.id,
          role: item.role
        })
        const proj = projects.value.find((p) => p.id === item.projectId)
        return proj?.name || item.projectId
      })
    )

    const fulfilled = bindResults.filter((r): r is PromiseFulfilledResult<string> => r.status === 'fulfilled')
    const rejected = bindResults.filter((r): r is PromiseRejectedResult => r.status === 'rejected')

    if (rejected.length === 0) {
      notice.value = `已创建用户：${created.username}，并成功加入 ${fulfilled.length} 个项目。`
      setTimeout(() => {
        void router.push('/workspace/users')
      }, 1500)
    } else {
      error.value = `用户 ${created.username} 已创建成功，但有 ${rejected.length} 个项目绑定失败：${rejected.map((r) => (r.reason instanceof Error ? r.reason.message : '权限不足或网络异常')).join('；')}。可稍后从项目成员页处理。`
    }
  } catch (createError) {
    error.value = createError instanceof Error ? createError.message : '用户创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Users"
      title="新建用户"
      description="一站式设置账号基础信息，并可按需直接分配所属项目与项目角色。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/users')"
        >
          返回列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="操作未完成"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作已完成"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-3">
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

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
      <SurfaceCard class="space-y-6">
        <div>
          <div class="text-lg font-semibold text-gray-900 dark:text-white">
            创建表单
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
            填写账号基本信息，可按需一次性加入一个或多个项目。
          </div>
        </div>

        <form
          autocomplete="off"
          class="space-y-5"
          @submit.prevent="handleSubmit"
        >
          <label class="block">
            <span class="pw-input-label">用户名</span>
            <input
              v-model="username"
              name="new_username"
              autocomplete="off"
              autocapitalize="none"
              spellcheck="false"
              class="pw-input"
              placeholder="请输入用户名"
              :disabled="submitting || !authorization.can('platform.user.create')"
              maxlength="64"
            >
          </label>

          <label class="block">
            <span class="pw-input-label">密码</span>
            <input
              v-model="password"
              type="password"
              name="new_password"
              autocomplete="new-password"
              class="pw-input"
              placeholder="请输入至少 8 位密码"
              minlength="8"
              :disabled="submitting || !authorization.can('platform.user.create')"
            >
          </label>

          <label class="block">
            <span class="pw-input-label">确认密码</span>
            <input
              v-model="confirmPassword"
              type="password"
              name="confirm_password"
              autocomplete="new-password"
              class="pw-input"
              placeholder="请再次输入密码"
              minlength="8"
              :disabled="submitting || !authorization.can('platform.user.create')"
            >
          </label>

          <div>
            <span class="pw-input-label">平台角色</span>
            <BaseSelect
              v-model="platformRole"
              :disabled="submitting || !authorization.can('platform.user.role.write')"
              :options="platformRoleOptions"
            />
          </div>

          <!-- 多项目动态分配区 -->
          <div class="pt-2 border-t border-gray-100 dark:border-dark-700">
            <div class="mb-3 flex items-center justify-between">
              <div>
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  所属项目分配（可选）
                </div>
                <div class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
                  用户创建成功后将直接绑定加入，支持同时加入多个项目并分别设定角色。
                </div>
              </div>
              <BaseButton
                type="button"
                variant="secondary"
                size="sm"
                :disabled="submitting"
                @click="addProjectAssignment"
              >
                <BaseIcon
                  name="plus"
                  size="sm"
                />
                添加项目
              </BaseButton>
            </div>

            <!-- 空态 -->
            <div
              v-if="projectAssignments.length === 0"
              class="flex items-center justify-between rounded-2xl border border-dashed border-gray-200 bg-gray-50/60 px-4 py-3.5 text-sm text-gray-500 dark:border-dark-700 dark:bg-dark-900/40 dark:text-dark-300"
            >
              <span>暂未分配项目（创建后可由具体项目管理员按需添加）</span>
              <BaseButton
                type="button"
                variant="secondary"
                size="sm"
                :disabled="submitting"
                @click="addProjectAssignment"
              >
                <BaseIcon
                  name="plus"
                  size="sm"
                />
                关联项目
              </BaseButton>
            </div>

            <!-- 动态项目列表 -->
            <div
              v-else
              class="space-y-3"
            >
              <div
                v-for="(item, index) in projectAssignments"
                :key="item.id"
                class="rounded-2xl border border-gray-200/80 bg-gray-50/50 p-3.5 transition-all dark:border-dark-700 dark:bg-dark-900/50"
              >
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <div class="flex-1 min-w-0">
                    <span class="pw-input-label text-xs mb-1">目标项目</span>
                    <BaseSelect
                      v-model="item.projectId"
                      :options="getAvailableProjectOptions(item.projectId)"
                      :disabled="submitting"
                      @update:model-value="() => onProjectChange(item)"
                    />
                  </div>
                  <div class="w-full sm:w-44">
                    <span class="pw-input-label text-xs mb-1">项目角色</span>
                    <BaseSelect
                      v-model="item.role"
                      :options="projectRoleOptions"
                      :disabled="submitting || !item.canBind"
                    />
                  </div>
                  <div class="sm:self-end pb-0.5">
                    <button
                      type="button"
                      class="flex h-10 w-10 items-center justify-center rounded-xl text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors dark:hover:bg-red-950/30"
                      title="移除此项目"
                      :disabled="submitting"
                      @click="removeProjectAssignment(index)"
                    >
                      <BaseIcon
                        name="trash"
                        size="sm"
                      />
                    </button>
                  </div>
                </div>
                <div
                  v-if="item.error"
                  class="mt-2 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5"
                >
                  <BaseIcon
                    name="alert"
                    size="sm"
                    class="shrink-0"
                  />
                  <span>{{ item.error }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end pt-2">
            <BaseButton
              type="submit"
              :disabled="submitting || !authorization.can('platform.user.create')"
              @click="handleSubmit"
            >
              <BaseIcon
                name="users"
                size="sm"
              />
              {{ submitButtonText }}
            </BaseButton>
          </div>
        </form>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="text-lg font-semibold text-gray-900 dark:text-white">
          请求预览
        </div>
        <pre class="overflow-auto whitespace-pre-wrap break-words rounded-[24px] bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ JSON.stringify(requestPreview, null, 2) }}</pre>

        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 text-sm leading-7 text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200">
          一站式完成账号创建与项目分配。若个别项目因权限不足或网络异常未绑定成功，已创建的账号仍将安全保留，并给出明确提示。
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>
