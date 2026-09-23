import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import ChatModelSelector from "./ChatModelSelector.vue";

it("selects model UUIDs and restores focus after keyboard selection", async () => {
  const wrapper = mount(ChatModelSelector, {
    attachTo: document.body,
    props: { projectId: "project-a", models: [{ id: "model-uuid", model: "qwen-plus", display_name: "Qwen", provider: "qwen", protocol: "openai-compatible", base_url: "https://example.com/v1", enabled: true, credential_configured: true }] },
    global: { stubs: { RouterLink: true } },
  });
  try {
    await wrapper.get("button").trigger("click");
    const search = document.querySelector<HTMLInputElement>('[aria-label="搜索模型"]')!;
    search.value = "qwen-plus";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    await wrapper.vm.$nextTick();
    const option = document.querySelector<HTMLElement>('[role="dialog"] [role="button"]')!;
    option.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await wrapper.vm.$nextTick();
    expect(wrapper.emitted("update:selectedModelId")).toEqual([["model-uuid"]]);
    expect(document.activeElement).toBe(wrapper.get("button").element);
  } finally { wrapper.unmount(); }
});

it("does not steal focus from external inputs when clicked outside", async () => {
  const externalInput = document.createElement("textarea");
  document.body.appendChild(externalInput);
  externalInput.focus();

  const wrapper = mount(ChatModelSelector, {
    attachTo: document.body,
    props: {
      projectId: "project-a",
      models: [{ id: "model-uuid", model: "qwen-plus", display_name: "Qwen", provider: "qwen", protocol: "openai-compatible", base_url: "https://example.com/v1", enabled: true, credential_configured: true }],
    },
    global: { stubs: { RouterLink: true } },
  });

  try {
    // 1. When closed: clicking externalInput triggers document click but must NOT steal focus
    externalInput.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(document.activeElement).toBe(externalInput);

    // 2. Open selector, then click externalInput to dismiss: must NOT steal focus back to trigger button
    await wrapper.get("button").trigger("click");
    expect(document.querySelector('[role="dialog"]')).toBeTruthy();

    externalInput.focus();
    externalInput.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(document.activeElement).toBe(externalInput);
  } finally {
    wrapper.unmount();
    externalInput.remove();
  }
});

it("deduplicates same-provider models preferring project scope and matches defaultModelId", async () => {
  const wrapper = mount(ChatModelSelector, {
    attachTo: document.body,
    props: {
      projectId: "project-a",
      defaultModelId: "proj-id-1",
      defaultModelName: "deepseek-v4.1-flash",
      models: [
        {
          id: "plat-id-1",
          model: "deepseek-v4.1-flash",
          display_name: "deepseek-v4.1-flash",
          provider: "maomaoai",
          protocol: "openai-compatible",
          base_url: "",
          enabled: true,
          credential_configured: true,
          scope_type: "platform",
        },
        {
          id: "proj-id-1",
          model: "deepseek-v4.1-flash",
          display_name: "deepseek-v4.1-flash",
          provider: "maomaoai",
          protocol: "openai-compatible",
          base_url: "https://api.maomaoai.test/v1",
          enabled: true,
          credential_configured: true,
          scope_type: "project",
        },
      ],
    },
    global: { stubs: { RouterLink: true } },
  });
  try {
    await wrapper.get("button").trigger("click");
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.textContent).toContain("共 1 款模型");
    expect(dialog.textContent).toContain("项目私有");
    expect(dialog.textContent).toContain("默认");
  } finally {
    wrapper.unmount();
  }
});

