import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useThemeStore } from "@/stores/theme";
import ObservabilityDashboardPage from "./ObservabilityDashboardPage.vue";

describe("ObservabilityDashboardPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  function renderPage() {
    return mount(ObservabilityDashboardPage, {
      global: {
        stubs: {
          BaseButton: {
            template:
              '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          BaseIcon: {
            props: ["name"],
            template: '<i :data-icon="name" />',
          },
          PageHeader: {
            props: ["title", "eyebrow", "description"],
            template: `
              <header class="page-header">
                <div>{{ eyebrow }} / {{ title }}</div>
                <p>{{ description }}</p>
                <div class="actions"><slot name="actions" /></div>
              </header>
            `,
          },
        },
      },
    });
  }

  it("renders page header and action buttons", () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("指标大盘");
    expect(wrapper.text()).toContain("刷新图表");
    expect(wrapper.text()).toContain("全屏看板");
    expect(wrapper.text()).toContain("独立窗口打开");
  });

  it("embeds iframe with kiosk and theme query params", () => {
    const themeStore = useThemeStore();
    themeStore.mode = "dark";

    const wrapper = renderPage();
    const iframe = wrapper.find("iframe");
    expect(iframe.exists()).toBe(true);

    const src = iframe.attributes("src") ?? "";
    expect(src).toContain("kiosk");
    expect(src).toContain("theme=dark");
  });

  it("clears loading mask when iframe loads", async () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("正在加载 Grafana 工业级指标大盘");

    const iframe = wrapper.find("iframe");
    await iframe.trigger("load");

    expect(wrapper.text()).not.toContain("正在加载 Grafana 工业级指标大盘");
  });
});
