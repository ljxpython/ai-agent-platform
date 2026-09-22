import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ThreadGovernancePage from './ThreadGovernancePage.vue'

const mocks = vi.hoisted(() => ({ get: vi.fn(), state: vi.fn(), remove: vi.fn(), resume: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: {} }) }))
vi.mock('@/composables/useAuthorization', () => ({ useAuthorization: () => ({ can: (permission: string) => permission === 'platform.super_admin.manage' }) }))
vi.mock('@/stores/workspace', () => ({ useWorkspaceStore: () => ({ projects: [{ id: 'p', name: '项目', status: 'active' }] }) }))
vi.mock('@/services/langgraph/client', () => ({ createLanggraphAuthorizedFetch: () => vi.fn() }))
vi.mock('@/services/threads/session.service', async importOriginal => ({
  ...await importOriginal<typeof import('@/services/threads/session.service')>(),
  createSessionService: () => mocks,
}))
let wrapper: ReturnType<typeof mount>
beforeEach(() => {
  vi.resetAllMocks()
  mocks.get.mockRejectedValue(new Error('需要临时访问'))
  mocks.state.mockResolvedValue({ values: { messages: [{ role: 'user', content: '私有正文' }] }, interrupts: [] })
  wrapper = mount(ThreadGovernancePage, { global: { stubs: {
    BaseDialog: { props: ['show'], template: '<div v-if="show"><slot /></div>' },
    BaseSelect: { props: ['modelValue', 'options'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="">选择项目</option><option v-for="option in options" :value="option.value">{{ option.label }}</option></select>' },
    ThreadAccessControl: { template: '<button @click="$emit(\'updated\')">完成接管</button>' },
    MessageContent: { props: ['blocks'], template: '<div>{{ blocks }}</div>' },
    ApprovalPanel: true,
  } } })
})
afterEach(() => { wrapper.unmount(); vi.useRealTimers() })
async function locate() {
  await wrapper.get('select').setValue('p')
  await wrapper.get('input').setValue('t')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

it('requires takeover before reading and clears content when access expires', async () => {
  await locate()
  expect(mocks.state).not.toHaveBeenCalled()
  expect(wrapper.text()).not.toContain('私有正文')
  mocks.get.mockResolvedValue({ thread_id: 't', metadata: { allowed_actions: ['read', 'approve', 'delete'] } })
  await wrapper.findAll('button').find(button => button.text() === '完成接管')!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('私有正文')
  mocks.get.mockRejectedValue(new Error('临时访问已到期'))
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  expect(wrapper.text()).not.toContain('私有正文')
  expect(wrapper.text()).toContain('临时访问已到期')
})

it('permits an explicit confirmed deletion without reading the private Thread', async () => {
  await locate()
  await wrapper.findAll('button').find(button => button.text() === '删除会话')!.trigger('click')
  expect(mocks.remove).not.toHaveBeenCalled()
  await wrapper.findAll('button').find(button => button.text() === '确认删除')!.trigger('click')
  await flushPromises()
  expect(mocks.remove).toHaveBeenCalledWith('t')
  expect(mocks.state).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('会话已删除')
})

it.each([false, true])('rechecks pending approval content before submitting (changed=%s)', async changed => {
  mocks.get.mockResolvedValue({ thread_id: 't', metadata: { allowed_actions: ['read', 'approve'] } })
  const snapshot = (path: string) => ({ values: {}, interrupts: [{ id: 'approval', value: {
    action_requests: [{ name: 'write_file', args: { path } }],
    review_configs: [{ action_name: 'write_file', allowed_decisions: ['approve', 'reject'] }],
  } }] })
  mocks.state.mockResolvedValue(snapshot('/old'))
  await locate()
  mocks.state.mockResolvedValue(snapshot(changed ? '/changed' : '/old'))
  wrapper.findComponent({ name: 'ApprovalPanel' }).vm.$emit('submit', { approval: [{ type: 'approve' }] })
  await flushPromises()
  if (changed) {
    expect(mocks.resume).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('审批内容已变化')
  } else {
    expect(mocks.resume).toHaveBeenCalledWith('t', { approval: { decisions: [{ type: 'approve' }] } })
    expect(wrapper.text()).toContain('审批已提交')
  }
})
