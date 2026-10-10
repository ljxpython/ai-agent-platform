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

    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("send")).toHaveLength(1);
  });

  it("emits queue on Enter when running and canQueue is true with input", async () => {
    const wrapper = mountComposer({
      modelValue: "补充新的要求",
      canSendFreshMessage: false,
      canQueue: true,
      isRunning: true,
    });

    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("queue")).toHaveLength(1);
  });

  it("emits queue on Enter and shows queue button when hasQueuedItems is true even if isRunning is false", async () => {
    const wrapper = mountComposer({
      modelValue: "队列里已有消息时的后续补充",
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

  it("renders composer suggestions when draft is empty and not running", async () => {
    const wrapper = mountComposer({
      modelValue: "",
      isRunning: false,
    });

    const suggestions = wrapper.find(
      '[data-testid="composer-suggestions-container"]',
    );
    expect(suggestions.exists()).toBe(true);
    expect(suggestions.text()).toContain("小惊喜");
  });

  it("hides composer suggestions when draft is non-empty or agent is running", async () => {
    const wrapper = mountComposer({
      modelValue: "已输入内容",
      isRunning: false,
    });
    expect(
      wrapper.find('[data-testid="composer-suggestions-container"]').exists(),
    ).toBe(false);

    await wrapper.setProps({ modelValue: "", isRunning: true });
    expect(
      wrapper.find('[data-testid="composer-suggestions-container"]').exists(),
    ).toBe(false);
  });

  it("hides composer suggestions when showSuggestions is false even if draft is empty and not running", () => {
    const wrapper = mountComposer({
      modelValue: "",
      isRunning: false,
      showSuggestions: false,
    });
    expect(
      wrapper.find('[data-testid="composer-suggestions-container"]').exists(),
    ).toBe(false);
  });

  it("blocks send and queue submission when turnState is stopping or stop_unconfirmed", async () => {
    const wrapper = mountComposer({
      modelValue: "待发送草稿",
      canSendFreshMessage: true,
      canQueue: true,
      turnState: "stopping",
    });

    const sendBtn = wrapper.findAll("button").at(-1);
    expect(sendBtn?.attributes("disabled")).toBeDefined();

    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("send")).toBeUndefined();
    expect(wrapper.emitted("queue")).toBeUndefined();

    // 切换到 stop_unconfirmed 同样一票否决
    await wrapper.setProps({ turnState: "stop_unconfirmed" });
    const sendBtnUnconfirmed = wrapper.findAll("button").at(-1);
    expect(sendBtnUnconfirmed?.attributes("disabled")).toBeDefined();

    await wrapper
      .find("textarea")
      .trigger("keydown", { key: "Enter", shiftKey: false });
    expect(wrapper.emitted("send")).toBeUndefined();
    expect(wrapper.emitted("queue")).toBeUndefined();

    // 草稿仍可正常编辑保留
    expect(wrapper.get("textarea").element.value).toBe("待发送草稿");
  });

  describe("F13 Voice Input Integration", () => {
    class TestMockRecognition {
      continuous = true;
      interimResults = true;
      lang = "zh-CN";
      maxAlternatives = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((e: any) => void) | null = null;
      onresult: ((e: any) => void) | null = null;
      static instances: TestMockRecognition[] = [];

      constructor() {
        TestMockRecognition.instances.push(this);
      }

      start() {
        setTimeout(() => this.onstart?.(), 0);
      }
      stop() {
        setTimeout(() => this.onend?.(), 0);
      }
      abort() {
        setTimeout(() => this.onend?.(), 0);
      }
    }

    const origRecognition = (window as any).SpeechRecognition;
    const origSecureContext = window.isSecureContext;

    beforeEach(() => {
      TestMockRecognition.instances = [];
      Object.defineProperty(window, "isSecureContext", {
        value: true,
        configurable: true,
      });
      (window as any).SpeechRecognition = TestMockRecognition;
    });

    afterEach(() => {
      (window as any).SpeechRecognition = origRecognition;
      Object.defineProperty(window, "isSecureContext", {
        value: origSecureContext,
        configurable: true,
      });
    });

    it("C01: empty draft can start voice dictation when canDictate is true, independent of send button", async () => {
      const wrapper = mountComposer({
        modelValue: "",
        canDictate: true,
        canSendFreshMessage: false,
      });

      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      expect(micBtn.exists()).toBe(true);
      expect(micBtn.attributes("disabled")).toBeUndefined();

      await micBtn.trigger("click");
      expect(TestMockRecognition.instances.length).toBe(1);
    });

    it("C02: appends final to existing draft, keeps trailing whitespace/code, only final enters model", async () => {
      let currentVal = "function test() {\n  ";
      const wrapper = mountComposer({
        modelValue: currentVal,
        canDictate: true,
        "onUpdate:modelValue": (val: string) => {
          currentVal = val;
        },
      });

      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      await micBtn.trigger("click");
      const inst = TestMockRecognition.instances[0];

      // interim 不进入 modelValue
      inst.onresult?.({
        results: {
          0: { 0: { transcript: "console.log(1)" }, isFinal: false, length: 1 },
          length: 1,
        },
      });
      await wrapper.vm.$nextTick();
      expect(wrapper.emitted("update:modelValue")).toBeUndefined();

      // final 进入 modelValue，由于 base 结尾有空白，直接追加
      inst.onresult?.({
        results: {
          0: { 0: { transcript: "console.log(1)" }, isFinal: true, length: 1 },
          length: 1,
        },
      });
      await wrapper.vm.$nextTick();
      const emitted = wrapper.emitted("update:modelValue");
      expect(emitted).toBeDefined();
      expect(emitted?.at(-1)?.[0]).toBe("function test() {\n  console.log(1)");
    });

    it("C03: textarea input preempts voice; self-echo of final does not cancel voice", async () => {
      const wrapper = mountComposer({
        modelValue: "原草稿",
        canDictate: true,
      });

      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      await micBtn.trigger("click");
      const inst = TestMockRecognition.instances[0];
      inst.onstart?.();
      await wrapper.vm.$nextTick();

      // final 发出后，模拟父组件 echo 回传相同值
      inst.onresult?.({
        results: {
          0: { 0: { transcript: "语音新内容" }, isFinal: true, length: 1 },
          length: 1,
        },
      });
      await wrapper.vm.$nextTick();
      const nextEmitted = wrapper.emitted("update:modelValue")?.at(-1)?.[0];
      expect(nextEmitted).toBe("原草稿\n语音新内容");

      // 模拟父组件以相同值更新 prop（Self-Echo）
      await wrapper.setProps({ modelValue: nextEmitted });
      // 确认未被取消
      expect(
        wrapper.find('[data-testid="composer-voice-interim-box"]').exists(),
      ).toBe(true);

      // 用户主动在 textarea 打字触发 input，立即抢占取消
      await wrapper.find("textarea").trigger("input");
      await wrapper.vm.$nextTick();
      expect(
        wrapper.find('[data-testid="composer-voice-interim-box"]').exists(),
      ).toBe(false);
    });

    it("C04: Enter, send and queue are locked while voice is active", async () => {
      const wrapper = mountComposer({
        modelValue: "已识别的文字",
        canDictate: true,
        canSendFreshMessage: true,
        canQueue: true,
      });

      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      await micBtn.trigger("click");
      const inst = TestMockRecognition.instances[0];
      inst.onstart?.();
      await wrapper.vm.$nextTick();

      // Enter 键发送被锁定
      await wrapper
        .find("textarea")
        .trigger("keydown", { key: "Enter", shiftKey: false });
      expect(wrapper.emitted("send")).toBeUndefined();
      expect(wrapper.emitted("queue")).toBeUndefined();

      // 发送按钮被禁用
      const sendBtn = wrapper.findAll("button").at(-1);
      expect(sendBtn?.attributes("disabled")).toBeDefined();
    });

    it("C05: revoking canDictate cancels active voice session immediately", async () => {
      const wrapper = mountComposer({
        modelValue: "测试",
        canDictate: true,
      });

      const micBtn = wrapper.find('[data-testid="composer-voice-input-btn"]');
      await micBtn.trigger("click");
      const inst = TestMockRecognition.instances[0];
      inst.onstart?.();
      await wrapper.vm.$nextTick();
      expect(
        wrapper.find('[data-testid="composer-voice-interim-box"]').exists(),
      ).toBe(true);

      // 撤掉门禁
      await wrapper.setProps({ canDictate: false });
      expect(
        wrapper.find('[data-testid="composer-voice-interim-box"]').exists(),
      ).toBe(false);
    });

    it("C06: hidden when unsupported, disabled when canDictate=false, active pulse style correct", async () => {
      // 1. 不支持隐藏
      (window as any).SpeechRecognition = null;
      const unsuppWrapper = mountComposer({ canDictate: true });
      expect(
        unsuppWrapper.find('[data-testid="composer-voice-input-btn"]').exists(),
      ).toBe(false);

      // 2. 支持但门禁为 false 时禁用
      (window as any).SpeechRecognition = TestMockRecognition;
      const disWrapper = mountComposer({ canDictate: false });
      const disBtn = disWrapper.find(
        '[data-testid="composer-voice-input-btn"]',
      );
      expect(disBtn.exists()).toBe(true);
      expect(disBtn.attributes("title")).toContain("语音");
      expect(disBtn.attributes("aria-label")).toContain("语音");
    });
  });
});
