import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import BaseSelect from './BaseSelect.vue'

describe('BaseSelect', () => {
  const options = [
    { value: '', label: '无平台角色' },
    { value: 'viewer', label: '只读' },
    { value: 'admin', label: '管理员' }
  ]

  it('renders default placeholder and toggles on click', async () => {
    const wrapper = mount(BaseSelect, {
      props: {
        modelValue: '',
        options
      },
      global: {
        stubs: {
          BaseIcon: true
        }
      }
    })

    const trigger = wrapper.find('button.pw-select-trigger')
    expect(trigger.exists()).toBe(true)
    expect(trigger.text()).toContain('无平台角色')

    // Click trigger to open
    await trigger.trigger('click')
    expect(wrapper.find('button.pw-select-trigger').attributes('aria-expanded')).toBe('true')
    expect(document.body.querySelector('.pw-select-dropdown')).not.toBeNull()

    // Click trigger to close
    await trigger.trigger('click')
    expect(wrapper.find('button.pw-select-trigger').attributes('aria-expanded')).toBe('false')
  })

  it('selects option and emits update:modelValue', async () => {
    const wrapper = mount(BaseSelect, {
      props: {
        modelValue: '',
        options
      },
      global: {
        stubs: {
          BaseIcon: true
        }
      }
    })

    const trigger = wrapper.find('button.pw-select-trigger')
    await trigger.trigger('click')

    const optionButtons = document.body.querySelectorAll('.pw-select-option')
    expect(optionButtons.length).toBe(3)

    const adminOption = Array.from(optionButtons).find((el) => el.textContent?.includes('管理员')) as HTMLButtonElement
    adminOption.click()
    await nextTick()

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual(['admin'])
    expect(wrapper.find('button.pw-select-trigger').attributes('aria-expanded')).toBe('false')
  })

  it('closes on outside click and suppresses rapid synthetic trigger toggle', async () => {
    const wrapper = mount({
      components: { BaseSelect },
      template: `
        <label id="test-label">
          <span id="label-text">平台角色</span>
          <BaseSelect model-value="" :options="options" />
        </label>
      `,
      data() {
        return { options }
      }
    }, {
      attachTo: document.body,
      global: {
        stubs: {
          BaseIcon: true
        }
      }
    })

    const trigger = wrapper.find('button.pw-select-trigger')
    await trigger.trigger('click')
    expect(trigger.attributes('aria-expanded')).toBe('true')

    // Simulate clicking on the label text outside trigger
    const labelText = document.getElementById('label-text')!
    labelText.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()

    // Dropdown should be closed by handleClickOutside
    expect(trigger.attributes('aria-expanded')).toBe('false')

    // Browser label activation fires a synthetic click on trigger immediately
    await trigger.trigger('click')
    await nextTick()

    // Debounce should prevent it from reopening immediately
    expect(trigger.attributes('aria-expanded')).toBe('false')

    wrapper.unmount()
  })
})
