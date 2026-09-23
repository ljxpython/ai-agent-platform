import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ThreadActionsMenu from './ThreadActionsMenu.vue'

describe('ThreadActionsMenu', () => {
  it('renders trigger button with icon and toggles dropdown', async () => {
    const wrapper = mount(ThreadActionsMenu, {
      props: {
        focusMode: false,
        canTakeover: true,
        canDelete: true,
      },
      global: {
        stubs: {
          BaseIcon: {
            props: ['name'],
            template: '<span class="icon-stub" :data-name="name" />'
          },
          Teleport: true,
        }
      }
    })

    const trigger = wrapper.find('button[aria-label="更多操作"]')
    expect(trigger.exists()).toBe(true)

    // 点击展开菜单
    await trigger.trigger('click')
    await flushPromises()

    // 检查是否有抽屉详情项
    const drawerItem = wrapper.findAll('button').find(b => b.text().includes('会话详情与上下文'))
    expect(drawerItem).toBeDefined()
    await drawerItem?.trigger('click')
    expect(wrapper.emitted('open-drawer')).toBeDefined()

    // 重新打开并点击运行参数配置
    await trigger.trigger('click')
    await flushPromises()
    const optionsItem = wrapper.findAll('button').find(b => b.text().includes('运行参数配置'))
    expect(optionsItem).toBeDefined()
    await optionsItem?.trigger('click')
    expect(wrapper.emitted('open-options')).toBeDefined()

    // 重新打开并点击专注模式
    await trigger.trigger('click')
    await flushPromises()
    const focusItem = wrapper.findAll('button').find(b => b.text().includes('进入专注模式'))
    expect(focusItem).toBeDefined()
    await focusItem?.trigger('click')
    expect(wrapper.emitted('toggle-focus')).toBeDefined()

    // 重新打开并测试管理员临时接管
    await trigger.trigger('click')
    await flushPromises()
    const takeoverItem = wrapper.findAll('button').find(b => b.text().includes('管理员临时接管'))
    expect(takeoverItem).toBeDefined()
    await takeoverItem?.trigger('click')
    expect(wrapper.emitted('open-takeover')).toBeDefined()

    // 重新打开并测试删除当前会话
    await trigger.trigger('click')
    await flushPromises()
    const deleteItem = wrapper.findAll('button').find(b => b.text().includes('删除当前会话'))
    expect(deleteItem).toBeDefined()
    await deleteItem?.trigger('click')
    expect(wrapper.emitted('delete-thread')).toBeDefined()
  })

  it('hides takeover and delete actions when permissions are false', async () => {
    const wrapper = mount(ThreadActionsMenu, {
      props: {
        focusMode: true,
        canTakeover: false,
        canDelete: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
          Teleport: true,
        }
      }
    })

    const trigger = wrapper.find('button[aria-label="更多操作"]')
    await trigger.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('退出专注模式')
    expect(wrapper.text()).not.toContain('管理员临时接管')
    expect(wrapper.text()).not.toContain('删除当前会话')
  })
})
