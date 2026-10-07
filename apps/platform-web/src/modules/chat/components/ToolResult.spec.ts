import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ToolResult from "./ToolResult.vue";
import type { ToolItem } from "../transcript";

describe("ToolResult.vue", () => {
  it("renders write_todos with humanized title and subtitle", () => {
    const tool: ToolItem = {
      key: "todo-tool-1",
      id: "call-todo-1",
      name: "write_todos",
      input: {
        todos: [
          { content: "读取 report.py 分析缺陷", status: "in_progress" },
          { content: "修复计算逻辑", status: "pending" },
          { content: "执行测试验证", status: "completed" },
        ],
      },
      output: undefined,
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
        },
      },
    });

    expect(wrapper.text()).toContain("更新任务清单");
    expect(wrapper.text()).toContain("· 共 3 项");
    expect(wrapper.text()).toContain("已返回");
  });

  it("expands to render structured todo list and emits inspect for task board", async () => {
    const tool: ToolItem = {
      key: "todo-tool-2",
      id: "call-todo-2",
      name: "write_todos",
      input: [
        { content: "定位缺陷", status: "in_progress" },
        { content: "提交修复", status: "pending" },
      ],
      output: undefined,
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
        },
      },
    });

    // 初始折叠
    expect(wrapper.text()).not.toContain("待办计划 · 共 2 项");

    // 点击展开
    const toggleButton = wrapper.find("button");
    await toggleButton.trigger("click");

    expect(wrapper.text()).toContain("待办计划 · 共 2 项");
    expect(wrapper.text()).toContain("定位缺陷");
    expect(wrapper.text()).toContain("进行中");
    expect(wrapper.text()).toContain("提交修复");
    expect(wrapper.text()).toContain("待处理");

    // 检查在详情面板查看任务看板按钮
    const inspectBtn = wrapper.find(".pw-table-tool-button");
    expect(inspectBtn.exists()).toBe(true);
    expect(inspectBtn.text()).toContain("在详情面板查看任务看板 →");

    await inspectBtn.trigger("click");
    expect(wrapper.emitted("inspect")).toBeTruthy();
    expect(wrapper.emitted("inspect")![0]).toEqual([tool]);
  });

  it("renders parse_document warnings with humanized localized messages", async () => {
    const tool: ToolItem = {
      key: "doc-tool-1",
      id: "call-doc-1",
      name: "parse_document",
      input: {
        file_path: "/workspace/uploads/contract.pdf",
        query: "付款条件",
      },
      output: JSON.stringify({
        version: 1,
        pages: 2,
        format: "pdf",
        matched_pages: [],
        chunks: [],
        text: "",
        truncated: false,
        warnings: ["no_query_match_in_selected_range"],
      }),
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("解析文档");
    expect(wrapper.text()).toContain("contract.pdf");

    // 点击展开
    const toggleButton = wrapper.find("button");
    await toggleButton.trigger("click");

    expect(wrapper.text()).toContain(
      '在指定页码范围内未匹配到关键词 "付款条件"',
    );
  });

  it("renders generated image only once when both output text and artifact contain the same image path", async () => {
    const imagePath =
      "/workspace/generated/29e6f9b9523246afba17dcc8b17f2747.png";
    const tool: ToolItem = {
      key: "img-tool-1",
      id: "call-img-1",
      name: "edit_image",
      input: {
        image_path: "/workspace/uploads/original.png",
        prompt: "添加迪迦奥特曼",
      },
      output: imagePath,
      artifact: {
        runtime_images: [
          {
            version: 1,
            path: imagePath,
            mime_type: "image/png",
            size_bytes: 1024,
            sha256: "0".repeat(64),
          },
        ],
      },
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          BaseIcon: true,
          ThreadImage: {
            template:
              '<div class="stub-thread-image" :data-path="imageRef?.path">image</div>',
            props: ["imageRef"],
          },
        },
      },
    });

    expect(wrapper.text()).toContain("图像编辑/图生图");
    expect(wrapper.text()).toContain(`· 产物: ${imagePath}`);

    // 点击展开
    const toggleButton = wrapper.find("button");
    await toggleButton.trigger("click");

    // 关键断言：卡片展开后，ThreadImage 只被渲染恰好 1 次，坚决杜绝双重渲染
    const renderedImages = wrapper.findAll(".stub-thread-image");
    expect(renderedImages.length).toBe(1);
    expect(renderedImages[0].attributes("data-path")).toBe(imagePath);
  });

  it("renders image via fallback runtimeImages section when output is plain text without image path", async () => {
    const imagePath = "/workspace/generated/fallback.png";
    const tool: ToolItem = {
      key: "img-tool-2",
      id: "call-img-2",
      name: "generate_image",
      input: { prompt: "画一只可爱的猫" },
      output: "已成功执行生图操作",
      artifact: {
        runtime_images: [
          {
            version: 1,
            path: imagePath,
            mime_type: "image/png",
            size_bytes: 1024,
            sha256: "0".repeat(64),
          },
        ],
      },
      status: "finished",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          BaseIcon: true,
          ThreadImage: {
            template:
              '<div class="stub-thread-image" :data-path="imageRef?.path">image</div>',
            props: ["imageRef"],
          },
        },
      },
    });

    // 点击展开
    const toggleButton = wrapper.find("button");
    await toggleButton.trigger("click");

    const renderedImages = wrapper.findAll(".stub-thread-image");
    expect(renderedImages.length).toBe(1);
    expect(renderedImages[0].attributes("data-path")).toBe(imagePath);
  });

  it("renders '正在生成参数 · 已生成 1.5k 字符' during streamingInput and switches to '执行中' when executing", async () => {
    const streamingTool: ToolItem = {
      key: "write-tool-1",
      id: "call-write-1",
      name: "write_file",
      input: {
        path: "/workspace/outputs/report.md",
        content: "# 综合报告\n" + "内容段落".repeat(380),
      },
      status: "running",
      streamingInput: true,
      streamingChars: 1526,
    };

    const wrapper = mount(ToolResult, {
      props: { tool: streamingTool },
      global: {
        stubs: {
          SubagentCard: true,
          BaseIcon: true,
          MessageContent: true,
        },
      },
    });

    expect(wrapper.text()).toContain("write_file");
    expect(wrapper.text()).toContain("report.md");
    expect(wrapper.text()).toContain("正在生成参数 · 已生成 1.5k 字符");

    // 展开后应显示正在流式生成写入内容预览
    await wrapper.find("button").trigger("click");
    expect(wrapper.text()).toContain("正在流式生成写入内容");

    // 切换为工具执行阶段（streamingInput: false）
    await wrapper.setProps({
      tool: {
        ...streamingTool,
        streamingInput: false,
        streamingChars: undefined,
      },
    });
    expect(wrapper.text()).toContain("执行中");
    expect(wrapper.text()).not.toContain("正在生成参数");
  });

  it("renders structured tool error with summary and recovery tag badge in collapsed bar and formatted json on expand", async () => {
    const rawJson = JSON.stringify({
      status: "error",
      code: "tool.invalid_input",
      error: "工具输入不符合要求，请修正参数后继续。",
      recovery: "correct_input",
    });

    const tool: ToolItem = {
      key: "error-tool-1",
      id: "call-err-1",
      name: "search_web",
      input: { query: "" },
      output: rawJson,
      status: "error",
      error: undefined, // 模拟真实 SDK 中 call.error 为 undefined 的场景
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
          BaseIcon: true,
        },
      },
    });

    // 折叠态：应显示失败状态、中文错误摘要和 Tag 徽章
    expect(wrapper.text()).toContain("失败");
    expect(wrapper.text()).toContain("工具输入不符合要求，请修正参数后继续。");
    expect(wrapper.text()).toContain("可修正参数");

    // 点击展开
    await wrapper.find("button").trigger("click");
    expect(wrapper.text()).toContain("结果");
    // 展开后应包含只读格式化 JSON 代码块
    const pre = wrapper.find(".pw-tool-error-output");
    expect(pre.exists()).toBe(true);
    expect(pre.text()).toContain('"code": "tool.invalid_input"');
    expect(pre.text()).toContain('"recovery": "correct_input"');
  });

  it("unpacks MCP content blocks array error and renders choose_alternative tag badge", async () => {
    const tool: ToolItem = {
      key: "mcp-err-1",
      id: "call-mcp-1",
      name: "generate_bar_chart",
      input: { data: [] },
      output: [
        {
          type: "text",
          text: JSON.stringify({
            status: "error",
            code: "tool.upstream_unavailable",
            error: "图表渲染服务不可用，请换用折线图",
            recovery: "choose_alternative",
          }),
        },
      ],
      status: "error",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("失败");
    expect(wrapper.text()).toContain("图表渲染服务不可用，请换用折线图");
    expect(wrapper.text()).toContain("可选择其他方式");
  });

  it("renders non-JSON plain text error and shows pre block on expand", async () => {
    const plainError = "Error: file not found: /workspace/main.py";
    const tool: ToolItem = {
      key: "plain-err-1",
      id: "call-plain-1",
      name: "read_file",
      input: { path: "/workspace/main.py" },
      output: plainError,
      status: "error",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("失败");
    expect(wrapper.text()).toContain(plainError);

    // 展开后验证
    await wrapper.find("button").trigger("click");
    expect(wrapper.find(".pw-tool-error-output").text()).toContain(plainError);
  });

  it("handles unknown outcome error without duplicate conflicting warning banners", async () => {
    const tool: ToolItem = {
      key: "unknown-err-1",
      id: "call-unknown-1",
      name: "generate_image",
      input: { prompt: "山水画" },
      output: JSON.stringify({
        status: "unknown",
        task_id: "task-img-999",
        error: "生成任务终态未知，远程超时",
        recovery: "do_not_repeat",
      }),
      status: "error",
    };

    const wrapper = mount(ToolResult, {
      props: { tool },
      global: {
        stubs: {
          SubagentCard: true,
          MessageContent: true,
          BaseIcon: true,
        },
      },
    });

    // 折叠态：摘要与 Tag 徽章
    expect(wrapper.text()).toContain("生成任务终态未知，远程超时");
    expect(wrapper.text()).toContain("先核对结果");

    // 点击展开：包含专用黄色告警框与 task_id
    await wrapper.find("button").trigger("click");
    expect(wrapper.text()).toContain("生成任务终态未知 (unknown)");
    expect(wrapper.text()).toContain("task-img-999");
    expect(wrapper.text()).toContain("切勿盲目重复点击生成");
  });
});
