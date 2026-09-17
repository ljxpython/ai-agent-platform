import { mount } from "@vue/test-utils";
import { expect, it, vi } from "vitest";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import ThreadAccessPolicySelect from "./ThreadAccessPolicySelect.vue";

it("renders review label and switches to review directly", async () => {
  const wrapper = mount(ThreadAccessPolicySelect, {
    attachTo: document.body,
    props: { modelValue: "workspace_write" },
  });

  try {
    const trigger = wrapper.get('[data-testid="access-policy-trigger"]');
    expect(trigger.text()).toContain("允许工作区操作");

    await trigger.trigger("click");
    const reviewOption = document.querySelector<HTMLButtonElement>(
      '[data-testid="policy-option-review"]',
    )!;
    expect(reviewOption).toBeTruthy();

    reviewOption.click();
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("update:modelValue")).toEqual([["review"]]);
    expect(wrapper.emitted("change")).toEqual([["review"]]);
  } finally {
    wrapper.unmount();
  }
});

it("opens risk dialog when selecting workspace_write from review", async () => {
  const wrapper = mount(ThreadAccessPolicySelect, {
    attachTo: document.body,
    props: { modelValue: "review" },
  });

  try {
    const trigger = wrapper.get('[data-testid="access-policy-trigger"]');
    expect(trigger.text()).toContain("审阅每项操作");

    await trigger.trigger("click");
    const writeOption = document.querySelector<HTMLButtonElement>(
      '[data-testid="policy-option-workspace-write"]',
    )!;
    expect(writeOption).toBeTruthy();

    writeOption.click();
    await wrapper.vm.$nextTick();

    // 应该弹出 RiskDialog，而不是直接 emit
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();

    const checkbox = document.querySelector<HTMLInputElement>(
      '[data-testid="risk-acknowledge-checkbox"]',
    )!;
    expect(checkbox).toBeTruthy();
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    await wrapper.vm.$nextTick();

    const confirmBtn = document.querySelector<HTMLButtonElement>(
      '[data-testid="risk-confirm-button"]',
    )!;
    confirmBtn.click();
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("update:modelValue")).toEqual([["workspace_write"]]);
    expect(wrapper.emitted("change")).toEqual([["workspace_write"]]);
  } finally {
    wrapper.unmount();
  }
});

it("disables trigger button when disabled prop is set", async () => {
  const wrapper = mount(ThreadAccessPolicySelect, {
    props: { modelValue: "review", disabled: true },
  });

  const trigger = wrapper.get<HTMLButtonElement>(
    '[data-testid="access-policy-trigger"]',
  );
  expect(trigger.element.disabled).toBe(true);
});
