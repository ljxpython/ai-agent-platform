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
});
