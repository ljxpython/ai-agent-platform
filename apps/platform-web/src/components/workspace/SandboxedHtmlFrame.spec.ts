import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import SandboxedHtmlFrame from "./SandboxedHtmlFrame.vue";

describe("SandboxedHtmlFrame", () => {
  it("renders sandboxed iframe with allow-scripts permission and badge", () => {
    const wrapper = mount(SandboxedHtmlFrame, {
      props: {
        html: "<h1>Hello Safe HTML</h1>",
        title: "test.html",
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const iframe = wrapper.find("iframe");
    expect(iframe.exists()).toBe(true);
    expect(iframe.attributes("sandbox")).toBe("allow-scripts");
    expect(iframe.attributes("referrerpolicy")).toBe("no-referrer");
    expect(iframe.attributes("srcdoc")).toBe("<h1>Hello Safe HTML</h1>");

    const badge = wrapper.text();
    expect(badge).toContain("独立脚本沙箱 (零同源凭据)");
    expect(badge).toContain("test.html");
  });

  it("toggles fullscreen mode and exits on Escape key", async () => {
    const wrapper = mount(SandboxedHtmlFrame, {
      props: {
        html: "<h1>Fullscreen Test</h1>",
        title: "fullscreen.html",
      },
      global: {
        stubs: {
          BaseIcon: true,
          Teleport: true,
        },
      },
    });

    const toggleBtn = wrapper.find("button[title*='全屏']");
    expect(toggleBtn.exists()).toBe(true);

    // 默认非全屏
    const container = wrapper.find(".h-full.w-full");
    expect(container.exists()).toBe(true);

    // 点击切换为全屏
    await toggleBtn.trigger("click");
    expect(wrapper.find(".fixed.inset-0.z-\\[120\\]").exists()).toBe(true);

    // 按 Escape 键退出全屏
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".h-full.w-full").exists()).toBe(true);
  });
});
