import {
  computed,
  getCurrentScope,
  nextTick,
  onScopeDispose,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import {
  computeDynamicBottomSpacerHeight,
  computeStreamingFollowScrollTop,
  computeTurnAnchorScrollTop,
  isChatViewportNearContentBottom,
} from "../scroll-state";
import { buildChatLiveFollowView } from "../live-follow-view-model";

function isHumanLikeMessage(m: unknown): boolean {
  if (!m || typeof m !== "object") return false;
  const raw = m as { type?: string; role?: string };
  return raw.type === "human" || raw.role === "user" || raw.role === "human";
}

function getOffsetTopWithinViewport(el: HTMLElement, vp: HTMLElement): number {
  const elRect = el.getBoundingClientRect();
  const vpRect = vp.getBoundingClientRect();
  if (vpRect.height > 0 || elRect.height > 0) {
    return Math.round(elRect.top - vpRect.top + vp.scrollTop);
  }
  return el.offsetTop;
}

export interface UseChatViewportOptions {
  viewportRef: Ref<HTMLElement | null>;
  contentEndSentinelRef: Ref<HTMLElement | null>;
  displayedMessages: ComputedRef<BaseMessage[]>;
  visible?: Ref<boolean | undefined>;
  isRunning: ComputedRef<boolean>;
  isOverlayOpen: ComputedRef<boolean>;
  onConversationStarted?: () => void;
}

export function useChatViewport(options: UseChatViewportOptions) {
  const bottomSpacerHeightPx = ref(0);
  const userScrolledUp = ref(false);
  const following = ref(true);
  const unreadMessageCount = ref(0);
  const bufferedStreamActivity = ref(false);
  const lastEventAt = ref("");

  let scrollRafId: number | null = null;
  let programmaticScrollUntil = 0;
  let lastKnownScrollTop = 0;
  let parkedScrollTop = 0;

  const turnCount = computed(
    () => options.displayedMessages.value.filter(isHumanLikeMessage).length,
  );

  const liveFollowView = computed(() =>
    buildChatLiveFollowView({
      autoFollowEnabled: following.value && !options.isOverlayOpen.value,
      isRunning: options.isRunning.value,
      unreadMessageCount: unreadMessageCount.value,
      bufferedStreamActivity: bufferedStreamActivity.value,
    }),
  );

  function getLatestUserElement(
    vp: HTMLElement,
    targetTurnIndex?: number,
  ): HTMLElement | null {
    if (typeof targetTurnIndex === "number" && targetTurnIndex >= 0) {
      const targetEl = vp.querySelector<HTMLElement>(
        `article[data-author="user"][data-turn-index="${targetTurnIndex}"]`,
      );
      if (targetEl) return targetEl;
    }
    const userEls = vp.querySelectorAll<HTMLElement>(
      'article[data-author="user"]',
    );
    if (userEls.length > 0) {
      return userEls[userEls.length - 1];
    }
    const lastMarked = vp.querySelectorAll<HTMLElement>(
      'article[data-is-last-user="true"]',
    );
    if (lastMarked.length > 0) {
      return lastMarked[lastMarked.length - 1];
    }
    return null;
  }

  function syncBottomSpacerHeight(): {
    lastUserOffsetTop: number;
    contentBottomOffsetTop: number;
  } {
    const vp = options.viewportRef.value;
    if (options.visible?.value === false) {
      return { lastUserOffsetTop: 0, contentBottomOffsetTop: 0 };
    }
    if (!vp || turnCount.value <= 0) {
      bottomSpacerHeightPx.value = 0;
      return { lastUserOffsetTop: 0, contentBottomOffsetTop: 0 };
    }
    const lastUserEl = getLatestUserElement(vp, turnCount.value - 1);
    const sentinelEl = options.contentEndSentinelRef.value;
    const lastUserOffsetTop = lastUserEl
      ? getOffsetTopWithinViewport(lastUserEl, vp)
      : 0;
    const contentBottomOffsetTop = sentinelEl
      ? getOffsetTopWithinViewport(sentinelEl, vp)
      : Math.max(0, vp.scrollHeight - bottomSpacerHeightPx.value);
    const latestTurnHeightPx = Math.max(
      0,
      contentBottomOffsetTop - lastUserOffsetTop,
    );
    const nextSpacer = computeDynamicBottomSpacerHeight({
      turnCount: turnCount.value,
      viewportClientHeight: vp.clientHeight,
      latestTurnHeightPx,
    });
    // 差值微弱时不反复写 ref，避免每个 token 都引发组件重绘与重排抖动
    if (Math.abs(bottomSpacerHeightPx.value - nextSpacer) > 3) {
      bottomSpacerHeightPx.value = nextSpacer;
    }
    return { lastUserOffsetTop, contentBottomOffsetTop };
  }

  async function anchorLatestUserTurn(smooth = true) {
    if (options.visible?.value === false) return;
    options.onConversationStarted?.();
    if (options.isOverlayOpen.value) return;

    userScrolledUp.value = false;
    following.value = true;
    unreadMessageCount.value = 0;
    bufferedStreamActivity.value = false;
    const currentTurns = turnCount.value;

    const vpPre = options.viewportRef.value;
    if (vpPre && currentTurns > 1) {
      bottomSpacerHeightPx.value = computeDynamicBottomSpacerHeight({
        turnCount: currentTurns,
        viewportClientHeight: vpPre.clientHeight,
        latestTurnHeightPx: 88,
      });
    }

    await nextTick();
    await nextTick();
    const vp = options.viewportRef.value;
    if (!vp) return;

    const expectedTurnIndex = currentTurns - 1;
    let lastUserEl = getLatestUserElement(vp, expectedTurnIndex);

    // 若当前回合元素尚未在 DOM 中完成渲染，再等一个微任务帧
    if (!lastUserEl && expectedTurnIndex > 0) {
      await nextTick();
      lastUserEl = getLatestUserElement(vp, expectedTurnIndex);
    }

    const foundTurnIndex = lastUserEl?.getAttribute("data-turn-index");
    const isTargetTurnMatched =
      !lastUserEl ||
      expectedTurnIndex <= 0 ||
      foundTurnIndex === String(expectedTurnIndex);

    const { lastUserOffsetTop } = syncBottomSpacerHeight();
    await nextTick();

    let targetTop: number;
    if (lastUserEl && isTargetTurnMatched) {
      targetTop = computeTurnAnchorScrollTop({
        turnCount: turnCount.value,
        userElementOffsetTop: lastUserOffsetTop,
        viewportClientHeight: vp.clientHeight,
      });
    } else {
      // 绝不可定位到上一轮历史元素！安全回退到视口底部新内容区
      targetTop = Math.max(0, vp.scrollHeight - vp.clientHeight);
    }

    programmaticScrollUntil = Date.now() + 500;
    lastKnownScrollTop = targetTop;
    if (typeof vp.scrollTo === "function" && smooth) {
      vp.scrollTo({ top: targetTop, behavior: "smooth" });
    } else {
      vp.scrollTop = targetTop;
    }
  }

  function requestSmartStreamingFollow() {
    if (
      options.visible?.value === false ||
      !following.value ||
      userScrolledUp.value ||
      options.isOverlayOpen.value ||
      Date.now() < programmaticScrollUntil
    ) {
      return;
    }
    if (scrollRafId !== null) return;
    scrollRafId = requestAnimationFrame(() => {
      scrollRafId = null;
      const vp = options.viewportRef.value;
      if (
        !vp ||
        options.visible?.value === false ||
        !following.value ||
        userScrolledUp.value ||
        Date.now() < programmaticScrollUntil
      ) {
        return;
      }
      const { contentBottomOffsetTop } = syncBottomSpacerHeight();
      const nextScrollTop = computeStreamingFollowScrollTop({
        currentScrollTop: vp.scrollTop,
        viewportClientHeight: vp.clientHeight,
        contentBottomOffsetTop,
      });
      if (nextScrollTop !== null && nextScrollTop !== vp.scrollTop) {
        // 彻底移除 180ms 机械死锁，改用原生 rAF 帧跟随，保持 60fps/120fps 顺滑
        lastKnownScrollTop = nextScrollTop;
        vp.scrollTop = nextScrollTop;
      }
    });
  }

  async function follow() {
    userScrolledUp.value = false;
    following.value = true;
    unreadMessageCount.value = 0;
    bufferedStreamActivity.value = false;
    await nextTick();
    const vp = options.viewportRef.value;
    if (!vp) return;
    const { lastUserOffsetTop, contentBottomOffsetTop } =
      syncBottomSpacerHeight();
    await nextTick();
    const anchorTop = computeTurnAnchorScrollTop({
      turnCount: turnCount.value,
      userElementOffsetTop: lastUserOffsetTop,
      viewportClientHeight: vp.clientHeight,
    });
    const streamFollowTop = computeStreamingFollowScrollTop({
      currentScrollTop: anchorTop,
      viewportClientHeight: vp.clientHeight,
      contentBottomOffsetTop,
    });
    const targetTop = streamFollowTop ?? anchorTop;
    programmaticScrollUntil = Date.now() + 500;
    lastKnownScrollTop = targetTop;
    if (typeof vp.scrollTo === "function") {
      vp.scrollTo({ top: targetTop, behavior: "smooth" });
    } else {
      vp.scrollTop = targetTop;
    }
  }

  function handleViewportWheel(event: WheelEvent) {
    if (event.deltaY < -2) {
      userScrolledUp.value = true;
      following.value = false;
    }
  }

  function handleViewportScroll() {
    if (options.visible?.value === false) return;
    const vp = options.viewportRef.value;
    if (!vp) return;
    const currentTop = vp.scrollTop;
    const isProgrammatic = Date.now() < programmaticScrollUntil;

    if (isProgrammatic) {
      lastKnownScrollTop = currentTop;
      return;
    }

    if (currentTop < lastKnownScrollTop - 4) {
      userScrolledUp.value = true;
      following.value = false;
    }
    lastKnownScrollTop = currentTop;

    const sentinelEl = options.contentEndSentinelRef.value;
    const contentBottomOffsetTop = sentinelEl
      ? getOffsetTopWithinViewport(sentinelEl, vp)
      : undefined;
    const nearBottom = isChatViewportNearContentBottom(
      vp,
      contentBottomOffsetTop,
    );
    if (nearBottom && !userScrolledUp.value) {
      following.value = true;
      unreadMessageCount.value = 0;
      bufferedStreamActivity.value = false;
    } else if (
      nearBottom &&
      userScrolledUp.value &&
      !isProgrammatic &&
      currentTop >=
        Math.max(
          0,
          (contentBottomOffsetTop ?? vp.scrollHeight) - vp.clientHeight - 40,
        )
    ) {
      userScrolledUp.value = false;
      following.value = true;
      unreadMessageCount.value = 0;
      bufferedStreamActivity.value = false;
    }
  }

  function handleVisibleChange(visible: boolean | undefined) {
    if (visible === false) {
      parkedScrollTop =
        options.viewportRef.value?.scrollTop ?? lastKnownScrollTop;
      if (scrollRafId !== null) cancelAnimationFrame(scrollRafId);
      scrollRafId = null;
      return;
    }
    void nextTick().then(() => {
      syncBottomSpacerHeight();
      const vp = options.viewportRef.value;
      if (vp) {
        vp.scrollTop = parkedScrollTop;
        lastKnownScrollTop = parkedScrollTop;
      }
      requestSmartStreamingFollow();
    });
  }

  if (options.visible) {
    watch(() => options.visible?.value, handleVisibleChange);
  }

  watch(
    options.displayedMessages,
    async (next, previous) => {
      lastEventAt.value = new Date().toISOString();
      if (next.length > 0) {
        options.onConversationStarted?.();
      }
      if (options.visible?.value === false) return;
      const prevHumanCount = (previous ?? []).filter(isHumanLikeMessage).length;
      const nextHumanCount = next.filter(isHumanLikeMessage).length;
      const hasNewUserTurn = nextHumanCount > prevHumanCount;

      if (hasNewUserTurn) {
        userScrolledUp.value = false;
        following.value = true;
        unreadMessageCount.value = 0;
        bufferedStreamActivity.value = false;
        if (options.isOverlayOpen.value) {
          return;
        }
        const isInitialHydration =
          (previous?.length ?? 0) === 0 && next.length > 1;
        await anchorLatestUserTurn(!isInitialHydration);
        return;
      }

      if (!following.value) {
        unreadMessageCount.value += Math.max(
          0,
          next.length - (previous?.length ?? 0),
        );
        bufferedStreamActivity.value = true;
        await nextTick();
        syncBottomSpacerHeight();
        return;
      }

      if (options.isOverlayOpen.value) {
        return;
      }

      if (following.value) {
        await nextTick();
        requestSmartStreamingFollow();
      }
    },
    { flush: "post", deep: true },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (scrollRafId !== null) {
        cancelAnimationFrame(scrollRafId);
        scrollRafId = null;
      }
    });
  }

  return {
    bottomSpacerHeightPx,
    userScrolledUp,
    following,
    unreadMessageCount,
    bufferedStreamActivity,
    liveFollowView,
    turnCount,
    lastEventAt,
    syncBottomSpacerHeight,
    anchorLatestUserTurn,
    requestSmartStreamingFollow,
    follow,
    handleViewportWheel,
    handleViewportScroll,
    handleVisibleChange,
  };
}
