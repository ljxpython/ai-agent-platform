<script setup lang="ts">
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useWorkspaceStore } from '@/stores/workspace'
import { createLanggraphAuthorizedFetch } from '@/services/langgraph/client'
import { createSessionService, hasThreadAction, type ChatThread } from '@/services/threads/session.service'
import ThreadAccessControl from '../components/ThreadAccessControl.vue'
import MessageContent from '../components/MessageContent.vue'
import ApprovalPanel from '../components/ApprovalPanel.vue'
import { asObject, contentItems } from '../transcript'
import { buildReviewResponses, parseReviews, type ReviewDraft } from '../approvals'

const route = useRoute()
const workspace = useWorkspaceStore()
const authorization = useAuthorization()
const projectInput = ref('')
const threadInput = ref('')
const target = ref<{ projectId: string; threadId: string }>()
const thread = shallowRef<ChatThread>()
const state = shallowRef<Awaited<ReturnType<ReturnType<typeof createSessionService>['state']>>>()
const busy = ref(false)
const error = ref('')
const notice = ref('')
const confirmDelete = ref(false)
let epoch = 0
let disposed = false
const routeProject = computed(() => typeof route.params.projectId === 'string' ? route.params.projectId : '')
const projectId = computed(() => routeProject.value || projectInput.value)
const canGovern = computed(() => authorization.can('platform.super_admin.manage') ||
  (!!projectId.value && authorization.can('project.runtime.write', projectId.value)))
const projectOptions = computed(() => workspace.projects.filter(project => project.status !== 'deleted')
  .map(project => ({ value: project.id, label: project.name })))
const reviews = computed(() => parseReviews(state.value?.interrupts ?? []))
const messages = computed(() => {
  const values = asObject(state.value?.values)
  return Array.isArray(values.messages) ? values.messages.map((value, index) => {
    const message = asObject(value)
    return { key: String(message.id || index), role: String(message.role || message.type || '消息'), blocks: contentItems(message.content, String(index)) }
  }) : []
})
const service = () => createSessionService(createLanggraphAuthorizedFetch(), target.value!.projectId)

function clearContent() { thread.value = undefined; state.value = undefined }
watch([projectId, threadInput, canGovern], () => {
  ++epoch; target.value = undefined; clearContent(); confirmDelete.value = false; error.value = ''; notice.value = ''; busy.value = false
})

