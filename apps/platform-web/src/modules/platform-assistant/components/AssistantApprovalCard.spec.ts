import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AssistantApprovalCard from "./AssistantApprovalCard.vue";

describe("AssistantApprovalCard", () => {
  const mockReview = {
    interrupt_id: "int-test-1",
    actions: [
      {
        name: "test_write",
        args: { key: "status", value: "active" },
        description: "更新系统状态。",
        allowed_decisions: ["approve", "reject"] as ("approve" | "reject")[],
      },
    ],
  };

  it("正确渲染待确认操作与参数，并仅展示执行与不执行按钮", () => {
    const wrapper = mount(AssistantApprovalCard, {
      props: {
        review: mockReview,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("需要用户人工确认执行");
    expect(wrapper.text()).toContain("test_write");
    expect(wrapper.text()).toContain("更新系统状态。");
    expect(wrapper.text()).toContain("status");
    expect(wrapper.text()).toContain("不执行 (拒绝)");
    expect(wrapper.text()).toContain("执行 (确认)");

    // 绝对不存在 edit 参数修改输入框
    expect(wrapper.find("input").exists()).toBe(false);
    expect(wrapper.find("textarea").exists()).toBe(false);
  });

  it("点击按钮触发对应的 decision 事件", async () => {
    const wrapper = mount(AssistantApprovalCard, {
      props: {
        review: mockReview,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    const rejectBtn = wrapper.find('[data-testid="assistant-reject-btn"]');
    const approveBtn = wrapper.find('[data-testid="assistant-approve-btn"]');

    expect(rejectBtn.exists()).toBe(true);
    expect(approveBtn.exists()).toBe(true);

    await rejectBtn.trigger("click");
    expect(wrapper.emitted("decision")?.[0]).toEqual(["reject"]);

    await approveBtn.trigger("click");
    expect(wrapper.emitted("decision")?.[1]).toEqual(["approve"]);
  });
});
