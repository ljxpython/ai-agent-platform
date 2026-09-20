import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import ToolRestrictionsPanel from './ToolRestrictionsPanel.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import StateBanner from '@/components/platform/StateBanner.vue'

const { mockListToolRestrictions, mockCreateToolRestriction, mockDeleteToolRestriction, mockListProjectMembers, mockListRuntimeGraphs } =
  vi.hoisted(() => ({
    mockListToolRestrictions: vi.fn(),
    mockCreateToolRestriction: vi.fn(),
    mockDeleteToolRestriction: vi.fn(),
    mockListProjectMembers: vi.fn(),
    mockListRuntimeGraphs: vi.fn()
  }))

vi.mock('@/services/runtime-policies/runtime-policies.service', () => ({
  listToolRestrictions: mockListToolRestrictions,
  createToolRestriction: mockCreateToolRestriction,
  deleteToolRestriction: mockDeleteToolRestriction
}))

vi.mock('@/services/members/members.service', () => ({
  listProjectMembers: mockListProjectMembers
}))

vi.mock('@/services/runtime/runtime.service', () => ({
  listRuntimeGraphs: mockListRuntimeGraphs
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key })
}))

describe('ToolRestrictionsPanel', () => {
  const mockTools = [
    {
      id: 't-1',
      runtime_id: 'rt-1',
      tool_key: 'execute',
      graph_ids: ['dearflow_agent', 'subagent'],
      name: '终端命令执行',
      source: 'builtin',
      description: '运行 bash 终端命令',
      sync_status: 'ready',
      last_seen_at: '2026-09-20T00:00:00Z',
      last_synced_at: '2026-09-20T00:00:00Z'
    },
    {
      id: 't-2',
      runtime_id: 'rt-1',
      tool_key: 'web_search',
      graph_ids: ['dearflow_agent'],
      name: '网络检索',
      source: 'builtin',
      description: '搜索网页内容',
      sync_status: 'ready',
      last_seen_at: '2026-09-20T00:00:00Z',
      last_synced_at: '2026-09-20T00:00:00Z'
    }
  ]

  const mockMembers = [
    {
      user_id: 'user-aaa-111',
      username: 'alice',
      role: 'project_editor' as const
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    mockListProjectMembers.mockResolvedValue(mockMembers)
    mockListRuntimeGraphs.mockResolvedValue({ count: 0, graphs: [] })
  })

  function createWrapper(props = {}) {
    return mount(ToolRestrictionsPanel, {
      props: {
        show: true,
        projectId: 'proj-001',
        tools: mockTools,
        canManage: true,
        ...props
      },
      global: {
        stubs: {
          BaseDialog: {
            props: ['show', 'title'],
            template: '<div v-if="show"><h2>{{ title }}</h2><slot /></div>'
          },
          ConfirmDialog: {
            props: ['show', 'title', 'message'],
            emits: ['confirm', 'cancel'],
            template: '<div v-if="show" class="confirm-stub"><span>{{ message }}</span><button class="confirm-btn" @click="$emit(\'confirm\')">确认</button></div>'
          }
        },
        components: {
          BaseButton,
          BaseIcon,
          StatusPill,
          StateBanner
        }
      }
    })
  }

  it('loads restrictions and members when dialog is shown', async () => {
    mockListToolRestrictions.mockResolvedValue({ items: [], total: 0 })

    const wrapper = createWrapper()
    await vi.dynamicImportSettled()

    expect(mockListToolRestrictions).toHaveBeenCalledWith('proj-001')
    expect(mockListProjectMembers).toHaveBeenCalledWith('proj-001')
    expect(wrapper.text()).toContain('工具禁用规则管理')
    expect(wrapper.text()).toContain('当前项目未配置任何工具禁用规则')
  })

  it('renders union semantics warning when both project and user restrictions exist for same tool', async () => {
    mockListToolRestrictions.mockResolvedValue({
      items: [
        {
          id: 'r-1',
          project_id: 'proj-001',
          graph_id: 'dearflow_agent',
          subject_type: 'project',
          subject_id: 'proj-001',
          tool_name: 'execute',
          reason: '全员禁用',
          created_by: 'admin',
          created_at: '2026-09-20T01:00:00Z'
        },
        {
          id: 'r-2',
          project_id: 'proj-001',
          graph_id: 'dearflow_agent',
          subject_type: 'user',
          subject_id: 'user-aaa-111',
          tool_name: 'execute',
          reason: '单人禁用',
          created_by: 'admin',
          created_at: '2026-09-20T02:00:00Z'
        }
      ],
      total: 2
    })

    const wrapper = createWrapper()
    // 等待异步数据加载和微任务完成
    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('execute')
    })

    // 应该渲染并集提示
    expect(wrapper.text()).toContain('项目全员已禁用，删除此单人规则后该用户仍受限')
    expect(wrapper.text()).toContain('alice')
  })

  it('automatically resolves and selects available graphs including direct runtime graphs', async () => {
    mockListToolRestrictions.mockResolvedValue({ items: [], total: 0 })
    mockListRuntimeGraphs.mockResolvedValue({
      count: 1,
      graphs: [{ graph_id: 'extra_graph' }]
    })

    const wrapper = createWrapper({ tools: [] })
    await vi.waitFor(() => {
      expect(mockListRuntimeGraphs).toHaveBeenCalledWith('proj-001')
    })
    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('extra_graph')
    })
  })

  it('renders refined delete button with trash icon in operations column', async () => {
    mockListToolRestrictions.mockResolvedValue({
      items: [
        {
          id: 'r-1',
          project_id: 'proj-001',
          graph_id: 'dearflow_agent',
          subject_type: 'project',
          subject_id: 'proj-001',
          tool_name: 'execute',
          reason: '测试禁用',
          created_by: 'admin',
          created_at: '2026-09-20T01:00:00Z'
        }
      ],
      total: 1
    })

    const wrapper = createWrapper()
    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('解除禁用')
    })

    const deleteBtn = wrapper.find('button[title="解除此条工具禁用规则"]')
    expect(deleteBtn.exists()).toBe(true)
    const trashIcon = deleteBtn.findComponent(BaseIcon)
    expect(trashIcon.exists()).toBe(true)
    expect(trashIcon.props('name')).toBe('trash')
  })
})
