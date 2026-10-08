import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import RunPreparationsSection from "./RunPreparationsSection.vue";
import type { PreparationSummaryItem } from "../../diagnostics/types";

describe("RunPreparationsSection.vue", () => {
  it("空数组时不渲染任何内容", () => {
    const wrapper = mount(RunPreparationsSection, {
      props: {
        preparations: [],
      },
    });

    expect(
      wrapper.find('[data-testid="run-preparations-section"]').exists(),
    ).toBe(false);
    expect(wrapper.html()).toBe("<!--v-if-->");
  });

  it("正常渲染准备项列表与状态徽章", () => {
    const mockItems: PreparationSummaryItem[] = [
      {
        observation_id: "prep-1",
        scope: "primary",
        namespace: ["workspace_root"],
        component: "workspace",
        outcome: "prepared",
        duration_ms: 15.5,
        error_code: null,
      },
      {
        observation_id: "prep-2",
        scope: "subagent",
        namespace: ["sub_agent_ns"],
        component: "workspace",
        outcome: "failed",
        duration_ms: 5,
        error_code: "resource_unavailable",
      },
    ];

    const wrapper = mount(RunPreparationsSection, {
      props: {
        preparations: mockItems,
      },
    });

    expect(wrapper.text()).toContain("运行准备记录");
    expect(wrapper.text()).toContain("共 2 项");
    expect(wrapper.text()).toContain("工作区");
    expect(wrapper.text()).toContain("已准备");
    expect(wrapper.text()).toContain("准备失败");
    expect(wrapper.text()).toContain("资源不可用");
    expect(wrapper.text()).toContain("子智能体");
  });
});
