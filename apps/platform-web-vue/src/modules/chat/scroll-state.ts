export const CHAT_AUTO_FOLLOW_THRESHOLD_PX = 80

type ChatViewportMetrics = {
  scrollTop: number
  scrollHeight: number
  clientHeight: number
}

export function getChatViewportDistanceToBottom(viewport: ChatViewportMetrics) {
  return Math.max(0, viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight)
}

export function isChatViewportNearBottom(
  viewport: ChatViewportMetrics,
  threshold = CHAT_AUTO_FOLLOW_THRESHOLD_PX
) {
  return getChatViewportDistanceToBottom(viewport) <= threshold
}
