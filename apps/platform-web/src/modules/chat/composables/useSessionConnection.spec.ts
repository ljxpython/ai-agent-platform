import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, effectScope, nextTick, ref, shallowRef } from "vue";
import { useSessionConnection } from "./useSessionConnection";

const mockUseStream = vi.fn((_opts: { threadId: { value: string | null } }) => {
  const thread = {
    onConnectionChange: vi.fn(),
    getConnectionState: () => ({ state: "connected", streams: [] }),
    reconnectEvents: vi.fn(),
    suspendEvents: vi.fn(),
  };
  return {
    getThread: () => thread,
    isLoading: ref(false),
    disconnect: vi.fn(),
  };
});

vi.mock("@langchain/vue", () => ({
  useStream: (opts: any) => mockUseStream(opts),
}));

describe("useSessionConnection", () => {
  let scope: ReturnType<typeof effectScope>;
  beforeEach(() => {
    scope = effectScope();
  });
  afterEach(() => {
    scope.stop();
  });

  it("initializes with default review access policy", () => {
    const threadId = ref<string | null>("thread-1");
    const canWrite = ref(true);
    const run = shallowRef(null);
    const busy = computed(() => false);
    const checking = ref(false);
    const hasPendingReviews = computed(() => false);
    const hydrated = ref(true);

    const mockService = {
      client: {} as any,
      get: vi.fn(),
      state: vi.fn(),
      history: vi.fn(),
    } as any;

    const mockActions = {
      fetch: vi.fn(),
    } as any;

    const conn = scope.run(() =>
      useSessionConnection({
        projectId: "proj-1",
        graphId: "chat",
        threadId,
        canWrite,
        service: mockService,
        actions: mockActions,
        run,
        busy,
        checking,
        hasPendingReviews,
        hydrated,
        getCheckEpoch: () => 0,
        onVerify: vi.fn().mockResolvedValue(undefined),
        onFail: vi.fn(),
      }),
    );

    expect(conn!.accessPolicy.value).toBe("review");
    expect(conn!.accessDenied.value).toBe(false);
  });

  it("normalizes empty or whitespace threadId to null for useStream", () => {
    mockUseStream.mockClear();
    const threadId = ref<string | null>("");
    const mockService = { client: {} as any } as any;
    const mockActions = { fetch: vi.fn() } as any;

    scope.run(() =>
      useSessionConnection({
        projectId: "proj-1",
        graphId: "chat",
        threadId,
        canWrite: ref(true),
        service: mockService,
        actions: mockActions,
        run: shallowRef(null),
        busy: computed(() => false),
        checking: ref(false),
        hasPendingReviews: computed(() => false),
        hydrated: ref(true),
        getCheckEpoch: () => 0,
        onVerify: vi.fn().mockResolvedValue(undefined),
        onFail: vi.fn(),
      }),
    );

    expect(mockUseStream).toHaveBeenCalled();
    const callArgs = mockUseStream.mock.calls[0]?.[0];
    expect(callArgs.threadId.value).toBeNull();

    threadId.value = "   ";
    expect(callArgs.threadId.value).toBeNull();

    threadId.value = " valid-thread-id ";
    expect(callArgs.threadId.value).toBe("valid-thread-id");
  });
});

