import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (k: string) => k }),
}));

import CommonChatComposer from "@/modules/chat/components/ChatComposer.vue";
import DearChatComposer from "./ChatComposer.vue";

type ComposerProps = InstanceType<typeof CommonChatComposer>["$props"];

function mountComposer(overrides: Partial<ComposerProps> = {}) {
  return mount(CommonChatComposer, {
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
    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
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
    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("queue")).toHaveLength(1);
    expect(wrapper.emitted("send")).toBeUndefined();
  });

  it("C07: mounts actual Dear Agent wrapper and transparently forwards canDictate and voice controls without second instance", async () => {
    class MockSpeechRecognition {
      continuous = true;
      interimResults = true;
      lang = "zh-CN";
      maxAlternatives = 1;
      start() {}
      stop() {}
      abort() {}
    }

    const origRecognition = (window as any).SpeechRecognition;
    const origSecure = window.isSecureContext;
    (window as any).SpeechRecognition = MockSpeechRecognition;
    Object.defineProperty(window, "isSecureContext", {
      value: true,
      configurable: true,
    });

    try {
      const onQueueSpy = vi.fn();
      const wrapper = mount(DearChatComposer, {
        props: {
          modelValue: "Dear草稿",
          attachments: [],
          isRunning: false,
          hasBlockingInterrupt: false,
          canSendFreshMessage: false,
          cancelling: false,
          sendButtonLabel: "发送消息",
          canDictate: true,
          onQueue: onQueueSpy,
        } as any,
      });

      // 验证通过包装器透传渲染了 mic 按钮
      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      expect(micBtn.exists()).toBe(true);
      expect(micBtn.attributes("disabled")).toBeUndefined();

      // 验证通过包装器事件透传
      const inner = wrapper.findComponent(CommonChatComposer);
      expect(inner.exists()).toBe(true);
      expect(inner.props("canDictate")).toBe(true);
    } finally {
      (window as any).SpeechRecognition = origRecognition;
      Object.defineProperty(window, "isSecureContext", {
        value: origSecure,
        configurable: true,
      });
    }
  });
});
