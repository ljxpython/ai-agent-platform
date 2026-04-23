import { describe, expect, it } from 'vitest'
import { buildChatLiveFollowView } from './live-follow-view-model'

describe('buildChatLiveFollowView', () => {
  it('shows realtime follow state while streaming and pinned to latest', () => {
    expect(
      buildChatLiveFollowView({
        autoFollowEnabled: true,
        isRunning: true,
        unreadMessageCount: 0,
        bufferedStreamActivity: false
      })
    ).toMatchObject({
      visible: true,
      tone: 'success',
      pillLabel: '实时跟随中',
      noticeVisible: false,
      showStopAction: false
    })
  })

  it('shows paused follow with jump-to-latest notice when unread messages accumulate', () => {
    expect(
      buildChatLiveFollowView({
        autoFollowEnabled: false,
        isRunning: true,
        unreadMessageCount: 3,
        bufferedStreamActivity: false
      })
    ).toMatchObject({
      visible: true,
      tone: 'warning',
      pillLabel: '已暂停跟随',
      noticeVisible: true,
      title: '有 3 条新消息',
      showStopAction: true
    })
  })

  it('shows execution update copy when stream activity arrives without discrete unread count', () => {
    expect(
      buildChatLiveFollowView({
        autoFollowEnabled: false,
        isRunning: true,
        unreadMessageCount: 0,
        bufferedStreamActivity: true
      })
    ).toMatchObject({
      visible: true,
      noticeVisible: true,
      title: '有新的执行更新',
      showStopAction: true
    })
  })

  it('stays hidden when chat is idle and there are no unread/live updates', () => {
    expect(
      buildChatLiveFollowView({
        autoFollowEnabled: true,
        isRunning: false,
        unreadMessageCount: 0,
        bufferedStreamActivity: false
      })
    ).toMatchObject({
      visible: false,
      noticeVisible: false
    })
  })
})
