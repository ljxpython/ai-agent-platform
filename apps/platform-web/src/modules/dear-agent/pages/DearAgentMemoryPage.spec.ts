import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";
import DearAgentMemoryPage from "./DearAgentMemoryPage.vue";
import * as memoryService from "@/services/dear-agent/memory.service";
import type { MemoryView } from "@/services/dear-agent/memory.service";

const mockPush = vi.fn();
vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const mockActiveProjectId = ref("proj-1");
const mockActiveProject = ref({ id: "proj-1", name: "智能研发项目" });
const mockCanWrite = ref(true);

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({
    can: () => mockCanWrite.value,
  }),
}));

vi.mock("@/composables/useWorkspaceProjectContext", () => ({
  useWorkspaceProjectContext: () => ({
    activeProject: mockActiveProject,
    activeProjectId: mockActiveProjectId,
  }),
}));

vi.mock("@/services/dear-agent/memory.service", async () => {
  const actual = await vi.importActual<typeof memoryService>(
    "@/services/dear-agent/memory.service",
  );
  return {
    ...actual,
    readMemory: vi.fn(),
    saveMemoryFact: vi.fn(),
    deleteMemoryFact: vi.fn(),
    clearMemory: vi.fn(),
    acceptMemoryCandidate: vi.fn(),
    rejectMemoryCandidate: vi.fn(),
    updateMemorySettings: vi.fn(),
    restoreMemoryFacts: vi.fn(),
  };
});

function createReadyMemoryView(overrides: Partial<MemoryView> = {}): MemoryView {
  return {
    status: "ready",
    scope: { kind: "project_user", project_id: "proj-1", user_id: "user-1" },
    capabilities: { memory_enabled: true, can_read: true, can_write: true },
    limits: {
      fact_text_chars: 1000,
      facts: 100,
      candidates: 100,
      restore_items: 100,
      request_bytes: 1500000,
    },
    document: {
      schema_version: 1,
      revision: 3,
      epoch: 1,
      automatic_candidates: false,
      facts: [
        {
          id: "fact-1",
          text: "用户偏好使用 TypeScript 严谨模式",
          category: "preference",
          expires_at: null,
          origin: "user",
          revision: 1,
          created_at: "2026-09-20T00:00:00Z",
          updated_at: "2026-09-20T00:00:00Z",
          source_kind: "management",
          source_thread_id: null,
          source_message_id: null,
          source_call_id: null,
          quote: null,
        },
      ],
      candidates: [
        {
          id: "cand-1",
          text: "偏好先给结论再展开细节",
          category: "preference",
          expires_at: null,
          origin: "inferred",
          revision: 1,
          created_at: "2026-09-20T01:00:00Z",
          updated_at: "2026-09-20T01:00:00Z",
          source_kind: "user_message",
          source_thread_id: "thread-source-1",
          source_message_id: "msg-1",
          source_call_id: null,
          quote: "以后回答我先给结论再展开细节",
        },
        {
          id: "cand-legacy",
          text: "旧记录无原文候选",
          category: "fact",
          expires_at: null,
          origin: "inferred",
          revision: 1,
          created_at: "2026-09-20T01:05:00Z",
          updated_at: "2026-09-20T01:05:00Z",
          source_kind: "legacy",
          source_thread_id: null,
          source_message_id: null,
          source_call_id: null,
          quote: null,
        },
      ],
    },
    counts: { facts: 1, candidates: 2 },
    extraction: {
      status: "succeeded",
      updated_at: "2026-09-20T01:05:00Z",
      source_thread_id: "thread-source-1",
      candidate_count: 2,
      error_code: null,
      pause_reason: null,
    },
    mutation: null,
    ...overrides,
  };
}

