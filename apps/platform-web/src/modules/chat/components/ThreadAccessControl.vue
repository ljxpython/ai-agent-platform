<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import { listProjectMembers } from '@/services/members/members.service'
import { shareThread, takeOverThread, endThreadTakeover, type SharedThreadAction, type TakeoverCategory } from '@/services/threads/access.service'
import { createSessionService } from '@/services/threads/session.service'
import { createLanggraphAuthorizedFetch } from '@/services/langgraph/client'
import type { ManagementProjectMember } from '@/types/management'

const props = defineProps<{
  projectId: string
  threadId: string
  canShare: boolean
  canTakeover: boolean
  showTakeoverButton?: boolean
}>()

const emit = defineEmits<{
  updated: []
}>()

const mode = ref<'share' | 'takeover' | null>(null)
const members = ref<ManagementProjectMember[]>([])
const target = ref('project')
const actions = ref<SharedThreadAction[]>(['read'])
const grants = ref<Record<string, SharedThreadAction[]>>({})
const busy = ref(false)
const shareLoaded = ref(false)
const error = ref('')
const notice = ref('')
const category = ref<TakeoverCategory>('user_support')
const reason = ref('')
const reference = ref('')
const duration = ref(15)
let epoch = 0

const targets = computed(() => [
  { value: 'project', label: '当前项目所有成员' },
  ...members.value.map(member => ({ value: member.user_id, label: member.username })),
  ...Object.keys(grants.value)
    .filter(id => id !== 'project' && grants.value[id]?.length && !members.value.some(member => member.user_id === id))
    .map(id => ({ value: id, label: `已离开项目（${id}，仅可撤销）` })),
])

const targetLeft = computed(() => target.value !== 'project' && !members.value.some(member => member.user_id === target.value))

const actionOptions = computed(() => [
  { value: 'read', label: '读取', desc: '可查看全部历史对话、步骤与产物' },
  { value: 'comment', label: '发送消息', desc: '可向该会话继续提问或交互' },
  { value: 'edit', label: '编辑', desc: '可回退并编辑前序对话内容' },
  ...(target.value === 'project' ? [] : [{ value: 'share', label: '转授权', desc: '可将此会话进一步共享给他人' }]),
  ...(members.value.find(member => member.user_id === target.value)?.role === 'project_admin' ? [{ value: 'delete', label: '删除（仅管理员）', desc: '允许删除此会话记录' }] : []),
])

// 格式化已授权名单列表
const grantedList = computed(() => {
  const result: Array<{
    id: string
    name: string
    isProject: boolean
    isDeparted: boolean
    role?: string
    actions: SharedThreadAction[]
  }> = []

  // 1. 项目全员
  if (grants.value.project && grants.value.project.length > 0) {
    result.push({
      id: 'project',
      name: '当前项目所有成员',
      isProject: true,
      isDeparted: false,
      actions: grants.value.project
    })
  }

  // 2. 个人成员
  Object.keys(grants.value).forEach(id => {
    if (id === 'project') return
    const acts = grants.value[id]
    if (!acts || acts.length === 0) return
    const mem = members.value.find(m => m.user_id === id)
    result.push({
      id,
      name: mem ? mem.username : `已离开成员 (${id})`,
      isProject: false,
      isDeparted: !mem,
      role: mem?.role,
      actions: acts
    })
  })

  return result
})

watch(target, () => {
  actions.value = [...(grants.value[target.value] || ['read'])]
})

watch(() => [props.projectId, props.threadId], () => {
  epoch++
  mode.value = null
  error.value = ''
  notice.value = ''
  busy.value = false
})

async function openShare() {
  if (!props.canShare || busy.value) return
  mode.value = 'share'
  error.value = ''
  notice.value = ''
  busy.value = true
  shareLoaded.value = false
  grants.value = {}
  members.value = []
  const current = epoch
  try {
    const service = createSessionService(createLanggraphAuthorizedFetch(), props.projectId)
    const [people, thread] = await Promise.all([listProjectMembers(props.projectId), service.get(props.threadId)])
    if (current !== epoch) return
    members.value = people
    grants.value = {
      ...(thread.metadata?.shared_actions as Record<string, SharedThreadAction[]> || {}),
      project: (thread.metadata?.project_actions as SharedThreadAction[] || [])
    }
    target.value = 'project'
    actions.value = [...(grants.value.project || ['read'])]
    shareLoaded.value = true
  } catch (cause) {
    if (current === epoch) error.value = cause instanceof Error ? cause.message : '读取共享权限失败'
  } finally {
    if (current === epoch) busy.value = false
  }
}

