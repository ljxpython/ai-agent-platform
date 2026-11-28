import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { usePlatformAssistantStore } from "./usePlatformAssistantStore";
import * as clientService from "../services/client";

vi.mock("../services/client", () => ({
  bootstrapAssistant: vi.fn(),
  getAssistantCapabilities: vi.fn(),
}));

describe("usePlatformAssistantStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("控制抽屉 open, close, toggle 状态切换", () => {
    const store = usePlatformAssistantStore();
    expect(store.isOpen).toBe(false);

    store.open();
    expect(store.isOpen).toBe(true);

    store.close();
    expect(store.isOpen).toBe(false);

    store.toggle();
    expect(store.isOpen).toBe(true);
  });

  it("通过 openWithDiagnostic 挂载错误上下文并自动开启抽屉", () => {
    const store = usePlatformAssistantStore();
    const mockContext = {
      title: "500 Internal Server Error",
      summary: "接口超时",
      diagnosticMarkdown: "# 排障包\n- Trace: tr-123",
      projectId: "proj-1",
      traceId: "tr-123",
    };

    store.openWithDiagnostic(mockContext);
    expect(store.isOpen).toBe(true);
    expect(store.hasAttachedContext).toBe(true);
    expect(store.attachedContext?.traceId).toBe("tr-123");

    store.clearAttachedContext();
    expect(store.hasAttachedContext).toBe(false);
    expect(store.attachedContext).toBeNull();
  });

  it("ensureBootstrap 成功初始化并缓存配置", async () => {
    const store = usePlatformAssistantStore();
    vi.mocked(clientService.bootstrapAssistant).mockResolvedValue({
      project_id: "proj-auto-created",
      personal_project: true,
      assistant_id: "platform_assistant",
      agent_id: "agent-1",
      model_id: "model-1",
      history: true,
    });
    vi.mocked(clientService.getAssistantCapabilities).mockResolvedValue({
      enabled: true,
      graph_id: "platform_assistant",
      history: true,
      long_term_memory: false,
      sandbox: false,
      write_tools: [],
      source: false,
      databases: ["platform-local"],
    });

    const config = await store.ensureBootstrap();
    expect(config.project_id).toBe("proj-auto-created");
    expect(store.boundProjectId).toBe("proj-auto-created");
    expect(store.isPersonalProject).toBe(true);
    expect(store.currentModelId).toBe("model-1");
    expect(store.capabilities?.enabled).toBe(true);

    // 再次调用同一目标项目，复用缓存不重复请求
    await store.ensureBootstrap("proj-auto-created");
    expect(clientService.bootstrapAssistant).toHaveBeenCalledTimes(1);
  });

  it("错误目标项目不切换已有助手会话，显式切换项目才清除旧会话编号", async () => {
    const store = usePlatformAssistantStore();
    const config = {
      project_id: "assistant-project",
      personal_project: true,
      assistant_id: "platform_assistant",
      agent_id: "a",
      model_id: "m",
      history: true,
    };
    store.bootstrapConfig = config;
    store.activeThreadId = "assistant-thread";
    store.openWithDiagnostic({
      title: "错误",
      diagnosticMarkdown: "诊断",
      projectId: "business-project",
    });
    expect(store.boundProjectId).toBe("assistant-project");
    expect(store.activeThreadId).toBe("assistant-thread");
    expect(clientService.bootstrapAssistant).not.toHaveBeenCalled();
    vi.mocked(clientService.bootstrapAssistant).mockResolvedValue({
      ...config,
      project_id: "other-project",
    });
    await store.ensureBootstrap("other-project");
    expect(store.activeThreadId).toBeNull();
  });

  it("支持设置选中的模型并正确计算 currentModelId 与 defaultModelName", () => {
    const store = usePlatformAssistantStore();
    store.bootstrapConfig = {
      project_id: "proj-1",
      personal_project: true,
      assistant_id: "platform_assistant",
      agent_id: "a-1",
      model_id: "model-default",
      history: true,
    };
    store.availableModels = [
      {
        id: "model-default",
        model: "deepseek-chat",
        display_name: "DeepSeek 官方",
        provider: "deepseek",
        api_style: "openai-compatible",
        base_url: "https://api.deepseek.com",
        protocol: "openai-compatible",
        credential_configured: true,
        enabled: true,
        scope_type: "platform",
      },
      {
        id: "model-custom",
        model: "qwen-plus",
        display_name: "通义千问 Plus",
        provider: "qwen",
        api_style: "openai-compatible",
        base_url: "https://dashscope.aliyuncs.com",
        protocol: "openai-compatible",
        credential_configured: true,
        enabled: true,
        scope_type: "platform",
      },
    ];

    // 默认情况下，currentModelId 为 bootstrap 返回的 model_id，defaultModelName 正确匹配
    expect(store.currentModelId).toBe("model-default");
    expect(store.defaultModelId).toBe("model-default");
    expect(store.defaultModelName).toBe("DeepSeek 官方");

    // 用户切换模型
    store.setSelectedModelId("model-custom");
    expect(store.selectedModelId).toBe("model-custom");
    expect(store.currentModelId).toBe("model-custom");

    // 用户重置为跟随默认配置
    store.setSelectedModelId("");
    expect(store.selectedModelId).toBe("");
    expect(store.currentModelId).toBe("model-default");
  });
});
