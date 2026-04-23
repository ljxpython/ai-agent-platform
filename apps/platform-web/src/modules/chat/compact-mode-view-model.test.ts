import { describe, expect, it } from 'vitest'
import { buildChatCompactModeView } from './compact-mode-view-model'

describe('buildChatCompactModeView', () => {
  it('stays expanded before a thread becomes active', () => {
    expect(
      buildChatCompactModeView({
        activeThreadId: '',
        messageCount: 0,
        isRunning: false,
        loadingThreadDetail: false
      })
    ).toEqual({
      enabled: false
    })
  })

  it('enters compact mode when an active thread has transcript messages', () => {
    expect(
      buildChatCompactModeView({
        activeThreadId: 'thread-1',
        messageCount: 2,
        isRunning: false,
        loadingThreadDetail: false
      })
    ).toEqual({
      enabled: true
    })
  })

  it('stays compact while an active thread is loading existing history', () => {
    expect(
      buildChatCompactModeView({
        activeThreadId: 'thread-1',
        messageCount: 0,
        isRunning: false,
        loadingThreadDetail: true
      })
    ).toEqual({
      enabled: true
    })
  })

  it('does not compact a blank fresh thread without messages or activity', () => {
    expect(
      buildChatCompactModeView({
        activeThreadId: 'thread-1',
        messageCount: 0,
        isRunning: false,
        loadingThreadDetail: false
      })
    ).toEqual({
      enabled: false
    })
  })
})
