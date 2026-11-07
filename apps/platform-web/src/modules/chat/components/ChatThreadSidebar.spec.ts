import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import ChatThreadSidebar from "./ChatThreadSidebar.vue";

describe("ChatThreadSidebar pagination", () => {
  const defaultProps = {
    showContextBar: false,
    targetText: "test-target",
    targetTypeText: "Agent",
    search: "",
    statusFilter: "all" as const,
    filters: [{ value: "all" as const, label: "全部" }],
    loading: false,
    threadCount: 100,
    filteredCount: 100,
    canStartThread: true,
    activeThreadId: "",
    deletingThreadId: "",
    groups: [],
    currentPage: 2,
    totalPages: 5,
    totalCount: 100,
    hasMore: true,
    canDelete: true,
  };

  it("renders total count and page indicators", () => {
    const wrapper = mount(ChatThreadSidebar, { props: defaultProps });
    expect(wrapper.text()).toContain("共 100 条");
    expect(wrapper.text()).toContain("/ 5");
    const input = wrapper.find('input[inputmode="numeric"]');
    expect((input.element as HTMLInputElement).value).toBe("2");
  });

  it("emits page-change on first, previous, next, last buttons", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: defaultProps });
    const buttons = wrapper.findAll("button");
    // Find buttons by title
    const firstBtn = buttons.find((b) => b.attributes("title") === "首页");
    const prevBtn = buttons.find((b) => b.attributes("title") === "上一页");
    const nextBtn = buttons.find((b) => b.attributes("title") === "下一页");
    const lastBtn = buttons.find((b) => b.attributes("title") === "末页");

    expect(firstBtn).toBeDefined();
    expect(prevBtn).toBeDefined();
    expect(nextBtn).toBeDefined();
    expect(lastBtn).toBeDefined();

    await firstBtn!.trigger("click");
    expect(wrapper.emitted("page-change")?.[0]).toEqual([1]);

    await prevBtn!.trigger("click");
    expect(wrapper.emitted("page-change")?.[1]).toEqual([1]);

    await nextBtn!.trigger("click");
    expect(wrapper.emitted("page-change")?.[2]).toEqual([3]);

    await lastBtn!.trigger("click");
    expect(wrapper.emitted("page-change")?.[3]).toEqual([5]);
  });

  it("jumps to page when input changes and enter key is pressed", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: defaultProps });
    const input = wrapper.find('input[inputmode="numeric"]');

    await input.setValue("4");
    await input.trigger("keydown.enter");
    expect(wrapper.emitted("page-change")?.[0]).toEqual([4]);
  });

  it("clamps out-of-range page numbers", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: defaultProps });
    const input = wrapper.find('input[inputmode="numeric"]');

    await input.setValue("999");
    await input.trigger("keydown.enter");
    // Clamped to totalPages = 5
    expect(wrapper.emitted("page-change")?.[0]).toEqual([5]);
  });
});

describe("ChatThreadSidebar thread items and renaming", () => {
  const itemProps = {
    showContextBar: false,
    targetText: "test-target",
    targetTypeText: "Agent",
    search: "",
    statusFilter: "all" as const,
    filters: [{ value: "all" as const, label: "全部" }],
    loading: false,
    threadCount: 1,
    filteredCount: 1,
    canStartThread: true,
    activeThreadId: "",
    deletingThreadId: "",
    groups: [
      {
        key: "today",
        label: "今天",
        items: [
          {
            id: "th-1",
            title: "架构设计讨论",
            preview: "",
            updatedAt: "2026-09-18T10:00:00Z",
            time: "10:00",
            status: "idle",
          },
        ],
      },
    ],
    canDelete: true,
  };

  it("does not render (无内容) when preview is empty", () => {
    const wrapper = mount(ChatThreadSidebar, { props: itemProps });
    expect(wrapper.text()).not.toContain("(无内容)");
  });

  it("triggers rename-thread on inline edit confirmation", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: itemProps });
    const renameBtn = wrapper.find('button[title="重命名会话"]');
    expect(renameBtn.exists()).toBe(true);

    await renameBtn.trigger("click");
    const input = wrapper.find('input[placeholder="会话标题"]');
    expect(input.exists()).toBe(true);

    await input.setValue("更新后的标题");
    await input.trigger("keydown.enter");
    expect(wrapper.emitted("rename-thread")?.[0]).toEqual([
      "th-1",
      "更新后的标题",
    ]);
  });

  it("triggers ai-summarize-title when magic wand button is clicked", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: itemProps });
    const aiBtn = wrapper.find('button[title="AI 智能生成标题"]');
    expect(aiBtn.exists()).toBe(true);

    await aiBtn.trigger("click");
    expect(wrapper.emitted("ai-summarize-title")?.[0]).toEqual(["th-1"]);
  });

  it("disables ai button and shows spinning icon when thread is summarizing", () => {
    const wrapper = mount(ChatThreadSidebar, {
      props: {
        ...itemProps,
        summarizingThreadId: "th-1",
      },
    });
    const aiBtn = wrapper.find('button[title="正在智能生成标题..."]');
    expect(aiBtn.exists()).toBe(true);
    expect(aiBtn.attributes("disabled")).toBeDefined();
  });
});

describe("ChatThreadSidebar compact search & batch mode", () => {
  const batchProps = {
    showContextBar: false,
    targetText: "test-target",
    targetTypeText: "Agent",
    search: "初始搜索",
    statusFilter: "all" as const,
    filters: [{ value: "all" as const, label: "全部" }],
    loading: false,
    threadCount: 2,
    filteredCount: 2,
    canStartThread: true,
    activeThreadId: "",
    deletingThreadId: "",
    groups: [
      {
        key: "today",
        label: "今天",
        items: [
          {
            id: "th-1",
            title: "会话 1",
            preview: "",
            updatedAt: "",
            time: "10:00",
            status: "idle",
          },
          {
            id: "th-2",
            title: "会话 2",
            preview: "",
            updatedAt: "",
            time: "11:00",
            status: "idle",
          },
        ],
      },
    ],
    canDeleteThread: (id: string) => id === "th-1", // th-1 可删，th-2 禁删
  };

  it("renders compact search input and clears search on button click", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: batchProps });
    const searchInput = wrapper.find('input[placeholder="搜索会话..."]');
    expect(searchInput.exists()).toBe(true);
    const clearBtn = wrapper.find('button[title="清空搜索"]');
    expect(clearBtn.exists()).toBe(true);

    await clearBtn.trigger("click");
    expect(wrapper.emitted("update:search")?.[0]).toEqual([""]);
  });

  it("supports toggling batch mode and batch deleting selected items", async () => {
    const wrapper = mount(ChatThreadSidebar, { props: batchProps });
    const batchToggleBtn = wrapper.find('button[title="批量管理会话"]');
    expect(batchToggleBtn.exists()).toBe(true);

    // 进入批量模式
    await batchToggleBtn.trigger("click");
    expect(wrapper.text()).toContain("已选 0 项");

    // 全选（应该只勾选有删除权限的 th-1）
    const selectAllBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "全选");
    expect(selectAllBtn).toBeDefined();
    await selectAllBtn!.trigger("click");
    expect(wrapper.text()).toContain("已选 1 项");

    // 点击删除按钮触发 batch-delete
    const deleteBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("删除 (1)"));
    expect(deleteBtn).toBeDefined();
    await deleteBtn!.trigger("click");
    expect(wrapper.emitted("batch-delete")?.[0]).toEqual([["th-1"]]);
  });
});
