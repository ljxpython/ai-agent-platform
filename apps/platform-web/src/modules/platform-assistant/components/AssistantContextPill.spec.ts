import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { copyText } from "@/utils/clipboard";
import AssistantContextPill from "./AssistantContextPill.vue";
vi.mock("@/utils/clipboard", () => ({ copyText: vi.fn() }));

describe("AssistantContextPill", () => {
  const mockContext = {
    title: "SQL 执行超时 504",
    summary: "执行统计查询时网关超时",
    diagnosticMarkdown: "```sql\nSELECT * FROM runs;\n```",
    traceId: "tr-test-55556666",
  };

  it("正常渲染错误上下文胶囊内容与 Trace 缩略", () => {
    const wrapper = mount(AssistantContextPill, {
      props: {
        context: mockContext,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("错误现场");
    expect(wrapper.text()).toContain("SQL 执行超时 504");
    expect(wrapper.text()).toContain("tr-test-");

    // 默认详情折叠
    expect(wrapper.text()).toContain("预览详情");
    expect(wrapper.text()).not.toContain("SELECT * FROM runs;");
  });

  it("点击预览详情展开与收起", async () => {
    const wrapper = mount(AssistantContextPill, {
      props: {
        context: mockContext,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const previewBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("预览详情"));
    expect(previewBtn?.exists()).toBe(true);

    await previewBtn?.trigger("click");
    expect(wrapper.text()).toContain("收起详情");
    expect(wrapper.text()).toContain("SELECT * FROM runs;");

    await previewBtn?.trigger("click");
    expect(wrapper.text()).toContain("预览详情");
  });

  it("点击移除按钮触发 remove 事件", async () => {
    const wrapper = mount(AssistantContextPill, {
      props: {
        context: mockContext,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const removeBtn = wrapper.find('button[title="移除此上下文"]');
    expect(removeBtn.exists()).toBe(true);

    await removeBtn.trigger("click");
    expect(wrapper.emitted("remove")).toHaveLength(1);
  });

  it("不依赖助手服务复制已有诊断，复制失败时可展开手动复制", async () => {
    vi.mocked(copyText)
      .mockResolvedValueOnce(true)
      .mockResolvedValueOnce(false);
    const wrapper = mount(AssistantContextPill, {
      props: { context: mockContext },
      global: { stubs: { BaseIcon: true } },
    });
    const button = wrapper
      .findAll("button")
      .find((b) => b.text() === "复制诊断")!;
    await button.trigger("click");
    expect(copyText).toHaveBeenCalledWith(mockContext.diagnosticMarkdown);
    expect(wrapper.text()).toContain("诊断已复制");
    await button.trigger("click");
    expect(wrapper.text()).toContain("复制失败，请展开详情手动复制");
  });
});
