import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import ControlPlanePage from './ControlPlanePage.vue'

const mocks = vi.hoisted(() => ({ can: vi.fn(), graphs: vi.fn(), tools: vi.fn() }))
vi.mock('@/composables/useAuthorization', () => ({ useAuthorization: () => ({ can: mocks.can, canAnyProject: () => false, currentProjectCan: () => false }) }))
vi.mock('@/stores/workspace', () => ({ useWorkspaceStore: () => ({ projects: [{ id: 'p', name: '业务项目', status: 'active' }], currentProjectId: '', currentProjectAccess: null }) }))
vi.mock('@/services/runtime/runtime.service', () => ({ refreshRuntimeGraphs: mocks.graphs, refreshRuntimeTools: mocks.tools }))
vi.mock('@/services/system/platform-config.service', () => ({ getPlatformConfigSnapshot: async () => null }))
vi.mock('@/services/system/system-governance.service', () => ({ getSystemHealth: async () => null, getSystemReadyProbe: async () => null }))
vi.mock('@/services/audit/audit.service', () => ({ listAudit: async () => ({ items: [] }) }))
vi.mock('@/services/system/service-accounts.service', () => ({ listServiceAccounts: async () => ({ items: [] }) }))

function render() {
  return mount(ControlPlanePage, { global: { stubs: {
    RouterLink: true, BaseIcon: true, GuidePanel: true, MetricCard: true,
    BaseSelect: { props: ['modelValue', 'options', 'disabled'], template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="">选择项目</option><option v-for="option in options" :value="option.value">{{ option.label }}</option></select>' },
  } } })
}
beforeEach(() => { vi.resetAllMocks(); mocks.can.mockImplementation(permission => permission === 'platform.catalog.refresh'); mocks.graphs.mockResolvedValue({ count: 2 }) })

it('lets an operator synchronize the catalog without selecting a business workspace', async () => {
  const wrapper = render()
  try {
    await flushPromises()
    const button = wrapper.findAll('button').find(item => item.text() === '同步 Graph 目录')!
    expect(button.attributes('disabled')).toBeDefined()
    await wrapper.get('select').setValue('p')
    await button.trigger('click')
    await flushPromises()
    expect(mocks.graphs).toHaveBeenCalledWith('p')
    expect(wrapper.text()).toContain('Graph全局目录已刷新，共 2 项')
    expect(wrapper.text()).toContain('无需加入项目')
  } finally { wrapper.unmount() }
})

it('hides catalog mutation controls from platform viewers', async () => {
  mocks.can.mockReturnValue(false)
  const wrapper = render()
  try {
    await flushPromises()
    expect(wrapper.text()).not.toContain('同步 Graph 目录')
    expect(mocks.graphs).not.toHaveBeenCalled()
  } finally { wrapper.unmount() }
})
