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

const props = defineProps<{ projectId: string; threadId: string; canShare: boolean; canTakeover: boolean }>()
const emit = defineEmits<{ updated: [] }>()
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
  { value: 'read', label: '读取' }, { value: 'comment', label: '发送消息' }, { value: 'edit', label: '编辑' },
  ...(target.value === 'project' ? [] : [{ value: 'share', label: '转授权' }]),
  ...(members.value.find(member => member.user_id === target.value)?.role === 'project_admin' ? [{ value: 'delete', label: '删除（仅管理员）' }] : []),
])
watch(target, () => { actions.value = [...(grants.value[target.value] || ['read'])] })
watch(() => [props.projectId, props.threadId], () => { epoch++; mode.value = null; error.value = ''; notice.value = ''; busy.value = false })

async function openShare() {
  if (!props.canShare || busy.value) return
  mode.value = 'share'; error.value = ''; notice.value = ''; busy.value = true
  shareLoaded.value = false; grants.value = {}; members.value = []
  const current = epoch
  try {
    const service = createSessionService(createLanggraphAuthorizedFetch(), props.projectId)
    const [people, thread] = await Promise.all([listProjectMembers(props.projectId), service.get(props.threadId)])
    if (current !== epoch) return
    members.value = people
    grants.value = { ...(thread.metadata?.shared_actions as Record<string, SharedThreadAction[]> || {}), project: (thread.metadata?.project_actions as SharedThreadAction[] || []) }
    target.value = 'project'
    actions.value = [...grants.value.project!]
    shareLoaded.value = true
  } catch (cause) { if (current === epoch) error.value = cause instanceof Error ? cause.message : '读取共享权限失败' }
  finally { if (current === epoch) busy.value = false }
}

async function save(revoke = false) {
  if (busy.value) return
  if (mode.value === 'share' && (!props.canShare || !shareLoaded.value || (targetLeft.value && !revoke))) return
  if (mode.value === 'takeover' && !props.canTakeover) return
  if (mode.value === null) return
  busy.value = true; error.value = ''; notice.value = ''
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
      const grant = await takeOverThread(props.projectId, props.threadId, { category: category.value, reason: reason.value, reference: reference.value, duration_minutes: duration.value })
      if (current !== epoch) return
      notice.value = `临时读取已授权，${new Date(grant.expires_at * 1000).toLocaleTimeString()} 到期。请重新打开此会话。`
    }
    window.dispatchEvent(new Event('thread-access-updated'))
    emit('updated')
  } catch (cause) { if (current === epoch) error.value = cause instanceof Error ? cause.message : '权限操作失败' }
  finally { if (current === epoch) busy.value = false }
}
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
      v-if="canTakeover"
      type="button"
      class="inline-flex h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-amber-200/80 bg-amber-50/70 px-2 text-xs font-medium text-amber-800 shadow-2xs hover:bg-amber-100/70 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/40 transition-colors"
      title="管理员临时安全接管此会话"
      @click="mode = 'takeover'; error = ''; notice = ''"
    >
      <BaseIcon
        name="shield"
        size="xs"
      />
      <span>临时访问</span>
    </button>
    <BaseDialog
      :show="mode !== null"
      :title="mode === 'share' ? '会话共享权限' : '管理员临时读取'"
      @close="mode = null"
    >
      <form
        class="space-y-4"
        @submit.prevent="save()"
      >
        <template v-if="mode === 'share'">
          <p class="text-sm text-gray-600 dark:text-dark-300">
            默认仅本人可见。共享不会授予终端、全权执行或审批权限。
          </p>
          <label class="block text-sm">共享对象<BaseSelect
            v-model="target"
            :options="targets"
            :disabled="busy"
          /></label>
          <fieldset
            :disabled="busy"
            class="flex flex-wrap gap-4"
          >
            <legend class="mb-2 text-sm">
              独立动作（保存时始终包含读取）
            </legend>
            <label
              v-for="option in actionOptions"
              :key="option.value"
              class="flex items-center gap-2 text-sm"
            >
              <input
                v-model="actions"
                type="checkbox"
                :value="option.value"
              >{{ option.label }}
            </label>
          </fieldset>
          <p class="text-sm">
            已有个人授权：{{ Object.keys(grants).filter(key => key !== 'project' && grants[key]?.length).map(key => members.find(member => member.user_id === key)?.username || key).join('、') || '无' }}
          </p>
        </template>
        <template v-else>
          <p class="text-sm text-gray-600 dark:text-dark-300">
            仅用于安全调查、合规、用户明确授权的排障或必要交接。只增加读取权限，所有访问留审计；完成后请立即结束。
          </p>
          <label class="block text-sm">用途<BaseSelect
            v-model="category"
            :disabled="busy"
            :options="[{ value: 'user_support', label: '用户授权排障' }, { value: 'security_incident', label: '安全事件' }, { value: 'compliance', label: '合规调查' }, { value: 'handover', label: '必要交接' }]"
          /></label>
          <label class="block text-sm">工单或请求号<input
            v-model="reference"
            required
            minlength="3"
            maxlength="200"
            :disabled="busy"
            class="mt-1 w-full rounded border p-2 dark:bg-dark-900"
          ></label>
          <label class="block text-sm">具体原因<textarea
            v-model="reason"
            required
            minlength="10"
            maxlength="1000"
            :disabled="busy"
            class="mt-1 w-full rounded border p-2 dark:bg-dark-900"
          /></label>
          <label class="block text-sm">有效期（1—60 分钟）<input
            v-model.number="duration"
            type="number"
            min="1"
            max="60"
            step="1"
            required
            :disabled="busy"
            class="mt-1 w-full rounded border p-2 dark:bg-dark-900"
          ></label>
        </template>
        <p
          v-if="error"
          role="alert"
          class="text-sm text-red-600"
        >
          {{ error }}
        </p>
        <p
          v-if="notice"
          role="status"
          class="text-sm text-green-700"
        >
          {{ notice }}
        </p>
        <div class="flex flex-wrap justify-end gap-2">
          <BaseButton
            variant="secondary"
            :disabled="busy || (mode === 'share' && !shareLoaded)"
            @click="save(true)"
          >
            {{ mode === 'share' ? '撤销所选共享' : '立即结束临时访问' }}
          </BaseButton>
          <BaseButton
            type="submit"
            :disabled="busy || (mode === 'share' && (!shareLoaded || targetLeft))"
          >
            {{ busy ? '处理中…' : mode === 'share' ? '保存共享' : '申请临时读取' }}
          </BaseButton>
        </div>
      </form>
    </BaseDialog>
  </div>
</template>
