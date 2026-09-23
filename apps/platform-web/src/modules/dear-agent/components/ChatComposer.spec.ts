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

describe("DearAgent ChatComposer", () => {
  it("renders correctly in idle state", () => {
    const wrapper = mountComposer({
      modelValue: "",
      canSendFreshMessage: true,
    });
    expect(wrapper.text()).toContain("发送");
  });

  it("switches to queue mode and emits queue on Enter when running and canQueue is true", async () => {
    const wrapper = mountComposer({
      modelValue: "补充新的要求",
      canSendFreshMessage: false,
      canQueue: true,
      isRunning: true,
    });

    expect(wrapper.text()).toContain("补充要求");
    expect(wrapper.text()).toContain("排队");
    await wrapper.find("textarea").trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("queue")).toHaveLength(1);
    expect(wrapper.emitted("send")).toBeUndefined();
  });

  it("switches to queue mode and emits queue on Enter when hasQueuedItems is true even if isRunning is false", async () => {
    const wrapper = mountComposer({
      modelValue: "队列已有消息继续排队",
      canSendFreshMessage: false,
      canQueue: true,
      isRunning: false,
      hasQueuedItems: true,
    });

    expect(wrapper.text()).toContain("补充要求");
    expect(wrapper.text()).toContain("排队");
    await wrapper.find("textarea").trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("queue")).toHaveLength(1);
    expect(wrapper.emitted("send")).toBeUndefined();
  });
});
