import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, expect, it, vi } from 'vitest'

const { refreshProject, refreshUser } = vi.hoisted(() => ({ refreshProject: vi.fn(), refreshUser: vi.fn() }))
vi.mock('vue-router', () => ({ useRoute: () => ({ name: 'workspace-chat', params: {}, meta: { immersive: true } }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ sessionEpoch: 1, fetchCurrentUser: refreshUser }) }))
vi.mock('@/stores/workspace', () => ({ useWorkspaceStore: () => ({ refreshCurrentProjectAccess: refreshProject }) }))
vi.mock('@/composables/useAuthorization', () => ({ useAuthorization: () => ({ can: () => true }) }))
vi.mock('@/components/layout/AppSidebar.vue', () => ({ default: { template: '<aside />' } }))
vi.mock('@/components/layout/TopContextBar.vue', () => ({ default: { template: '<header />' } }))
import WorkspaceLayout from './WorkspaceLayout.vue'

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

it('refreshes immersive pages every 60 seconds, on activation and rejection, and removes listeners', async () => {
  vi.useFakeTimers()
  refreshProject.mockResolvedValue(undefined)
  refreshUser.mockResolvedValue(undefined)
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const wrapper = mount(WorkspaceLayout, { global: { plugins: [createPinia()], stubs: {
    AppSidebar: true, TopContextBar: true, 'router-view': true, RouterLink: true, StateBanner: true
  } } })
  await vi.advanceTimersByTimeAsync(60_000)
  expect(refreshProject).toHaveBeenCalledTimes(1)
  expect(refreshUser).toHaveBeenCalledTimes(1)
  visibility.mockReturnValue('hidden')
  await vi.advanceTimersByTimeAsync(60_000)
  expect(refreshProject).toHaveBeenCalledTimes(1)
  visibility.mockReturnValue('visible')
  document.dispatchEvent(new Event('visibilitychange'))
  await flushPromises()
  window.dispatchEvent(new Event('platform-access-denied'))
  await flushPromises()
  window.dispatchEvent(new Event('focus'))
  await flushPromises()
  expect(refreshProject).toHaveBeenCalledTimes(4)
  wrapper.unmount()
  await vi.advanceTimersByTimeAsync(60_000)
  window.dispatchEvent(new Event('platform-access-denied'))
  window.dispatchEvent(new Event('focus'))
  expect(refreshProject).toHaveBeenCalledTimes(4)
})
