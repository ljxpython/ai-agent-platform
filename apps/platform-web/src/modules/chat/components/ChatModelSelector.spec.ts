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
