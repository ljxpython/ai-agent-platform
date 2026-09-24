export const CHAT_AUTO_FOLLOW_THRESHOLD_PX = 80;
export const CHAT_SUBSEQUENT_TURN_ANCHOR_RATIO = 0.32;
export const CHAT_STREAM_BOTTOM_PADDING_PX = 36;
export const CHAT_MIN_BOTTOM_SPACER_PX = 24;

export type ChatViewportMetrics = {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
};

export function getChatViewportDistanceToBottom(viewport: ChatViewportMetrics) {
  return Math.max(
    0,
    viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight,
  );
}

export function isChatViewportNearBottom(
  viewport: ChatViewportMetrics,
  threshold = CHAT_AUTO_FOLLOW_THRESHOLD_PX,
) {
  return getChatViewportDistanceToBottom(viewport) <= threshold;
}

/**
 * 计算仿 GPT 对话界面的回合锚定目标 scrollTop：
 * - 第 1 次提问 (turnCount <= 1)：问题移动到最上方 (scrollTop = 0)，下方流式生成内容
 * - 后续提问 (turnCount > 1)：问题停留在视口偏中间位置（默认距离视口顶部 32% 处），继续向下流式输出
 */
export function computeTurnAnchorScrollTop(params: {
  turnCount: number;
  userElementOffsetTop: number;
  viewportClientHeight: number;
  anchorRatio?: number;
}): number {
  const {
    turnCount,
    userElementOffsetTop,
    viewportClientHeight,
    anchorRatio = CHAT_SUBSEQUENT_TURN_ANCHOR_RATIO,
  } = params;
  if (turnCount <= 1 || viewportClientHeight <= 0) {
    return 0;
  }
  const desiredTopOffset = Math.round(viewportClientHeight * anchorRatio);
  return Math.max(0, Math.round(userElementOffsetTop - desiredTopOffset));
}

/**
 * 计算后续对话（turnCount > 1）底部的动态留白垫片高度：
 * 确保最新一轮（用户提问 + AI 当前已输出内容）下方有足够空间让用户提问停留在偏中间位置，
 * 同时当 AI 输出逐渐变长时垫片自动等量收缩，避免流式输出时画面上蹿或长回复底部残留巨大空白。
 */
export function computeDynamicBottomSpacerHeight(params: {
  turnCount: number;
  viewportClientHeight: number;
  latestTurnHeightPx: number;
  anchorRatio?: number;
  minSpacerPx?: number;
}): number {
  const {
    turnCount,
    viewportClientHeight,
    latestTurnHeightPx,
    anchorRatio = CHAT_SUBSEQUENT_TURN_ANCHOR_RATIO,
    minSpacerPx = CHAT_MIN_BOTTOM_SPACER_PX,
  } = params;
  if (turnCount <= 1 || viewportClientHeight <= 0) {
    return 0;
  }
  const targetBelowUserTop = Math.round(viewportClientHeight * (1 - anchorRatio));
  return Math.max(
    minSpacerPx,
    targetBelowUserTop - Math.max(0, Math.round(latestTurnHeightPx)),
  );
}

/**
 * 流式输出期间的按需推进滚动计算：
 * 当流式生成的最新内容底部仍在当前可视区域内（即在问题下方的空白区内生长）时，返回 null（保持 scrollTop 不动，防止问题被往上顶）；
 * 仅当流式内容超出了视口底边安全边距时，才推进 scrollTop 使最新文字保持可见。
 */
export function computeStreamingFollowScrollTop(params: {
  currentScrollTop: number;
  viewportClientHeight: number;
  contentBottomOffsetTop: number;
  bottomPaddingPx?: number;
}): number | null {
  const {
    currentScrollTop,
    viewportClientHeight,
    contentBottomOffsetTop,
    bottomPaddingPx = CHAT_STREAM_BOTTOM_PADDING_PX,
  } = params;
  if (viewportClientHeight <= 0 || contentBottomOffsetTop <= 0) {
    return null;
  }
  const visibleBottomLimit =
    currentScrollTop + viewportClientHeight - bottomPaddingPx;
  if (contentBottomOffsetTop <= visibleBottomLimit) {
    return null;
  }
  return Math.max(
    currentScrollTop,
    Math.round(contentBottomOffsetTop - viewportClientHeight + bottomPaddingPx),
  );
}

/**
 * 判断视口是否处于最新内容底部附近（兼容底部动态留白垫片）：
 * 若最新内容实际底边（contentBottomOffsetTop）已在视口可视底部内或距离在阈值内，视为处于底部。
 */
export function isChatViewportNearContentBottom(
  viewport: ChatViewportMetrics,
  contentBottomOffsetTop?: number,
  threshold = CHAT_AUTO_FOLLOW_THRESHOLD_PX,
): boolean {
  if (isChatViewportNearBottom(viewport, threshold)) {
    return true;
  }
  if (
    typeof contentBottomOffsetTop === "number" &&
    contentBottomOffsetTop > 0
  ) {
    const distanceToContentBottom =
      contentBottomOffsetTop - (viewport.scrollTop + viewport.clientHeight);
    return distanceToContentBottom <= threshold;
  }
  return false;
}

