import { computed, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const { queryProjectKnowledgeMock, streamProjectKnowledgeQueryMock } = vi.hoisted(() => ({
  queryProjectKnowledgeMock: vi.fn(),
  streamProjectKnowledgeQueryMock: vi.fn(),
}))

vi.mock('@/composables/useAuthorization', () => ({
  useAuthorization: () => ({
    can: () => true,
  }),
}))

vi.mock('@/modules/knowledge/composables/useKnowledgeProjectRoute', () => ({
  useKnowledgeProjectRoute: () => ({
    projectId: ref('project-42'),
    project: computed(() => ({
      id: 'project-42',
      name: 'Project 42',
    })),
  }),
}))

vi.mock('@/services/knowledge/knowledge.service', () => ({
  queryProjectKnowledge: queryProjectKnowledgeMock,
  streamProjectKnowledgeQuery: streamProjectKnowledgeQueryMock,
}))

vi.mock('@/utils/http-error', () => ({
  resolvePlatformHttpErrorMessage: () => '知识检索失败',
}))

import KnowledgeRetrievalPage from './KnowledgeRetrievalPage.vue'

describe('KnowledgeRetrievalPage', () => {
  it('uses the workspace page shell with an internal scroll container', async () => {
    const wrapper = mount(KnowledgeRetrievalPage, {
      global: {
        stubs: {
          BaseButton: { template: '<button><slot /></button>' },
          SurfaceCard: { template: '<section><slot /></section>' },
          PageHeader: {
            props: ['title', 'description'],
            template: '<header><h1>{{ title }}</h1><p>{{ description }}</p><slot name="actions" /></header>',
          },
          EmptyState: { template: '<div><slot /></div>' },
          StateBanner: {
            props: ['title', 'description'],
            template: '<div><strong>{{ title }}</strong><span>{{ description }}</span></div>',
          },
          KnowledgeQuerySettingsPanel: { template: '<aside>settings panel</aside>' },
          KnowledgeWorkspaceNav: { template: '<nav>knowledge nav</nav>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('section').classes()).toEqual(
      expect.arrayContaining(['pw-page-shell', 'flex', 'h-full', 'min-h-0', 'flex-col', 'overflow-y-auto']),
    )
    expect(wrapper.text()).toContain('settings panel')
  })
})
