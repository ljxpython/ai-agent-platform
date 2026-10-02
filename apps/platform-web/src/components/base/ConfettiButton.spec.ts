import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ConfettiButton from "./ConfettiButton.vue";
import confetti from "canvas-confetti";

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("ConfettiButton", () => {
  it("renders slot content properly", () => {
    const wrapper = mount(ConfettiButton, {
      slots: {
        default: "<span>小惊喜</span>",
      },
    });
    expect(wrapper.text()).toContain("小惊喜");
  });

  it("calls confetti and emits click event when clicked", async () => {
    const wrapper = mount(ConfettiButton, {
      slots: {
        default: "Click me",
      },
    });

    const button = wrapper.find("button");
    await button.trigger("click");

    expect(confetti).toHaveBeenCalled();
    expect(wrapper.emitted("click")).toBeTruthy();
  });

  it("does not trigger confetti or click emit when disabled", async () => {
    vi.clearAllMocks();
    const wrapper = mount(ConfettiButton, {
      props: {
        disabled: true,
      },
      slots: {
        default: "Disabled",
      },
    });

    const button = wrapper.find("button");
    await button.trigger("click");

    expect(confetti).not.toHaveBeenCalled();
    expect(wrapper.emitted("click")).toBeFalsy();
  });
});
