import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ComposerSuggestions from "./ComposerSuggestions.vue";

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("ComposerSuggestions", () => {
  it("renders surprise me button and suggestions", () => {
    const wrapper = mount(ComposerSuggestions, {
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("小惊喜");
    expect(wrapper.text()).toContain("深度写作");
    expect(wrapper.text()).toContain("敏捷调研");
  });

  it("emits select with prompt when surprise button clicked", async () => {
    const wrapper = mount(ComposerSuggestions, {
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const surpriseBtn = wrapper.findComponent({ name: "ConfettiButton" });
    expect(surpriseBtn.exists()).toBe(true);

    await surpriseBtn.trigger("click");
    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")?.[0]).toEqual(["给我一个小惊喜吧"]);
  });

  it("emits select when normal suggestion pill clicked", async () => {
    const wrapper = mount(ComposerSuggestions, {
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const buttons = wrapper.findAll("button");
    // Find the writing button
    const writeBtn = buttons.find((b) => b.text().includes("深度写作"));
    expect(writeBtn).toBeDefined();

    await writeBtn!.trigger("click");
    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")?.[0][0]).toContain("撰写一篇关于[主题]");
  });
});
