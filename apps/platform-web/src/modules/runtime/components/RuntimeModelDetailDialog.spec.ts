import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import RuntimeModelDetailDialog from "./RuntimeModelDetailDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import StatusPill from "@/components/platform/StatusPill.vue";

describe("RuntimeModelDetailDialog", () => {
  const mockModel = {
    id: "model-001",
    model: "DeepSeek-V4-Flash",
    display_name: "DeepSeek V4 Flash (中转)",
    provider: "deepseek-proxy",
    base_url: "http://120.48.180.39:20002/v1",
    protocol: "openai-compatible",
    enabled: true,
    credential_configured: true,
  };

  function createWrapper(props: Record<string, unknown> = {}) {
    const pinia = createPinia();
    setActivePinia(pinia);

    return mount(RuntimeModelDetailDialog, {
      props: {
        show: true,
        canManage: true,
        isProjectDefault: true,
        model: mockModel,
        ...props,
      },
      global: {
        plugins: [pinia],
        stubs: {
          BaseDialog: {
            props: ["show", "title"],
            template:
              '<div v-if="show"><h2>{{ title }}</h2><slot /><slot name="footer" /></div>',
          },
        },
        components: {
          BaseButton,
          BaseIcon,
          StatusPill,
        },
      },
    });
  }

  it("renders complete model technical details when open", () => {
    const wrapper = createWrapper();
    expect(wrapper.text()).toContain("模型详情");
    expect(wrapper.text()).toContain("DeepSeek-V4-Flash");
    expect(wrapper.text()).toContain("DeepSeek V4 Flash (中转)");
    expect(wrapper.text()).toContain("deepseek-proxy");
    expect(wrapper.text()).toContain("http://120.48.180.39:20002/v1");
    expect(wrapper.text()).toContain("openai-compatible");
    expect(wrapper.text()).toContain("默认模型");
    expect(wrapper.text()).toContain("已启用");
    expect(wrapper.text()).toContain("API 凭据已配置");
  });

  it("emits edit event when clicking edit button in footer", async () => {
    const wrapper = createWrapper();
    const editBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("编辑配置"));
    expect(editBtn).toBeDefined();

    await editBtn?.trigger("click");
    expect(wrapper.emitted("edit")).toBeDefined();
    expect(wrapper.emitted("edit")?.[0][0]).toEqual(mockModel);
  });

  it("emits close event when clicking close button", async () => {
    const wrapper = createWrapper();
    const closeBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("关闭"));
    expect(closeBtn).toBeDefined();

    await closeBtn?.trigger("click");
    expect(wrapper.emitted("close")).toBeDefined();
  });
});
