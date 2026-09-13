import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatAgentSelector from './ChatAgentSelector.vue'
import type { Agent } from '@/services/agents/types'

const mockAgents: Agent[] = [
  {
    id: 'agent-1',
    name: '代码开发助手',
    description: '负责核心功能开发与代码重构',
    graph_id: 'graph-dev',
    status: 'active',
    project_id: 'proj-1',
    context: {},
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z'
  },
  {
    id: 'agent-2',
    name: '架构评审专家',
    description: '负责技术方案审查与安全审计',
    graph_id: 'graph-arch',
    status: 'active',
    project_id: 'proj-1',
    context: {},
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z'
  }
]

describe('ChatAgentSelector.vue', () => {
  it('renders default label when no agent is selected', () => {
    const wrapper = mount(ChatAgentSelector, {
      props: {
        agents: mockAgents,
        selectedAgentId: ''
      }
    })

    expect(wrapper.text()).toContain('选择智能体')
  })

  it('renders selected agent name', () => {
    const wrapper = mount(ChatAgentSelector, {
      props: {
        agents: mockAgents,
        selectedAgentId: 'agent-1'
      }
    })

    expect(wrapper.text()).toContain('代码开发助手')
  })

  it('toggles dropdown and emits select when clicked', async () => {
    const wrapper = mount(ChatAgentSelector, {
      props: {
        agents: mockAgents,
        selectedAgentId: 'agent-1'
      },
      attachTo: document.body
    })

    const triggerBtn = wrapper.find('button[aria-label="对话目标"]')
    expect(triggerBtn.exists()).toBe(true)

    // Click to open dropdown
    await triggerBtn.trigger('click')
    expect(wrapper.vm.isOpen).toBe(true)

    // Select second agent
    wrapper.vm.select('agent-2')
    expect(wrapper.emitted('select')).toEqual([['agent-2']])
    expect(wrapper.vm.isOpen).toBe(false)

    wrapper.unmount()
  })
})