function openTakeover() {
  if (!props.canTakeover) return
  mode.value = 'takeover'
  error.value = ''
  notice.value = ''
}

async function quickRevoke(targetId: string) {
  target.value = targetId
  await save(true)
}

function quickSelect(targetId: string) {
  target.value = targetId
}

async function save(revoke = false) {
  if (busy.value) return
  if (mode.value === 'share' && (!props.canShare || !shareLoaded.value || (targetLeft.value && !revoke))) return
  if (mode.value === 'takeover' && !props.canTakeover) return
  if (mode.value === null) return
  busy.value = true
  error.value = ''
  notice.value = ''
  const current = epoch
  try {
    if (mode.value === 'share') {
      const next = revoke ? [] : [...new Set<SharedThreadAction>(['read', ...actions.value])]
      await shareThread(props.projectId, props.threadId, target.value === 'project' ? null : target.value, next)
      if (current !== epoch) return
      grants.value[target.value] = next
      notice.value = revoke ? '已撤销所选对象的共享权限；其他授权不变。' : '共享权限已保存。'
    } else if (revoke) {
      await endThreadTakeover(props.projectId, props.threadId)
      if (current !== epoch) return
      notice.value = '临时访问已结束。'
    } else {
      const grant = await takeOverThread(props.projectId, props.threadId, {
        category: category.value,
        reason: reason.value,
        reference: reference.value,
        duration_minutes: duration.value
      })
      if (current !== epoch) return
      notice.value = `临时读取已授权，${new Date(grant.expires_at * 1000).toLocaleTimeString()} 到期。请重新打开此会话。`
    }
    window.dispatchEvent(new Event('thread-access-updated'))
    emit('updated')
  } catch (cause) {
    if (current === epoch) error.value = cause instanceof Error ? cause.message : '权限操作失败'
  } finally {
    if (current === epoch) busy.value = false
  }
}

defineExpose({
  openShare,
  openTakeover
})
</script>

