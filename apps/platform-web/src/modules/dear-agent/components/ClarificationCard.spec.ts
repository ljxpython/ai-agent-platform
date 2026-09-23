import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import ClarificationCard from "@/modules/chat/components/ClarificationCard.vue";
import type { PendingClarification } from "../human-input";

describe("ClarificationCard.vue", () => {
  const sampleClarification: PendingClarification = {
    id: "intr-1",
    namespace: [],
    supported: true,
    raw: {},
    request: {
      question: "请选择周期并输入备注",
      context: "这是背景说明",
      schema_version: 1,
      fields: [
        {
          name: "period",
          type: "select",
          label: "统计周期",
          required: true,
          options: [
            { label: "按日", value: "daily" },
            { label: "按周", value: "weekly" },
          ],
        },
        {
          name: "memo",
          type: "text",
          label: "额外说明",
          required: true,
          placeholder: "请输入说明",
        },
      ],
    },
  };

  it("renders question, context and form fields", () => {
    const wrapper = mount(ClarificationCard, {
      props: {
        clarification: sampleClarification,
      },
    });

    expect(wrapper.find('[data-testid="clarification-question"]').text()).toBe(
      "请选择周期并输入备注",
    );
    expect(wrapper.text()).toContain("这是背景说明");
    expect(wrapper.find("select#field-period").exists()).toBe(true);
    expect(wrapper.find("input#field-memo").exists()).toBe(true);
  });

  it("validates required fields and stops submission on empty required text", async () => {
    const wrapper = mount(ClarificationCard, {
      props: {
        clarification: sampleClarification,
      },
    });

    // select defaults to first option, but memo is empty
    await wrapper.find("form").trigger("submit");

    expect(wrapper.emitted("submit")).toBeUndefined();
    expect(wrapper.find('[data-testid="field-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="field-error"]').text()).toContain("请填写额外说明");
  });

  it("emits submit with entered values when valid", async () => {
    const wrapper = mount(ClarificationCard, {
      props: {
        clarification: sampleClarification,
      },
    });

    await wrapper.find("input#field-memo").setValue("这是我的测试说明");
    await wrapper.find("form").trigger("submit");

    expect(wrapper.emitted("submit")).toHaveLength(1);
    const submitted = wrapper.emitted("submit")![0][0] as Record<string, unknown>;
    expect(submitted.period).toBe("daily");
    expect(submitted.memo).toBe("这是我的测试说明");
  });
});