describe("scoped access refresh", () => {
  const scopes: ReturnType<typeof effectScope>[] = [];
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(document, "hidden", "get").mockReturnValue(false);
  });
  afterEach(() => {
    scopes.splice(0).forEach((scope) => scope.stop());
    vi.restoreAllMocks();
    vi.useRealTimers();
  });
  function session(id: string, visible = ref<boolean | undefined>(true)) {
    const get = vi.fn().mockResolvedValue({
      thread_id: id,
      metadata: { allowed_actions: ["read", "comment"] },
    });
    const revoked = vi.fn();
    const scope = effectScope();
    scopes.push(scope);
    const connection = scope.run(() =>
      useSessionConnection({
        projectId: "p",
        graphId: "g",
        threadId: ref(id),
        visible,
        canWrite: ref(true),
        service: { client: {}, get } as never,
        actions: { fetch: vi.fn() } as never,
        run: shallowRef(null),
        busy: computed(() => false),
        checking: ref(false),
        hasPendingReviews: computed(() => false),
        hydrated: ref(true),
        getCheckEpoch: () => 0,
        onVerify: vi.fn(),
        onFail: vi.fn(),
        onAccessRevoked: revoked,
      }),
    )!;
    return { connection, get, revoked };
  }
  it("refreshes only visible sessions on focus and only the rejected thread on a scoped event", async () => {
    const active = session("active");
    const background = session("background", ref(false));
    window.dispatchEvent(new Event("focus"));
    await vi.advanceTimersByTimeAsync(0);
    expect(active.get).toHaveBeenCalledOnce();
    expect(background.get).not.toHaveBeenCalled();
    window.dispatchEvent(
      new CustomEvent("platform-access-denied", {
        detail: { scope: "thread", projectId: "p", threadId: "background" },
      }),
    );
    await vi.advanceTimersByTimeAsync(0);
    expect(background.get).toHaveBeenCalledOnce();
    expect(active.get).toHaveBeenCalledOnce();
    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
    expect(active.get).toHaveBeenCalledOnce();
  });
  it("still checks background subscriptions for real revocation every minute", async () => {
    const item = session("background", ref(false));
    item.get.mockRejectedValue({ status: 403 });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(item.get).toHaveBeenCalledOnce();
    expect(item.revoked).toHaveBeenCalledOnce();
  });
  it("retains content on unavailable ACL and revokes only after authoritative rejection", async () => {
    const item = session("t");
    await item.connection.refreshAccessPolicy();
    item.get.mockRejectedValueOnce({ status: 503 });
    await item.connection.refreshAccessPolicy();
    expect(item.connection.canRead.value).toBe(true);
    expect(item.connection.accessUncertain.value).toBe(true);
    expect(item.revoked).not.toHaveBeenCalled();
    item.get.mockRejectedValueOnce({ status: 403 });
    await item.connection.refreshAccessPolicy();
    expect(item.connection.canRead.value).toBe(false);
    expect(item.revoked).toHaveBeenCalledOnce();
  });
  it("rechecks thread access instead of deleting a session for a missing stream resource", async () => {
    const item = session("t");
    const callback = mockUseStream.mock.results.at(-1)!.value.getThread()
      .onConnectionChange.mock.calls[0][0];
    callback({ state: "paused", streams: [{ error: { status: 404 } }] });
    await vi.advanceTimersByTimeAsync(0);
    expect(item.get).toHaveBeenCalledOnce();
    expect(item.revoked).not.toHaveBeenCalled();
    expect(item.connection.canRead.value).toBe(true);
  });
  it("parks subscriptions opened after a session entered the background", async () => {
    const item = session("background", ref(false));
    const thread = mockUseStream.mock.results.at(-1)!.value.getThread();
    const callback = thread.onConnectionChange.mock.calls[0][0];
    callback({ state: "connecting", streams: [{ state: "connecting" }] });
    expect(thread.suspendEvents).not.toHaveBeenCalled();
    callback({ state: "connected", streams: [{ state: "connected" }] });
    expect(thread.suspendEvents).toHaveBeenCalledOnce();
    expect(item.connection.eventsParked.value).toBe(true);
    await item.connection.reconnectStream();
    expect(thread.reconnectEvents).not.toHaveBeenCalled();
  });
  it("checks a background session when it becomes visible", async () => {
    const visible = ref<boolean | undefined>(false);
    const item = session("t", visible);
    visible.value = true;
    await nextTick();
    await vi.advanceTimersByTimeAsync(0);
    expect(item.get).toHaveBeenCalledOnce();
  });
});