async function refresh() {
  if (!target.value || !canGovern.value || busy.value || disposed) return
  const current = epoch
  const id = target.value.threadId
  busy.value = true
  error.value = ''
  try {
    const api = service()
    const loaded = await api.get(id)
    const snapshot = await api.state(id)
    if (current !== epoch || disposed) return
    thread.value = loaded; state.value = snapshot
  } catch (cause) {
    if (current !== epoch || disposed) return
    clearContent()
    error.value = cause instanceof Error ? cause.message : '读取失败，请先申请临时访问'
  } finally { if (current === epoch && !disposed) busy.value = false }
}
function locate() {
  if (!canGovern.value || !projectId.value || !threadInput.value.trim()) return
  ++epoch; clearContent(); notice.value = ''
  target.value = { projectId: projectId.value, threadId: threadInput.value.trim() }
  void refresh()
}
function accessUpdated() { ++epoch; busy.value = false; clearContent(); void refresh() }
async function remove() {
  if (!target.value || !canGovern.value || busy.value) return
  const current = epoch
  busy.value = true; error.value = ''
  try {
    await service().remove(target.value.threadId)
    if (current !== epoch || disposed) return
    clearContent(); target.value = undefined; confirmDelete.value = false; notice.value = '会话已删除。'
  } catch (cause) {
    if (current === epoch && !disposed) { clearContent(); error.value = cause instanceof Error ? cause.message : '删除失败' }
  } finally { if (current === epoch && !disposed) busy.value = false }
}
async function approve(drafts: Record<string, ReviewDraft[]>) {
  if (!target.value || busy.value || !canGovern.value || !hasThreadAction(thread.value, 'approve')) return
  const current = epoch
  const id = target.value.threadId
  const before = reviews.value
  busy.value = true; error.value = ''
  try {
    const api = service()
    const latest = parseReviews((await api.state(id)).interrupts ?? [])
    if (current !== epoch || disposed) return
    if (latest.length !== before.length || before.some(item => !latest.some(value => value.id === item.id && value.fingerprint === item.fingerprint)))
      throw new Error('审批内容已变化，请重新读取后确认')
    await api.resume(id, buildReviewResponses(latest, drafts))
    if (current !== epoch || disposed) return
    state.value = undefined
    notice.value = '审批已提交，请重新读取查看最新状态。'
  } catch (cause) {
    if (current === epoch && !disposed) { clearContent(); error.value = cause instanceof Error ? cause.message : '审批失败' }
  } finally { if (current === epoch && !disposed) busy.value = false }
}
const refreshVisible = () => { if (!document.hidden) void refresh() }
const timer = setInterval(refreshVisible, 60_000)
window.addEventListener('focus', refreshVisible)
window.addEventListener('platform-access-denied', refreshVisible)
document.addEventListener('visibilitychange', refreshVisible)
onScopeDispose(() => {
  disposed = true; ++epoch; clearInterval(timer)
  window.removeEventListener('focus', refreshVisible)
  window.removeEventListener('platform-access-denied', refreshVisible)
  document.removeEventListener('visibilitychange', refreshVisible)
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      title="会话治理"
      description="按工单中的项目和会话 ID 定位对象。管理员默认不能读取私有内容；临时访问必须说明原因并留审计。"
    />
    <SurfaceCard>
      <form
        class="space-y-4"
        @submit.prevent="locate"
      >
        <label
          v-if="!routeProject"
          class="block text-sm"
        >项目<BaseSelect
          v-model="projectInput"
          :options="projectOptions"
          placeholder="选择项目"
        /></label>
        <label class="block text-sm">会话 ID<input
          v-model="threadInput"
          required
          class="mt-1 w-full rounded border p-2 dark:bg-dark-900"
        ></label>
        <BaseButton
          type="submit"
          :disabled="busy || !canGovern || !projectId"
        >
          定位会话
        </BaseButton>
      </form>
    </SurfaceCard>
    <StateBanner
      v-if="error"
      title="无法完成操作"
      :description="error"
      variant="warning"
    />
    <p
      v-if="notice"
      role="status"
    >
      {{ notice }}
    </p>
    <SurfaceCard v-if="target && canGovern">
      <div class="flex flex-wrap items-center gap-3">
        <ThreadAccessControl
          :key="`${target.projectId}:${target.threadId}`"
          :project-id="target.projectId"
          :thread-id="target.threadId"
          :can-share="false"
          :can-takeover="canGovern"
          @updated="accessUpdated"
        />
        <BaseButton
          variant="secondary"
          :disabled="busy"
          @click="refresh"
        >
          重新读取
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="busy"
          @click="confirmDelete = true"
        >
          删除会话
        </BaseButton>
      </div>
      <p
        v-if="busy"
        role="status"
      >
        正在处理…
      </p>
      <p
        v-if="!thread"
        class="mt-3 text-sm"
      >
        私有会话须先申请临时读取。删除权限不代表可以读取内容。
      </p>
    </SurfaceCard>
    <template v-if="thread && target && canGovern">
      <SurfaceCard>
        <h2 class="font-semibold">
          {{ thread.metadata?.title || target.threadId }}
        </h2>
        <p v-if="!messages.length && !reviews.length" class="mt-2 text-sm">
          会话已读取，暂无消息或待审批项。
        </p>
      </SurfaceCard>
      <ApprovalPanel
        v-if="reviews.length"
        :reviews="reviews"
        :disabled="busy || !hasThreadAction(thread, 'approve')"
        @submit="approve"
      />
      <SurfaceCard
        v-for="message in messages"
        :key="message.key"
      >
        <p class="mb-2 text-sm font-semibold">
          {{ message.role }}
        </p>
        <MessageContent
          :blocks="message.blocks"
          :project-id="target.projectId"
          :thread-id="target.threadId"
        />
      </SurfaceCard>
    </template>
    <BaseDialog
      :show="confirmDelete"
      title="确认删除会话"
      @close="confirmDelete = false"
    >
      <p>删除此会话及其运行数据后无法恢复。请核对工单中的会话 ID：{{ target?.threadId }}</p>
      <BaseButton
        variant="secondary"
        :disabled="busy"
        @click="confirmDelete = false"
      >
        取消
      </BaseButton>
      <BaseButton
        :disabled="busy || !canGovern"
        @click="remove"
      >
        确认删除
      </BaseButton>
    </BaseDialog>
  </section>
</template>
