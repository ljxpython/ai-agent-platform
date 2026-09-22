import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ThreadAccessControl from './ThreadAccessControl.vue'

const mocks = vi.hoisted(() => ({ members: vi.fn(), get: vi.fn(), share: vi.fn(), takeover: vi.fn(), end: vi.fn() }))
vi.mock('@/services/members/members.service', () => ({ listProjectMembers: mocks.members }))
vi.mock('@/services/threads/session.service', () => ({ createSessionService: () => ({ get: mocks.get }) }))
vi.mock('@/services/langgraph/client', () => ({ createLanggraphAuthorizedFetch: () => vi.fn() }))
vi.mock('@/services/threads/access.service', () => ({ shareThread: mocks.share, takeOverThread: mocks.takeover, endThreadTakeover: mocks.end }))

let wrapper: ReturnType<typeof mount>
beforeEach(() => {
  vi.resetAllMocks()
  mocks.members.mockResolvedValue([])
  mocks.get.mockResolvedValue({ metadata: { shared_actions: { departed: ['read'] } } })
  wrapper = mount(ThreadAccessControl, {
    props: { projectId: 'p', threadId: 't', canShare: true, canTakeover: true },
    global: { stubs: {
      BaseDialog: { props: ['show'], template: '<div v-if="show"><slot /></div>' },
      BaseSelect: { props: ['modelValue', 'options', 'disabled'], template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="option in options" :value="option.value">{{ option.label }}</option></select>' },
    } },
  })
})
afterEach(() => wrapper.unmount())

it('allows revoking a departed member without allowing a new grant', async () => {
  await wrapper.findAll('button')[0]!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('已离开项目')
  await wrapper.get('select').setValue('departed')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  const revoke = wrapper.findAll('button').find(button => button.text() === '撤销所选共享')!
  await revoke.trigger('click')
  await flushPromises()
  expect(mocks.share).toHaveBeenCalledWith('p', 't', 'departed', [])
  expect(wrapper.emitted('updated')).toHaveLength(1)
})

it('keeps sharing disabled after a failed read and never submits stale grants', async () => {
  mocks.get.mockRejectedValue(new Error('读取失败'))
  await wrapper.findAll('button')[0]!.trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe('读取失败')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('form').trigger('submit')
  expect(mocks.share).not.toHaveBeenCalled()
})
