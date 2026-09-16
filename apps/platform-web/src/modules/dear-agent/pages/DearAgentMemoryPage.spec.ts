import { describe, expect, it, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { ref } from "vue";
import DearAgentMemoryPage from "./DearAgentMemoryPage.vue";
import * as memoryService from "@/services/dear-agent/memory.service";

const mockActiveProjectId = ref("proj-1");
const mockActiveThreadId = ref("th-1");
const mockHasThreads = ref(true);
const mockThreads = ref([{ thread_id: "th-1", metadata: { title: "会话1", graph_id: "dearflow_agent" } }]);
const mockCreateInitialThread = vi.fn();
const mockCanWrite = ref(true);

vi.mock("@/composables/useAuthorization", () => ({
  useAuthorization: () => ({
    can: () => mockCanWrite.value,
  }),
}));

vi.mock("../composables/useDearGovernanceContext", () => ({
  useDearGovernanceContext: () => ({
    activeProject: ref({ id: "proj-1", name: "测试项目" }),
    activeProjectId: mockActiveProjectId,
    threads: mockThreads,
    activeThreadId: mockActiveThreadId,
    hasThreads: mockHasThreads,
    loading: ref(false),
    isCreatingThread: ref(false),
    switchThread: vi.fn(),
    createInitialThread: mockCreateInitialThread,
  }),
}));

vi.mock("@/services/dear-agent/memory.service", () => ({
  readMemory: vi.fn(),
  saveMemoryFact: vi.fn(),
  deleteMemoryFact: vi.fn(),
  clearMemory: vi.fn(),
  acceptMemoryCandidate: vi.fn(),
  rejectMemoryCandidate: vi.fn(),
  updateMemorySettings: vi.fn(),
  restoreMemoryFacts: vi.fn(),
}));

describe("DearAgentMemoryPage.vue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCanWrite.value = true;
    mockHasThreads.value = true;
    mockActiveThreadId.value = "th-1";
  });

  it("正确载入并展示已生效记忆事实", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce({
      schema_version: 1,
      revision: 3,
      epoch: 0,
      automatic_candidates: false,
      facts: [
        {
          id: "fact-1",
          text: "用户偏好使用 TypeScript 严谨模式",
          category: "preference",
          origin: "user",
          revision: 1,
          created_at: "2026-09-16T00:00:00Z",
          updated_at: "2026-09-16T00:00:00Z",
        },
      ],
      candidates: [
        {
          id: "cand-1",
          text: "用户可能喜欢简洁的输出",
          category: "preference",
          origin: "inferred",
          revision: 1,
          created_at: "2026-09-16T00:00:00Z",
          updated_at: "2026-09-16T00:00:00Z",
        },
      ],
    });

    const wrapper = mount(DearAgentMemoryPage);
    await flushPromises();

    expect(wrapper.text()).toContain("长期记忆与偏好治理");
    expect(wrapper.text()).toContain("用户偏好使用 TypeScript 严谨模式");
    expect(wrapper.text()).toContain("偏好规则");
  });

  it("切换到候选 Tab 并点击采纳", async () => {
    (memoryService.readMemory as any).mockResolvedValueOnce({
      schema_version: 1,
      revision: 3,
      epoch: 0,
      automatic_candidates: false,
      facts: [],
      candidates: [
        {
          id: "cand-1",
          text: "推断偏好：优先使用 vitest",
          category: "preference",
          origin: "inferred",
          revision: 1,
          created_at: "2026-09-16T00:00:00Z",
          updated_at: "2026-09-16T00:00:00Z",
        },
      ],
    });
    (memoryService.acceptMemoryCandidate as any).mockResolvedValueOnce({
      schema_version: 1,
      revision: 4,
      epoch: 0,
      automatic_candidates: false,
      facts: [
        {
          id: "cand-1",
          text: "推断偏好：优先使用 vitest",
          category: "preference",
          origin: "confirmed",
          revision: 2,
          created_at: "2026-09-16T00:00:00Z",
          updated_at: "2026-09-16T00:00:00Z",
        },
      ],
      candidates: [],
    });

    const wrapper = mount(DearAgentMemoryPage);
    await flushPromises();

    // 找到推断候选 tab
    const candidateTabBtn = wrapper.findAll("button").find((b) => b.text().includes("推断候选"));
    expect(candidateTabBtn).toBeDefined();
    await candidateTabBtn!.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("推断偏好：优先使用 vitest");

    const acceptBtn = wrapper.findAll("button").find((b) => b.text().includes("采纳为事实"));
    expect(acceptBtn).toBeDefined();
    await acceptBtn!.trigger("click");
    await flushPromises();

    expect(memoryService.acceptMemoryCandidate).toHaveBeenCalledWith("proj-1", "th-1", 3, "cand-1");
  });

  it("无会话时展示空态并允许一键创建", async () => {
    mockHasThreads.value = false;
    mockActiveThreadId.value = "";

    const wrapper = mount(DearAgentMemoryPage);
    await flushPromises();

    expect(wrapper.text()).toContain("当前项目尚未开启 Dear Agent 会话");
    const createBtn = wrapper.findAll("button").find((b) => b.text().includes("立即创建会话并开启记忆"));
    expect(createBtn).toBeDefined();
    await createBtn!.trigger("click");

    expect(mockCreateInitialThread).toHaveBeenCalled();
  });

  it("无写权限时展示只读提示并禁用写操作按钮", async () => {
    mockCanWrite.value = false;
    (memoryService.readMemory as any).mockResolvedValueOnce({
      schema_version: 1,
      revision: 1,
      epoch: 0,
      automatic_candidates: false,
      facts: [
        {
          id: "fact-1",
          text: "测试事实",
          category: "knowledge",
          origin: "system",
          revision: 1,
          created_at: "2026-09-16T00:00:00Z",
          updated_at: "2026-09-16T00:00:00Z",
        },
      ],
      candidates: [],
    });

    const wrapper = mount(DearAgentMemoryPage);
    await flushPromises();

    expect(wrapper.text()).toContain("当前项目处于只读模式（缺少 project.runtime.write 权限）");
    const addBtn = wrapper.findAll("button").find((b) => b.text().includes("手动记录事实") || b.text().includes("新增事实"));
    expect(addBtn?.attributes("disabled")).toBeDefined();
  });
});
