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

  it("displays policy columns and tags when showPolicy is true", () => {
    const wrapper = createWrapper({
      showPolicy: true,
      defaultModelIds: ["m-1"],
      authorizedModelIds: ["m-1"],
    });
    expect(wrapper.text()).toContain("默认项");
    expect(wrapper.text()).toContain("项目授权");
    expect(wrapper.text()).toContain("已授权");
    expect(wrapper.text()).toContain("未授权");
    expect(wrapper.text()).toContain("包含默认模型");
  });

  it("hides policy columns and tags when showPolicy is false", () => {
    const wrapper = createWrapper({
      showPolicy: false,
      defaultModelIds: ["m-1"],
      authorizedModelIds: ["m-1"],
    });
    expect(wrapper.text()).not.toContain("默认项");
    expect(wrapper.text()).not.toContain("项目授权");
    expect(wrapper.text()).not.toContain("包含默认模型");
  });

  it("displays credentials indicator and column when showCredentials is true", () => {
    const wrapper = createWrapper({
      showCredentials: true,
    });
    expect(wrapper.text()).toContain("平台托管就绪");
    expect(wrapper.text()).toContain("凭据");
    expect(wrapper.text()).toContain("托管就绪");
  });

  it("displays BYOK badge and private credential labels for project private stations", () => {
    const wrapper = createWrapper({
      showCredentials: true,
      showPolicy: true,
      station: {
        ...mockStation,
        scopeType: "project",
        models: mockStation.models.map((m) => ({
          ...m,
          scope_type: "project" as const,
        })),
      },
    });
    expect(wrapper.text()).toContain("私有 BYOK");
    expect(wrapper.text()).toContain("私有凭据已配置");
    expect(wrapper.text()).toContain("私有已配置");
  });

  it("displays platform托管 badge and platform托管就绪 for platform stations in project view", () => {
    const wrapper = createWrapper({
      showCredentials: true,
      showPolicy: true,
      station: {
        ...mockStation,
        scopeType: "platform",
        models: mockStation.models.map((m) => ({
          ...m,
          scope_type: "platform" as const,
        })),
      },
    });
    expect(wrapper.text()).toContain("平台托管");
    expect(wrapper.text()).toContain("平台托管就绪");
    expect(wrapper.text()).toContain("托管就绪");
  });

  it("hides credentials indicator and column when showCredentials is false", () => {
    const wrapper = createWrapper({
      showCredentials: false,
    });
    expect(wrapper.text()).not.toContain("凭据均已配置");
    expect(wrapper.text()).not.toContain("部分凭据未配置");
    expect(wrapper.text()).not.toContain("configured");
  });

  it("renders delete station button and emits delete-station when canManage is true", async () => {
    const wrapper = createWrapper({
      canManage: true,
    });
    const deleteBtn = wrapper
      .findAll("button")
      .find((b) => b.attributes("title") === "删除提供商" || b.attributes("aria-label") === "删除提供商");
    expect(deleteBtn).toBeDefined();
    await deleteBtn?.trigger("click");
    expect(wrapper.emitted("delete-station")).toBeDefined();
    expect(wrapper.emitted("delete-station")?.[0][0]).toEqual(mockStation);
  });

  it("hides delete station button when canManage is false", () => {
    const wrapper = createWrapper({
      canManage: false,
    });
    const deleteBtn = wrapper
      .findAll("button")
      .find((b) => b.attributes("title") === "删除提供商");
    expect(deleteBtn).toBeUndefined();
  });
});
