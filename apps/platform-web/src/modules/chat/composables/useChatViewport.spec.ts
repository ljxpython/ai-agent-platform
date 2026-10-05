import { describe, expect, it, vi } from "vitest";
import { computed, nextTick, ref } from "vue";
import { useChatViewport } from "./useChatViewport";
import type { BaseMessage } from "@langchain/core/messages";

describe("useChatViewport", () => {
  it("computes turn count and initial states correctly", () => {
    const viewportRef = ref<HTMLElement | null>(null);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    const messages = ref<BaseMessage[]>([
      { type: "human", content: "hello" } as unknown as BaseMessage,
      { type: "ai", content: "hi" } as unknown as BaseMessage,
      { type: "human", content: "how are you" } as unknown as BaseMessage,
    ]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    expect(viewport.following.value).toBe(true);
    expect(viewport.userScrolledUp.value).toBe(false);
    expect(viewport.unreadMessageCount.value).toBe(0);
    expect(viewport.turnCount.value).toBe(2);
  });

  it("handles wheel up by stopping follow mode", () => {
    const viewportRef = ref<HTMLElement | null>(null);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    const messages = ref<BaseMessage[]>([]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    viewport.handleViewportWheel({ deltaY: -10 } as WheelEvent);
    expect(viewport.userScrolledUp.value).toBe(true);
    expect(viewport.following.value).toBe(false);
  });

  it("resumes follow mode when follow() is called", async () => {
    const dummyVp = document.createElement("div");
    dummyVp.scrollTop = 100;
    const viewportRef = ref<HTMLElement | null>(dummyVp);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    const messages = ref<BaseMessage[]>([]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    viewport.handleViewportWheel({ deltaY: -10 } as WheelEvent);
    expect(viewport.following.value).toBe(false);

    await viewport.follow();
    expect(viewport.following.value).toBe(true);
    expect(viewport.userScrolledUp.value).toBe(false);
  });

  it("does not treat programmatic smooth scroll intermediate events as user scroll up", async () => {
    const dummyVp = document.createElement("div");
    dummyVp.scrollTop = 200;
    const viewportRef = ref<HTMLElement | null>(dummyVp);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    const messages = ref<BaseMessage[]>([
      { type: "human", content: "turn 1" } as unknown as BaseMessage,
      { type: "ai", content: "reply 1" } as unknown as BaseMessage,
    ]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    // Simulate programmatic scroll in progress
    await viewport.anchorLatestUserTurn(false);
    expect(viewport.following.value).toBe(true);
    expect(viewport.userScrolledUp.value).toBe(false);

    // During programmatic scroll window, intermediate scroll events must NOT break follow mode
    dummyVp.scrollTop = 150;
    viewport.handleViewportScroll();
    expect(viewport.following.value).toBe(true);
    expect(viewport.userScrolledUp.value).toBe(false);
  });

  it("automatically recovers following and resets userScrolledUp when a new user turn is added", async () => {
    const dummyVp = document.createElement("div");
    const viewportRef = ref<HTMLElement | null>(dummyVp);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    const messages = ref<BaseMessage[]>([
      { type: "human", content: "turn 1" } as unknown as BaseMessage,
      { type: "ai", content: "reply 1" } as unknown as BaseMessage,
    ]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    // User scrolled up during turn 1
    viewport.handleViewportWheel({ deltaY: -10 } as WheelEvent);
    expect(viewport.following.value).toBe(false);
    expect(viewport.userScrolledUp.value).toBe(true);

    // Turn 2 is added (e.g. user sends a new message or queued message drains)
    messages.value = [
      ...messages.value,
      { type: "human", content: "turn 2" } as unknown as BaseMessage,
    ];
    await nextTick();
    await nextTick();

    // Following must be restored for the new user turn
    expect(viewport.following.value).toBe(true);
    expect(viewport.userScrolledUp.value).toBe(false);
    expect(viewport.unreadMessageCount.value).toBe(0);
  });

  it("does not scroll backwards to previous turn when latest turn DOM element is not yet rendered", async () => {
    const dummyVp = document.createElement("div");
    // 模拟只有第一轮的 DOM 元素
    const turn0UserEl = document.createElement("article");
    turn0UserEl.setAttribute("data-author", "user");
    turn0UserEl.setAttribute("data-turn-index", "0");
    Object.defineProperty(turn0UserEl, "offsetTop", {
      value: 100,
      configurable: true,
    });
    dummyVp.appendChild(turn0UserEl);

    dummyVp.scrollTop = 500;
    Object.defineProperty(dummyVp, "scrollHeight", {
      value: 1200,
      configurable: true,
    });
    Object.defineProperty(dummyVp, "clientHeight", {
      value: 600,
      configurable: true,
    });

    const viewportRef = ref<HTMLElement | null>(dummyVp);
    const contentEndSentinelRef = ref<HTMLElement | null>(null);
    // 逻辑上有 2 轮
    const messages = ref<BaseMessage[]>([
      { type: "human", content: "turn 1" } as unknown as BaseMessage,
      { type: "ai", content: "reply 1" } as unknown as BaseMessage,
      { type: "human", content: "turn 2" } as unknown as BaseMessage,
    ]);

    const viewport = useChatViewport({
      viewportRef,
      contentEndSentinelRef,
      displayedMessages: computed(() => messages.value),
      isRunning: computed(() => false),
      isOverlayOpen: computed(() => false),
    });

    await viewport.anchorLatestUserTurn(false);

    // 此时虽然 turnCount 为 2，但 DOM 只有 turn 0，绝不能滚到 100 - desiredTopOffset（即倒滚到上一个对话）！
    // 应当安全回退到当前内容底部（scrollHeight - clientHeight = 600）
    expect(dummyVp.scrollTop).toBeGreaterThanOrEqual(500);
  });
});
