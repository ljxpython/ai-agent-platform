import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DearAgentThreadSidebar from './DearAgentThreadSidebar.vue'

describe('DearAgentThreadSidebar pagination', () => {
  const defaultProps = {
    showContextBar: false,
    targetText: 'test-target',
    targetTypeText: 'Agent',
    search: '',
    statusFilter: 'all' as const,
    filters: [{ value: 'all' as const, label: '全部' }],
    loading: false,
    threadCount: 100,
    filteredCount: 100,
    canStartThread: true,
    activeThreadId: '',
    deletingThreadId: '',
    groups: [],
    currentPage: 2,
    totalPages: 5,
    totalCount: 100,
    hasMore: true,
    canDelete: true,
  }

  it('renders total count and page indicators', () => {
    const wrapper = mount(DearAgentThreadSidebar, { props: defaultProps })
    expect(wrapper.text()).toContain('共 100 条')
    expect(wrapper.text()).toContain('/ 5')
    const input = wrapper.find('input[inputmode="numeric"]')
    expect((input.element as HTMLInputElement).value).toBe('2')
  })

  it('emits page-change on first, previous, next, last buttons', async () => {
    const wrapper = mount(DearAgentThreadSidebar, { props: defaultProps })
    const buttons = wrapper.findAll('button')
    const firstBtn = buttons.find((b) => b.attributes('title') === '首页')
    const prevBtn = buttons.find((b) => b.attributes('title') === '上一页')
    const nextBtn = buttons.find((b) => b.attributes('title') === '下一页')
    const lastBtn = buttons.find((b) => b.attributes('title') === '末页')

    expect(firstBtn).toBeDefined()
    expect(prevBtn).toBeDefined()
    expect(nextBtn).toBeDefined()
    expect(lastBtn).toBeDefined()

    await firstBtn!.trigger('click')
    expect(wrapper.emitted('page-change')?.[0]).toEqual([1])

    await prevBtn!.trigger('click')
    expect(wrapper.emitted('page-change')?.[1]).toEqual([1])

    await nextBtn!.trigger('click')
    expect(wrapper.emitted('page-change')?.[2]).toEqual([3])

    await lastBtn!.trigger('click')
    expect(wrapper.emitted('page-change')?.[3]).toEqual([5])
  })

  it('jumps to page when input changes and enter key is pressed', async () => {
    const wrapper = mount(DearAgentThreadSidebar, { props: defaultProps })
    const input = wrapper.find('input[inputmode="numeric"]')

    await input.setValue('4')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('page-change')?.[0]).toEqual([4])
  })

  it('clamps out-of-range page numbers', async () => {
    const wrapper = mount(DearAgentThreadSidebar, { props: defaultProps })
    const input = wrapper.find('input[inputmode="numeric"]')

    await input.setValue('999')
    await input.trigger('keydown.enter')
    expect(wrapper.emitted('page-change')?.[0]).toEqual([5])
  })
})
