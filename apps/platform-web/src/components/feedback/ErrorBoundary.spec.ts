import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import ErrorBoundary from "./ErrorBoundary.vue";
import { errorRingBuffer } from "@/services/observability/error-buffer";
import * as diagnosticPacket from "@/services/observability/diagnostic-packet";

const GoodChild = defineComponent({
  name: "GoodChild",
  render() {
    return h("div", { class: "normal-child" }, "Normal Content");
  },
});

const BadChild = defineComponent({
  name: "BadChild",
  setup() {
    throw new Error("Simulated setup crash");
  },
  render() {
    return h("div", "Never rendered");
  },
});

describe("ErrorBoundary.vue", () => {
  beforeEach(() => {
    errorRingBuffer.clear();
    vi.restoreAllMocks();
  });

  it("正常子组件应当正常渲染 slot 内容", () => {
    const wrapper = mount(ErrorBoundary, {
      slots: {
        default: () => h(GoodChild),
      },
    });

    expect(wrapper.find(".normal-child").exists()).toBe(true);
    expect(wrapper.text()).toContain("Normal Content");
    expect(wrapper.find('[data-testid="error-boundary-crash"]').exists()).toBe(
      false,
    );
  });

  it("子组件崩溃时应当捕获错误并渲染崩溃卡片，阻止白屏", async () => {
    const wrapper = mount(ErrorBoundary, {
      slots: {
        default: () => h(BadChild),
      },
    });

    await nextTick();

    expect(wrapper.find('[data-testid="error-boundary-crash"]').exists()).toBe(
      true,
    );
    expect(wrapper.text()).toContain("视图遇到未处理异常");
    expect(wrapper.text()).toContain("Simulated setup crash");

    // 断言错误被推入 errorRingBuffer
    const latest = errorRingBuffer.getLatest();
    expect(latest).not.toBeNull();
    expect(latest?.type).toBe("js_runtime");
    expect(latest?.message).toBe("Simulated setup crash");
  });

  it("点击复制排障信息按钮时应当触发 copyDiagnosticPacket", async () => {
    const spy = vi
      .spyOn(diagnosticPacket, "copyDiagnosticPacket")
      .mockResolvedValue({
        success: true,
        markdown: "markdown report",
      });

    const wrapper = mount(ErrorBoundary, {
      slots: {
        default: () => h(BadChild),
      },
    });

    await nextTick();

    const copyBtn = wrapper.find('[data-testid="copy-diagnostic-btn"]');
    expect(copyBtn.exists()).toBe(true);

    await copyBtn.trigger("click");
    expect(spy).toHaveBeenCalled();
  });
});
