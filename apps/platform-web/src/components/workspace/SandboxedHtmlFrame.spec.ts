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
});
