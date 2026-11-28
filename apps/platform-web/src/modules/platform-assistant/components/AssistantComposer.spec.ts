import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AssistantComposer from "./AssistantComposer.vue";

describe("AssistantComposer", () => {
  it("审批中禁止键盘和按钮发送，正常输入只发送一次", async () => {
    const wrapper = mount(AssistantComposer, {
      props: { disabled: true },
      global: {
        stubs: {
          BaseIcon: true,
          BaseButton: {
            props: ["disabled"],
            template: '<button :disabled="disabled"><slot /></button>',
          },
        },
      },
    });
    await wrapper.find("textarea").setValue("继续");
    await wrapper.find("textarea").trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("send")).toBeUndefined();
    expect(wrapper.find("button").attributes("disabled")).toBeDefined();
    await wrapper.setProps({ disabled: false });
    await wrapper.find("textarea").setValue("继续");
    await wrapper.find("textarea").trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("send")).toEqual([["继续"]]);
  });

  it("当提供 projectId 与 models 时正确渲染 ChatModelSelector 并转发模型切换事件", async () => {
    const mockModels = [
      {
        id: "m-1",
        model: "deepseek-v4.1-flash",
        display_name: "Chickener DeepSeek",
        provider: "chickener",
        api_style: "openai-compatible",
        base_url: "https://chickener.top/v1",
        protocol: "openai-compatible",
        credential_configured: true,
        enabled: true,
        scope_type: "platform" as const,
      },
    ];

    const wrapper = mount(AssistantComposer, {
      props: {
        projectId: "proj-123",
        models: mockModels,
        selectedModelId: "m-1",
        defaultModelId: "m-1",
        defaultModelName: "Chickener DeepSeek",
      },
      global: {
        stubs: {
          BaseIcon: true,
          BaseButton: true,
          ChatModelSelector: {
            props: ["models", "selectedModelId", "projectId"],
            template:
              "<div class=\"mock-selector\" @click=\"$emit('update:selectedModelId', 'm-2')\">{{ selectedModelId }}</div>",
          },
        },
      },
    });

    const selector = wrapper.find(".mock-selector");
    expect(selector.exists()).toBe(true);
    expect(selector.text()).toBe("m-1");

    await selector.trigger("click");
    expect(wrapper.emitted("update:selectedModelId")).toEqual([["m-2"]]);
  });

  it("当 isRunning 为 true 时输入框不被禁用且允许输入，但按 Enter 不会触发发送", async () => {
    const wrapper = mount(AssistantComposer, {
      props: {
        isRunning: true,
        disabled: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
          BaseButton: true,
        },
      },
    });

    const textarea = wrapper.find("textarea");
    expect(textarea.attributes("disabled")).toBeUndefined();

    // 用户在 agent 思考/输出期间输入草稿
    await textarea.setValue("这是提前打好的问题");
    expect((textarea.element as HTMLTextAreaElement).value).toBe(
      "这是提前打好的问题",
    );

    // 用户按 Enter，不应该触发发送
    await textarea.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("send")).toBeUndefined();
    // 草稿内容仍然完好保留
    expect((textarea.element as HTMLTextAreaElement).value).toBe(
      "这是提前打好的问题",
    );
  });
});
