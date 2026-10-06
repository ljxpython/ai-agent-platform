import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import FollowUpSuggestions from "./FollowUpSuggestions.vue";

const globalMountOptions = {
  stubs: {
    BaseDialog: {
      props: ["show"],
      template:
        '<div v-if="show" data-testid="base-dialog"><slot /><slot name="footer" /></div>',
    },
    BaseButton: {
      template: "<button><slot /></button>",
    },
    BaseIcon: {
      template: "<i />",
    },
  },
};

describe("FollowUpSuggestions.vue", () => {
  it("loading 时展示加载骨架屏", () => {
    const wrapper = mount(FollowUpSuggestions, {
      props: {
        suggestions: ["问题 1"],
        loading: true,
      },
      global: globalMountOptions,
    });

    expect(wrapper.find("[data-testid='followup-loading']").exists()).toBe(
      true,
    );
    expect(wrapper.findAll("button").length).toBe(0);
  });

  it("渲染建议列表与关闭按钮", () => {
    const wrapper = mount(FollowUpSuggestions, {
      props: {
        suggestions: ["问题 1", "问题 2"],
        loading: false,
      },
      global: globalMountOptions,
    });

    const buttons = wrapper.findAll("button");
    // 2 个建议胶囊 + 1 个关闭按钮
    expect(buttons.length).toBe(3);
    expect(buttons[0]!.text()).toContain("问题 1");
    expect(buttons[1]!.text()).toContain("问题 2");
  });

  it("草稿为空时点击直接触发 select direct", async () => {
    const wrapper = mount(FollowUpSuggestions, {
      props: {
        suggestions: ["深度追问"],
        loading: false,
        draft: "",
      },
      global: globalMountOptions,
    });

    const chip = wrapper.findAll("button")[0]!;
    await chip.trigger("click");

    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")![0]).toEqual(["深度追问", "direct"]);
  });

  it("草稿非空时点击呼起弹窗并在确认后触发相应 mode", async () => {
    const wrapper = mount(FollowUpSuggestions, {
      props: {
        suggestions: ["深度追问"],
        loading: false,
        draft: "已有草稿内容",
      },
      global: globalMountOptions,
    });

    const chip = wrapper.findAll("button")[0]!;
    await chip.trigger("click");

    // 此时并未直接 emit select
    expect(wrapper.emitted("select")).toBeFalsy();

    // 模拟弹窗确认
    const dialog = wrapper.findComponent({ name: "FollowUpConfirmDialog" });
    expect(dialog.exists()).toBe(true);
    expect(dialog.props("show")).toBe(true);

    dialog.vm.$emit("confirm", "append");
    expect(wrapper.emitted("select")).toBeTruthy();
    expect(wrapper.emitted("select")![0]).toEqual(["深度追问", "append"]);
  });

  it("点击关闭按钮触发 dismiss", async () => {
    const wrapper = mount(FollowUpSuggestions, {
      props: {
        suggestions: ["问题 1"],
        loading: false,
      },
      global: globalMountOptions,
    });

    const dismissBtn = wrapper.find("button[title='关闭推荐问题']");
    expect(dismissBtn.exists()).toBe(true);

    await dismissBtn.trigger("click");
    expect(wrapper.emitted("dismiss")).toBeTruthy();
  });
});
