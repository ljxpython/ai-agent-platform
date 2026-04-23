import {
  CHAT_AUTO_FOLLOW_THRESHOLD_PX,
  getChatViewportDistanceToBottom,
  isChatViewportNearBottom
} from './scroll-state'

describe('chat scroll state', () => {
  it('会正确计算距离底部的像素值', () => {
    expect(
      getChatViewportDistanceToBottom({
        scrollTop: 520,
        scrollHeight: 1200,
        clientHeight: 600
      })
    ).toBe(80)
  })

  it('会基于阈值判断是否处于可自动跟随状态', () => {
    expect(
      isChatViewportNearBottom({
        scrollTop: 520,
        scrollHeight: 1200,
        clientHeight: 600
      })
    ).toBe(true)

    expect(
      isChatViewportNearBottom({
        scrollTop: 480,
        scrollHeight: 1200,
        clientHeight: 600
      })
    ).toBe(false)

    expect(CHAT_AUTO_FOLLOW_THRESHOLD_PX).toBe(80)
  })
})
