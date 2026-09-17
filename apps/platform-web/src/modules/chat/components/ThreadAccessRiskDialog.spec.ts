import { mount } from "@vue/test-utils";
import { expect, it, vi } from "vitest";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import ThreadAccessRiskDialog from "./ThreadAccessRiskDialog.vue";

it("requires checkbox acknowledgment before confirming workspace_write", async () => {
  const wrapper = mount(ThreadAccessRiskDialog, {
    attachTo: document.body,
    props: { show: true },
  });

  try {
    const confirmBtn = document.querySelector<HTMLButtonElement>(
      '[data-testid="risk-confirm-button"]',
    )!;
    expect(confirmBtn).toBeTruthy();
    expect(confirmBtn.disabled).toBe(true);

    const checkbox = document.querySelector<HTMLInputElement>(
      '[data-testid="risk-acknowledge-checkbox"]',
    )!;
    expect(checkbox).toBeTruthy();

    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    await wrapper.vm.$nextTick();

    expect(confirmBtn.disabled).toBe(false);

    confirmBtn.click();
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("confirm")).toHaveLength(1);
  } finally {
    wrapper.unmount();
  }
});

it("emits close and resets checkbox on cancel", async () => {
  const wrapper = mount(ThreadAccessRiskDialog, {
    attachTo: document.body,
    props: { show: true },
  });

  try {
    const checkbox = document.querySelector<HTMLInputElement>(
      '[data-testid="risk-acknowledge-checkbox"]',
    )!;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    await wrapper.vm.$nextTick();

    const cancelBtn = [...document.querySelectorAll("button")].find(
      (b) => b.textContent?.includes("取消"),
    );
    expect(cancelBtn).toBeTruthy();
    cancelBtn!.click();
    await wrapper.vm.$nextTick();

    expect(wrapper.emitted("close")).toHaveLength(1);
  } finally {
    wrapper.unmount();
  }
});

it("renders full_access title and button label when targetPolicy is full_access", () => {
  const wrapper = mount(ThreadAccessRiskDialog, {
    attachTo: document.body,
    props: { show: true, targetPolicy: "full_access" },
  });

  try {
    const dialog = document.body.textContent;
    expect(dialog).toContain("确认启用 Full access？");
    expect(dialog).toContain("全权负责模式（Full access）");
    const confirmBtn = document.querySelector<HTMLButtonElement>(
      '[data-testid="risk-confirm-button"]',
    );
    expect(confirmBtn?.textContent).toContain("启用 Full access");
  } finally {
    wrapper.unmount();
  }
});
