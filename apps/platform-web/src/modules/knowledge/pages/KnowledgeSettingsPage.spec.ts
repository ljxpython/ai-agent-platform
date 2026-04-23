import { computed, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const { getProjectKnowledgeSpaceMock, refreshProjectKnowledgeSpaceMock } = vi.hoisted(() => ({
  getProjectKnowledgeSpaceMock: vi.fn(),
  refreshProjectKnowledgeSpaceMock: vi.fn()
}))

vi.mock('@/composables/useAuthorization', () => ({
  useAuthorization: () => ({
    can: () => true
  })
}))

vi.mock('@/modules/knowledge/composables/useKnowledgeProjectRoute', () => ({
  useKnowledgeProjectRoute: () => ({
    projectId: ref('project-42'),
    project: computed(() => ({
      id: 'project-42',
      name: 'Project 42'
    }))
  })
}))

vi.mock('@/services/knowledge/knowledge.service', () => ({
  getProjectKnowledgeSpace: getProjectKnowledgeSpaceMock,
  refreshProjectKnowledgeSpace: refreshProjectKnowledgeSpaceMock
}))

vi.mock('@/utils/format', () => ({
  formatDateTime: (value: string | null | undefined) => value || '--'
}))

vi.mock('@/utils/http-error', () => ({
  resolvePlatformHttpErrorMessage: () => '知识空间设置加载失败'
}))

import KnowledgeSettingsPage from './KnowledgeSettingsPage.vue'

describe('KnowledgeSettingsPage', () => {
  it('renders workspace mapping and runbook guidance for the project knowledge space', async () => {
    getProjectKnowledgeSpaceMock.mockResolvedValue({
      id: 'space-1',
      project_id: 'project-42',
      provider: 'lightrag',
      display_name: 'Project 42 知识空间',
      workspace_key: 'kb_project_42',
      status: 'active',
      service_base_url: 'http://knowledge.test',
      runtime_profile_json: {},
      updated_at: '2026-04-12T00:00:00Z',
      health: {
        status: 'ok',
        request_id: 'req-123',
        trace_id: 'trace-456',
        latency_ms: 32,
        checks: ['api', 'storage'],
        details: {
          provider: 'lightrag',
          shard: 'default'
        }
      },
    })

    const wrapper = mount(KnowledgeSettingsPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template:
              '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>'
          },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>'
          },
          StatusPill: { template: '<span><slot /></span>' },
          KnowledgeWorkspaceNav: { template: '<nav>knowledge nav</nav>' }
        }
      }
    })

    await flushPromises()

    expect(wrapper.find('section').classes()).toEqual(
      expect.arrayContaining(['pw-page-shell', 'h-full', 'min-h-0', 'overflow-y-auto']),
    )
    expect(wrapper.text()).toContain('workspace 映射摘要')
    expect(wrapper.text()).toContain('project_id')
    expect(wrapper.text()).toContain('workspace_key')
    expect(wrapper.text()).toContain('platform-web → platform-api → LightRAG')
    expect(wrapper.text()).toContain('服务健康')
    expect(wrapper.text()).toContain('request id')
    expect(wrapper.text()).toContain('trace id')
    expect(wrapper.text()).toContain('Raw Payload')
    expect(wrapper.text()).toContain('details')
    expect(wrapper.text()).toContain('api, storage')
    expect(wrapper.text()).toContain('运行说明 / 风险说明')
    expect(wrapper.text()).toContain('清空知识文档属于高风险操作，仅项目管理员可执行')
    expect(wrapper.text()).toContain('future runtime-side reuse 仍应走 LightRAG MCP')
  })
})
