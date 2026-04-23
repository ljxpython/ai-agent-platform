import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatComposer from './ChatComposer.vue'

function mountComposer() {
  return mount(ChatComposer, {
    props: {
      modelValue: '',
      attachments: [],
      isRunning: false,
      hasBlockingInterrupt: false,
      interruptPayload: null,
      canStartThread: true,
      showContinueAction: false,
      canSendFreshMessage: false,
      cancelling: false,
      sendButtonLabel: '发送消息',
      lastEventAt: '',
      compact: true,
      onResumeInterruptedRun: async () => true,
      'onUpdate:modelValue': () => undefined
    },
    global: {
      stubs: {
        ChatInterruptPanel: true,
        ChatAttachmentPreview: true
      }
    }
  })
}

describe('ChatComposer', () => {
  it('does not render legacy resize or expand controls in compact mode', () => {
    const wrapper = mountComposer()

    expect(wrapper.find('button[aria-label="拖拽调整输入框高度"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('展开输入框')
    expect(wrapper.text()).not.toContain('支持 JPEG')
  })
})
