import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { usePlatformAssistantSession } from "./usePlatformAssistantSession";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { createAssistantScopedClient } from "../services/client";

vi.mock("../services/client", () => ({
  createAssistantScopedClient: vi.fn(),
  bootstrapAssistant: vi.fn(),
  getAssistantCapabilities: vi.fn(),
}));

describe("助手会话失败与项目作用域", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });
  it.each(["send", "history"])(
    "%s 收到403后清空旧消息及证据缓存",
    async (action) => {
      const store = usePlatformAssistantStore();
      const config = {
        project_id: "p",
        personal_project: true,
        assistant_id: "platform_assistant",
        agent_id: "a",
        model_id: "m",
        history: true,
      };
      store.bootstrapConfig = config;
      vi.spyOn(store, "ensureBootstrap").mockResolvedValue(config);
      const getState = vi.fn().mockResolvedValue({
        values: {
          messages: [
            { type: "ai", content: "旧资料" },
            {
              type: "tool",
              content: JSON.stringify({
                evidence_id: "evidence-private",
                operation: "diagnostics",
                data: { run_status: "success" },
              }),
            },
          ],
        },
      });
      const denied = Object.assign(new Error("请求失败（HTTP 403）"), {
        status: 403,
      });
      const stream = vi.fn().mockImplementation(() => {
        throw denied;
      });
      vi.mocked(createAssistantScopedClient).mockReturnValue({
        threads: { getState },
        runs: { stream },
      } as unknown as ReturnType<typeof createAssistantScopedClient>);
      const session = usePlatformAssistantSession();
      await session.loadThread("old-thread");
      session.evidenceLookup.openEvidence("evidence-private");
      if (action === "send") await session.sendMessage("继续读取");
      else {
        getState.mockRejectedValueOnce(denied);
        await session.loadThread("another-thread");
      }
      expect(session.messages.value).toEqual([]);
      expect(session.threadId.value).toBeNull();
      expect(store.activeThreadId).toBeNull();
      expect(session.evidenceLookup.evidenceMap.value.size).toBe(0);
      expect(session.evidenceLookup.activeEvidence.value).toBeNull();
      expect(session.errorBanner.value).toContain("权限");
      expect(session.turnStatus.value).toBe("error");
    },
  );
  it("初始化失败转为可见错误，不创建会话也不抛出未处理异常", async () => {
    const store = usePlatformAssistantStore();
    vi.spyOn(store, "ensureBootstrap").mockRejectedValue(
      new Error("助手API不可用"),
    );
    const session = usePlatformAssistantSession();
    await session.sendMessage("排查", {
      title: "错误",
      diagnosticMarkdown: "已有诊断",
    });
    expect(session.turnStatus.value).toBe("error");
    expect(session.errorBanner.value).toBe("助手API不可用");
    expect(createAssistantScopedClient).not.toHaveBeenCalled();
  });
  it("项目绑定变化后重建客户端，不复用另一项目的请求头", async () => {
    const store = usePlatformAssistantStore();
    const config = {
      project_id: "first",
      personal_project: false,
      assistant_id: "platform_assistant",
      agent_id: "a",
      model_id: "m",
      history: true,
    };
    store.bootstrapConfig = config;
    vi.spyOn(store, "ensureBootstrap").mockResolvedValue(config);
    const create = vi
      .fn()
      .mockRejectedValue(new Error("synthetic unavailable"));
    vi.mocked(createAssistantScopedClient).mockReturnValue({
      threads: { create },
    } as unknown as ReturnType<typeof createAssistantScopedClient>);
    const session = usePlatformAssistantSession();
    await session.sendMessage("first");
    store.bootstrapConfig = { ...config, project_id: "second" };
    await session.sendMessage("second");
    expect(vi.mocked(createAssistantScopedClient).mock.calls).toEqual([
      ["first"],
      ["second"],
    ]);
  });

  it.each(["project", "new-session"])(
    "%s 切换后丢弃晚到的旧历史，不恢复旧Thread和证据",
    async (change) => {
      const store = usePlatformAssistantStore();
      const config = {
        project_id: "first",
        personal_project: false,
        assistant_id: "platform_assistant",
        agent_id: "a",
        model_id: "m",
        history: true,
      };
      store.bootstrapConfig = config;
      vi.spyOn(store, "ensureBootstrap").mockResolvedValue(config);
      let complete!: (state: unknown) => void;
      const getState = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            complete = resolve;
          }),
      );
      vi.mocked(createAssistantScopedClient).mockReturnValue({
        threads: { getState },
      } as unknown as ReturnType<typeof createAssistantScopedClient>);
      const session = usePlatformAssistantSession();
      const loading = session.loadThread("old-thread");
      await vi.waitFor(() => expect(getState).toHaveBeenCalled());
      if (change === "project") {
        store.bootstrapConfig = { ...config, project_id: "second" };
      } else {
        session.startNewSession();
      }
      complete({
        values: { messages: [{ type: "ai", content: "旧项目消息" }] },
      });
      await loading;
      expect(session.threadId.value).toBeNull();
      expect(store.activeThreadId).toBeNull();
      expect(session.messages.value).toEqual([]);
      expect(session.turnStatus.value).toBe("idle");
    },
  );

  it("项目切换后不采用晚到的Thread创建结果，也不发送到旧项目", async () => {
    const store = usePlatformAssistantStore();
    const config = {
      project_id: "first",
      personal_project: false,
      assistant_id: "platform_assistant",
      agent_id: "a",
      model_id: "m",
      history: true,
    };
    store.bootstrapConfig = config;
    vi.spyOn(store, "ensureBootstrap").mockResolvedValue(config);
    let complete!: (thread: unknown) => void;
    const create = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    );
    const stream = vi.fn();
    vi.mocked(createAssistantScopedClient).mockReturnValue({
      threads: { create },
      runs: { stream },
    } as unknown as ReturnType<typeof createAssistantScopedClient>);
    const session = usePlatformAssistantSession();
    const sending = session.sendMessage("合成测试");
    await vi.waitFor(() => expect(create).toHaveBeenCalled());
    store.bootstrapConfig = { ...config, project_id: "second" };
    complete({ thread_id: "old-thread" });
    await sending;
    expect(stream).not.toHaveBeenCalled();
    expect(session.threadId.value).toBeNull();
    expect(store.activeThreadId).toBeNull();
  });
});
