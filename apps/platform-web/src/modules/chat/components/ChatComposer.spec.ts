import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (k: string) => k }),
}));

import ChatComposer from "./ChatComposer.vue";

type ComposerProps = InstanceType<typeof ChatComposer>["$props"];

function mountComposer(overrides: Partial<ComposerProps> = {}) {
  return mount(ChatComposer, {
    props: {
      modelValue: "",
      attachments: [],
      isRunning: false,
      hasBlockingInterrupt: false,
      canSendFreshMessage: false,
      cancelling: false,
      sendButtonLabel: "发送消息",
      compact: true,
      "onUpdate:modelValue": () => undefined,
      ...overrides,
    } as ComposerProps,
    global: {
      stubs: {
        ChatInterruptPanel: true,
        ChatAttachmentPreview: true,
      },
    },
  });
}

describe("ChatComposer", () => {
  it("does not render legacy resize or expand controls in compact mode", () => {
    const wrapper = mountComposer();

    expect(
      wrapper.find('button[aria-label="拖拽调整输入框高度"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain("展开输入框");
    expect(wrapper.text()).not.toContain("支持 JPEG");
  });

  it("preserves the draft while the primary action switches from send to cancel", async () => {
    const wrapper = mountComposer({
      modelValue: "尚未发送的草稿",
      canSendFreshMessage: true,
    });

    expect(wrapper.get("textarea").element.value).toBe("尚未发送的草稿");
    expect(wrapper.text()).toContain("发送消息");

    await wrapper.setProps({ isRunning: true });
    expect(wrapper.get("textarea").element.value).toBe("尚未发送的草稿");
    expect(wrapper.text()).toContain("停止生成");

    await wrapper.findAll("button").at(-1)?.trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("renders ThreadAccessPolicySelect when projectId is provided and bubbles change events", async () => {
    const wrapper = mountComposer({
      projectId: "proj-abc",
      accessPolicy: "workspace_write",
    });

    const trigger = wrapper.find('[data-testid="access-policy-trigger"]');
    expect(trigger.exists()).toBe(true);
    expect(trigger.text()).toContain("允许工作区操作");
  });

  it("enables send button and triggers send on Enter when canQueue is true even if canSendFreshMessage is false", async () => {
    const wrapper = mountComposer({
      modelValue: "连续提问不卡顿",
      canSendFreshMessage: false,
      canQueue: true,
      isRunning: false,
    });

    const sendBtn = wrapper.findAll("button").at(-1);
    expect(sendBtn?.attributes("disabled")).toBeUndefined();

    await wrapper.find("textarea").trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("send")).toHaveLength(1);
  });

  it("emits queue on Enter when running and canQueue is true with input", async () => {
    const wrapper = mountComposer({
      modelValue: "补充新的要求",
      canSendFreshMessage: false,
      canQueue: true,
      isRunning: true,
    });

    await wrapper.find("textarea").trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("queue")).toHaveLength(1);
  });
});