describe("DearAgentMemoryPage.vue (无线程项目内个人记忆视图)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCanWrite.value = true;
    mockActiveProjectId.value = "proj-1";
    mockActiveProject.value = { id: "proj-1", name: "智能研发项目" };
  });

  it("ready_empty: 空库无需创建会话即可直接点击新增事实", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce(
      createReadyMemoryView({
        document: {
          schema_version: 1,
          revision: 0,
          epoch: 0,
          automatic_candidates: false,
          facts: [],
          candidates: [],
        },
        counts: { facts: 0, candidates: 0 },
        extraction: {
          status: "never",
          updated_at: null,
          source_thread_id: null,
          candidate_count: 0,
          error_code: null,
          pause_reason: null,
        },
      }),
    );

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    expect(wrapper.text()).not.toContain("关联会话");
    expect(wrapper.text()).not.toContain("立即创建会话并开启记忆");
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("新增事实"));
    expect(addBtn).toBeDefined();
    expect(addBtn?.attributes("disabled")).toBeUndefined();
  });

  it("disabled: status=disabled 时显示独立说明，不渲染“0 条已生效”假空库", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce({
      status: "disabled",
      scope: { kind: "project_user", project_id: "proj-1", user_id: "user-1" },
      capabilities: { memory_enabled: false, can_read: false, can_write: false },
      limits: {
        fact_text_chars: 1000,
        facts: 100,
        candidates: 100,
        restore_items: 100,
        request_bytes: 1500000,
      },
      document: null,
      counts: null,
      extraction: null,
      mutation: null,
    } satisfies MemoryView);

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    expect(wrapper.text()).toContain("当前环境未启用长期记忆治理");
    expect(wrapper.text()).not.toContain("生效事实总数");
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("新增事实"));
    expect(addBtn?.attributes("disabled")).toBeDefined();
  });

  it("ready_readonly: can_write=false 时禁用全部写操作，但导出仍可用", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce(
      createReadyMemoryView({
        capabilities: { memory_enabled: true, can_read: true, can_write: false },
      }),
    );

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    expect(wrapper.text()).toContain("缺少 project.runtime.execute 权限或服务端只读限制");
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("新增事实"));
    const exportBtn = wrapper.findAll("button").find((b) => b.text().includes("导出 JSON"));
    expect(addBtn?.attributes("disabled")).toBeDefined();
    expect(exportBtn?.attributes("disabled")).toBeUndefined();
  });

  it("candidate_with_quote_and_replace: 展示候选原文、缺失原文降级、来源会话跳转与替换已有事实", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce(createReadyMemoryView());
    (memoryService.acceptMemoryCandidate as any).mockResolvedValueOnce(createReadyMemoryView());

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    const candTab = wrapper.findAll("button").find((b) => b.text().includes("待确认候选"));
    await candTab!.trigger("click");
    await flushPromises();

    // 校验原文与缺失原文降级文案
    expect(wrapper.text()).toContain("以后回答我先给结论再展开细节");
    expect(wrapper.text()).toContain("历史记录缺少原文");

    // 校验来源会话跳转
    const sourceLinkBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("查看来源会话"));
    expect(sourceLinkBtn).toBeDefined();
    await sourceLinkBtn!.trigger("click");
    expect(mockPush).toHaveBeenCalledWith({
      name: "workspace-dear-agent",
      params: { projectId: "proj-1", threadId: "thread-source-1" },
    });

    // 校验替换已有事实交互 (replace_fact_id)
    const replaceBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("替换已有事实"));
    expect(replaceBtn).toBeDefined();
    await replaceBtn!.trigger("click");
    await flushPromises();

    const confirmReplaceBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("确认替换并采纳"));
    expect(confirmReplaceBtn).toBeDefined();
    await confirmReplaceBtn!.trigger("click");
    await flushPromises();

    expect(memoryService.acceptMemoryCandidate).toHaveBeenCalledWith(
      "proj-1",
      3,
      "cand-1",
      "fact-1",
    );
  });

  it("conflict_nested_error: 409 memory_revision_conflict 自动拉新版本、保留表单草稿且持久展示冲突提示", async () => {
    (memoryService.readMemory as any)
      .mockResolvedValueOnce(createReadyMemoryView())
      .mockResolvedValueOnce(
        createReadyMemoryView({
          document: {
            ...createReadyMemoryView().document!,
            revision: 9,
          },
        }),
      );

    (memoryService.saveMemoryFact as any).mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          request_id: "req-409",
          error: {
            code: "memory_revision_conflict",
            message: "Memory has changed.",
          },
        },
      },
    });

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    // 打开新增弹窗并输入草稿
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("新增事实"));
    await addBtn!.trigger("click");
    await flushPromises();

    const textarea = wrapper.find("textarea");
    await textarea.setValue("我的重要草稿内容不丢失");

    const submitBtn = wrapper.findAll("button").find((b) => b.text().includes("保存提交"));
    await submitBtn!.trigger("click");
    await flushPromises();

    // 1. 自动重新调用了 readMemory 同步最新 revision
    expect(memoryService.readMemory).toHaveBeenCalledTimes(2);
    // 2. 冲突提示未被第二次 readMemory 清掉
    expect(wrapper.text()).toContain("版本冲突");
    // 3. 弹窗草稿仍然保留
    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe(
      "我的重要草稿内容不丢失",
    );
    // 4. 不会自动重发 saveMemoryFact
    expect(memoryService.saveMemoryFact).toHaveBeenCalledTimes(1);
  });

  it("project_switch_out_of_order: 项目 A/B 反序返回时只保留当前项目 B 的数据", async () => {
    let resolveProjA!: (val: MemoryView) => void;
    const promiseProjA = new Promise<MemoryView>((resolve) => {
      resolveProjA = resolve;
    });

    (memoryService.readMemory as any).mockImplementation((projId: string) => {
      if (projId === "proj-1") return promiseProjA;
      return Promise.resolve(
        createReadyMemoryView({
          scope: { kind: "project_user", project_id: "proj-2", user_id: "user-1" },
          document: {
            schema_version: 1,
            revision: 5,
            epoch: 1,
            automatic_candidates: false,
            facts: [
              {
                id: "fact-b",
                text: "属于项目 B 的专属记忆",
                category: "fact",
                expires_at: null,
                origin: "user",
                revision: 1,
                created_at: "2026-09-20T00:00:00Z",
                updated_at: "2026-09-20T00:00:00Z",
                source_kind: "management",
                source_thread_id: null,
                source_message_id: null,
                source_call_id: null,
                quote: null,
              },
            ],
            candidates: [],
          },
        }),
      );
    });

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    // 切换到项目 B
    mockActiveProjectId.value = "proj-2";
    await flushPromises();

    // 此时项目 A 的慢响应才返回
    resolveProjA(createReadyMemoryView());
    await flushPromises();

    expect(wrapper.text()).toContain("属于项目 B 的专属记忆");
    expect(wrapper.text()).not.toContain("用户偏好使用 TypeScript 严谨模式");
  });

  it("restore_duplicates_and_validation: 拦截非法分类，合法提交按服务端 added/skipped 显示结果", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce(createReadyMemoryView());
    (memoryService.restoreMemoryFacts as any).mockResolvedValueOnce(
      createReadyMemoryView({
        mutation: { action: "restore", changed: true, added: 1, updated: 0, removed: 0, skipped: 2 },
      }),
    );

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    const openImportBtn = wrapper.findAll("button").find((b) => b.text().includes("追加导入"));
    await openImportBtn!.trigger("click");
    await flushPromises();

    const importTextarea = wrapper.findAll("textarea")[0];
    // 填入非法分类 knowledge
    await importTextarea.setValue(JSON.stringify([{ text: "测试", category: "knowledge" }]));
    await flushPromises();

    expect(wrapper.text()).toContain('非法分类 "knowledge"');
    const confirmImportBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("确认追加导入"));
    expect(confirmImportBtn?.attributes("disabled")).toBeDefined();

    // 改为合法 JSON
    await importTextarea.setValue(
      JSON.stringify([{ text: "使用 Python 3.12", category: "fact", expires_at: null }]),
    );
    await flushPromises();

    expect(confirmImportBtn?.attributes("disabled")).toBeUndefined();
    await confirmImportBtn!.trigger("click");
    await flushPromises();

    expect(memoryService.restoreMemoryFacts).toHaveBeenCalledWith("proj-1", 3, [
      { text: "使用 Python 3.12", category: "fact", expires_at: null },
    ]);
    expect(wrapper.text()).toContain("新增 1 条事实，跳过 2 条重复项");
  });

  it("storage_error: 503 memory_storage_unavailable 显示 request_id 与重试按钮，不渲染假空库", async () => {
    (memoryService.readMemory as any).mockRejectedValueOnce({
      response: {
        status: 503,
        data: {
          request_id: "req-503-pg",
          error: {
            code: "memory_storage_unavailable",
            message: "Database down",
          },
        },
      },
    });

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    expect(wrapper.text()).toContain("记忆存储服务暂不可用（503）");
    expect(wrapper.text()).toContain("req-503-pg");
    expect(wrapper.text()).not.toContain("生效事实总数");
  });

  it("editing fact: 未修改到期日期时原样保留原 expires_at ISO，导出 JSON 调用 fresh GET 与 revokeObjectURL", async () => {
    const initialView = createReadyMemoryView({
      document: {
        schema_version: 1,
        revision: 4,
        epoch: 1,
        automatic_candidates: false,
        facts: [
          {
            id: "fact-exp",
            text: "原始带到期时间的事实",
            category: "fact",
            expires_at: "2027-06-15T10:30:00Z",
            origin: "user",
            revision: 1,
            created_at: "2026-09-20T00:00:00Z",
            updated_at: "2026-09-20T00:00:00Z",
            source_kind: "management",
            source_thread_id: null,
            source_message_id: null,
            source_call_id: null,
            quote: null,
          },
        ],
        candidates: [],
      },
    });
    (memoryService.readMemory as any)
      .mockResolvedValueOnce(initialView)
      .mockResolvedValueOnce(initialView);
    (memoryService.saveMemoryFact as any).mockResolvedValueOnce(initialView);

    const createObjUrlMock = vi.fn().mockReturnValue("blob:dear-memory-test");
    const revokeObjUrlMock = vi.fn();
    URL.createObjectURL = createObjUrlMock;
    URL.revokeObjectURL = revokeObjUrlMock;
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const wrapper = mount(DearAgentMemoryPage, { global: { stubs: { teleport: true } } });
    await flushPromises();

    // 点击编辑按钮，只修改 text 不改日期
    const editBtn = wrapper.find('button[title="编辑事实"]');
    await editBtn.trigger("click");
    await flushPromises();

    await wrapper.find("textarea").setValue("修改文本但保留原到期时间");
    const submitBtn = wrapper.findAll("button").find((b) => b.text().includes("保存提交"));
    await submitBtn!.trigger("click");
    await flushPromises();

    expect(memoryService.saveMemoryFact).toHaveBeenCalledWith(
      "proj-1",
      4,
      {
        text: "修改文本但保留原到期时间",
        category: "fact",
        expires_at: "2027-06-15T10:30:00Z",
      },
      "fact-exp",
    );

    // 点击导出 JSON
    const exportBtn = wrapper.findAll("button").find((b) => b.text().includes("导出 JSON"));
    await exportBtn!.trigger("click");
    await flushPromises();

    expect(memoryService.readMemory).toHaveBeenCalledTimes(2);
    expect(createObjUrlMock).toHaveBeenCalled();
    expect(revokeObjUrlMock).toHaveBeenCalledWith("blob:dear-memory-test");

    clickSpy.mockRestore();
  });
});
