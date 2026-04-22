export type ChatCompactModeView = {
  enabled: boolean
}

export function buildChatCompactModeView(options: {
  activeThreadId: string
  messageCount: number
  isRunning: boolean
  loadingThreadDetail: boolean
}): ChatCompactModeView {
  const hasActiveThread = options.activeThreadId.trim().length > 0
  const messageCount = Math.max(0, Math.floor(options.messageCount))

  return {
    enabled:
      hasActiveThread &&
      (messageCount > 0 || options.isRunning || options.loadingThreadDetail)
  }
}
