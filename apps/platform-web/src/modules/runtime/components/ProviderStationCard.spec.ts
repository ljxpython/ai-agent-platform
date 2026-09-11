import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import ProviderStationCard, {
  type ProviderStation,
} from "./ProviderStationCard.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import ActionMenu from "@/components/platform/ActionMenu.vue";
import StatusPill from "@/components/platform/StatusPill.vue";

describe("ProviderStationCard", () => {
  const mockStation: ProviderStation = {
    id: "deepseek-proxy",
    name: "DeepSeek 中转站 (deepseek-proxy)",
    provider: "deepseek-proxy",
    baseUrl: "http://120.48.180.39:20002/v1",
    protocol: "openai-compatible",
    credentialConfigured: true,
    modelCount: 2,
    enabledCount: 2,
    isDefaultStation: true,
    models: [
      {
        id: "m-1",
        model: "DeepSeek-V4-Flash",
        display_name: "DeepSeek V4 Flash (中转)",
        provider: "deepseek-proxy",
        base_url: "http://120.48.180.39:20002/v1",
        protocol: "openai-compatible",
        enabled: true,
        credential_configured: true,
      },
      {
        id: "m-2",
        model: "qwen3.6-27b",
        display_name: "Qwen 3.6 27B (中转)",
        provider: "deepseek-proxy",
        base_url: "http://120.48.180.39:20002/v1",
        protocol: "openai-compatible",
        enabled: true,
        credential_configured: true,
      },
    ],
  };

  function createWrapper(props: Record<string, unknown> = {}) {
    const pinia = createPinia();
    setActivePinia(pinia);

    return mount(ProviderStationCard, {
      props: {
        station: mockStation,
        canManage: true,
        defaultModelIds: ["m-1"],
        getModelActions: () => [],
        ...props,
      },
      global: {
        plugins: [pinia],
        components: {
          BaseButton,
          BaseIcon,
          ActionMenu,
          StatusPill,
        },
      },
    });
  }

  it("renders station header and its contained models", () => {
    const wrapper = createWrapper();
    expect(wrapper.text()).toContain("DeepSeek 中转站 (deepseek-proxy)");
    expect(wrapper.text()).toContain("http://120.48.180.39:20002/v1");
    expect(wrapper.text()).toContain("共 2 个模型");
    expect(wrapper.text()).toContain("DeepSeek-V4-Flash");
    expect(wrapper.text()).toContain("qwen3.6-27b");
  });

  it("emits add-model event when clicking add model button", async () => {
    const wrapper = createWrapper();
    const addBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("添加模型"));
    expect(addBtn).toBeDefined();

    await addBtn?.trigger("click");
    expect(wrapper.emitted("add-model")).toBeDefined();
    expect(wrapper.emitted("add-model")?.[0][0]).toEqual(mockStation);
  });
});