<template>
  <div class="inline-flex shrink-0 items-center gap-1.5">
    <button
      v-if="canShare"
      type="button"
      class="inline-flex h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-gray-200/70 bg-white px-2 text-xs font-medium text-gray-700 shadow-2xs hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-900 dark:text-dark-200 dark:hover:text-white transition-colors"
      title="分享此会话给项目成员"
      @click="openShare"
    >
      <BaseIcon
        name="users"
        size="xs"
      />
      <span>分享</span>
    </button>
    <button
      v-if="canTakeover && showTakeoverButton"
      type="button"
      class="inline-flex h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-amber-200/80 bg-amber-50/70 px-2 text-xs font-medium text-amber-800 shadow-2xs hover:bg-amber-100/70 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/40 transition-colors"
      title="管理员临时安全接管此会话"
      @click="openTakeover"
    >
      <BaseIcon
        name="shield"
        size="xs"
      />
      <span>临时访问</span>
    </button>

    <BaseDialog
      :show="mode !== null"
      :title="mode === 'share' ? '会话共享与协同权限' : '管理员临时安全接管'"
      width="normal"
      @close="mode = null"
    >
      <form
        class="space-y-5"
        @submit.prevent="save()"
      >
        <!-- 共享模式 -->
        <template v-if="mode === 'share'">
          <!-- 提示条 -->
          <div class="flex items-start gap-2.5 rounded-xl border border-blue-100 bg-blue-50/60 p-3 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-200">
            <BaseIcon
              name="info"
              size="sm"
              class="mt-0.5 shrink-0 text-blue-600 dark:text-blue-400"
            />
            <div class="leading-relaxed">
              <span class="font-semibold">会话安全隔离说明：</span>
              默认仅本人可见。共享仅授予会话浏览或发言权，<strong>绝不会</strong>授予本地终端操作、全权执行或高危动作审批权限。
            </div>
          </div>

          <!-- 授权配置区 -->
          <div class="rounded-xl border border-gray-200/80 bg-gray-50/60 p-4 space-y-4 dark:border-dark-700 dark:bg-dark-900/50">
            <div>
              <label class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200">
                选择共享成员或范围
              </label>
              <BaseSelect
                v-model="target"
                :options="targets"
                :disabled="busy"
              />
              <p
                v-if="targetLeft"
                class="mt-1 text-xs text-amber-600 dark:text-amber-400"
              >
                ⚠️ 该用户已离开项目，不可赋予新权限，仅支持撤销已有授权。
              </p>
            </div>

            <fieldset
              :disabled="busy || targetLeft"
              class="space-y-2"
            >
              <legend class="mb-1 text-xs font-semibold text-gray-700 dark:text-dark-200">
                授予的权限动作（保存时自动包含读取）
              </legend>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <label
                  v-for="option in actionOptions"
                  :key="option.value"
                  class="flex cursor-pointer items-start gap-2.5 rounded-lg border p-2.5 transition-all text-xs"
                  :class="[
                    actions.includes(option.value as SharedThreadAction) || option.value === 'read'
                      ? 'border-primary-500/50 bg-primary-50/40 text-primary-950 dark:border-primary-800 dark:bg-primary-950/30 dark:text-primary-200 font-medium'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'
                  ]"
                >
                  <input
                    v-model="actions"
                    type="checkbox"
                    :value="option.value"
                    :disabled="option.value === 'read'"
                    class="mt-0.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-dark-600 dark:bg-dark-800"
                  >
                  <div class="min-w-0 flex-1">
                    <div class="font-medium text-gray-900 dark:text-white">
                      {{ option.label }}
                    </div>
                    <div class="text-[11px] text-gray-500 dark:text-dark-400">
                      {{ option.desc }}
                    </div>
                  </div>
                </label>
              </div>
            </fieldset>

            <div class="flex items-center justify-between pt-1 border-t border-gray-200/60 dark:border-dark-700">
              <span class="text-xs text-gray-500 dark:text-dark-400">
                配置完成后点击右侧按钮生效
              </span>
              <div class="flex items-center gap-2">
                <BaseButton
                  v-if="grants[target]?.length"
                  variant="secondary"
                  size="sm"
                  type="button"
                  :disabled="busy || !shareLoaded"
                  @click="save(true)"
                >
                  撤销所选共享
                </BaseButton>
                <BaseButton
                  size="sm"
                  type="submit"
                  :disabled="busy || !shareLoaded || targetLeft"
                >
                  {{ busy ? '处理中…' : '保存共享' }}
                </BaseButton>
              </div>
            </div>
          </div>

          <!-- 已生效授权名单展示区 -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-gray-700 dark:text-dark-200">
                已生效的共享权限清单 ({{ grantedList.length }})
              </span>
              <span class="text-[11px] text-gray-400">点击用户可直接编辑或撤销</span>
            </div>

            <div
              v-if="grantedList.length === 0"
              class="rounded-xl border border-dashed border-gray-200 p-6 text-center text-xs text-gray-400 dark:border-dark-700"
            >
              当前会话尚未向任何人共享，仅本人可访问。
            </div>

            <div
              v-else
              class="max-h-48 overflow-y-auto space-y-1.5 pr-0.5"
            >
              <div
                v-for="item in grantedList"
                :key="item.id"
                class="flex items-center justify-between rounded-xl border border-gray-200/70 bg-white px-3 py-2 transition-all hover:border-gray-300 dark:border-dark-700 dark:bg-dark-900"
                :class="target === item.id ? 'ring-1 ring-primary-500/50 border-primary-500' : ''"
              >
                <div
                  class="flex min-w-0 items-center gap-2.5 cursor-pointer flex-1"
                  @click="quickSelect(item.id)"
                >
                  <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-medium text-gray-600 dark:bg-dark-800 dark:text-dark-200">
                    <BaseIcon
                      :name="item.isProject ? 'users' : 'user'"
                      size="xs"
                    />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5">
                      <span class="truncate text-xs font-medium text-gray-900 dark:text-white">
                        {{ item.name }}
                      </span>
                      <span
                        v-if="item.role"
                        class="rounded bg-gray-100 px-1 py-0.2 text-[10px] text-gray-500 dark:bg-dark-800 dark:text-dark-400"
                      >
                        {{ item.role === 'project_admin' ? '管理员' : '成员' }}
                      </span>
                      <span
                        v-if="item.isDeparted"
                        class="rounded bg-rose-50 px-1 py-0.2 text-[10px] text-rose-600 dark:bg-rose-950/40 dark:text-rose-400"
                      >
                        已离开
                      </span>
                    </div>
                    <div class="flex flex-wrap gap-1 mt-0.5">
                      <span
                        v-for="act in item.actions"
                        :key="act"
                        class="rounded-full bg-blue-50 px-1.5 py-0.2 text-[9px] font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                      >
                        {{ act === 'read' ? '读取' : act === 'comment' ? '提问' : act === 'edit' ? '编辑' : act === 'share' ? '转授' : '删除' }}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  class="ml-2 inline-flex h-6 items-center gap-1 rounded-md px-2 text-xs font-medium text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/30 transition-colors"
                  title="撤销此成员的所有共享权限"
                  :disabled="busy"
                  @click="quickRevoke(item.id)"
                >
                  <BaseIcon
                    name="x"
                    size="xs"
                  />
                  <span>撤销</span>
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- 管理员临时安全接管模式 -->
        <template v-else>
          <div class="flex items-start gap-2.5 rounded-xl border border-amber-200/80 bg-amber-50/70 p-3 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            <BaseIcon
              name="shield"
              size="sm"
              class="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400"
            />
            <div class="leading-relaxed">
              <strong>审计与合规提示：</strong>
              临时接管仅用于安全应急、合规调查或用户明确授权的技术排障。只授予临时读取权限，所有访问行为将永久记录入平台审计日志。排障完成后请立即结束。
            </div>
          </div>

          <div class="space-y-3.5 text-xs">
            <div>
              <label class="mb-1 block font-semibold text-gray-700 dark:text-dark-200">用途类别</label>
              <BaseSelect
                v-model="category"
                :disabled="busy"
                :options="[
                  { value: 'user_support', label: '用户授权技术排障' },
                  { value: 'security_incident', label: '安全应急事件' },
                  { value: 'compliance', label: '合规与审计调查' },
                  { value: 'handover', label: '紧急工作交接' }
                ]"
              />
            </div>

            <div>
              <label class="mb-1 block font-semibold text-gray-700 dark:text-dark-200">关联工单 / 审批编号</label>
              <input
                v-model="reference"
                required
                minlength="3"
                maxlength="200"
                placeholder="例如：SEC-2026-0922 或 TICKET-8891"
                :disabled="busy"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-900 dark:text-white"
              >
            </div>

            <div>
              <label class="mb-1 block font-semibold text-gray-700 dark:text-dark-200">具体申请事由</label>
              <textarea
                v-model="reason"
                required
                minlength="10"
                maxlength="1000"
                rows="3"
                placeholder="请详细说明接管此会话的具体原因与必要性（至少10个字符）…"
                :disabled="busy"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-900 dark:text-white"
              />
            </div>

            <div>
              <label class="mb-1 block font-semibold text-gray-700 dark:text-dark-200">接管有效期（1 — 60 分钟）</label>
              <input
                v-model.number="duration"
                type="number"
                min="1"
                max="60"
                step="1"
                required
                :disabled="busy"
                class="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-900 focus:border-primary-500 focus:outline-none dark:border-dark-700 dark:bg-dark-900 dark:text-white"
              >
            </div>
          </div>

          <div class="flex justify-end gap-2 pt-2 border-t border-gray-100 dark:border-dark-800">
            <BaseButton
              variant="secondary"
              type="button"
              :disabled="busy"
              @click="save(true)"
            >
              立即结束临时访问
            </BaseButton>
            <BaseButton
              type="submit"
              :disabled="busy"
            >
              {{ busy ? '处理中…' : '申请临时读取' }}
            </BaseButton>
          </div>
        </template>

        <!-- 错误与成功通知 -->
        <p
          v-if="error"
          role="alert"
          class="rounded-lg bg-red-50 p-2.5 text-xs text-red-600 dark:bg-red-950/40 dark:text-red-400"
        >
          {{ error }}
        </p>
        <p
          v-if="notice"
          role="status"
          class="rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
        >
          {{ notice }}
        </p>
      </form>
    </BaseDialog>
  </div>
</template>
