import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useThemeStore } from "@/stores/theme";
import ObservabilityDashboardPage from "./ObservabilityDashboardPage.vue";

const mockRouter = { push: vi.fn() };

vi.mock("vue-router", () => ({
  useRouter: () => mockRouter,
}));

describe("ObservabilityDashboardPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
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
    expect(wrapper.text()).toContain("链路诊断中心");
    expect(wrapper.text()).toContain("刷新");
    expect(wrapper.text()).toContain("全屏");
    expect(wrapper.text()).toContain("独立窗口");
  });

  it("embeds overview dashboard with kiosk and theme mode", () => {
    const themeStore = useThemeStore();
    themeStore.mode = "dark";

    const wrapper = renderPage();
    const iframe = wrapper.find("iframe");
    expect(iframe.exists()).toBe(true);

    const src = iframe.attributes("src") ?? "";
    expect(src).toContain("kiosk");
    expect(src).toContain("theme=dark");
    expect(src).toContain("ai-platform-overview");
  });

  it("navigates to trace diagnostics when clicking button", async () => {
    const wrapper = renderPage();
    const buttons = wrapper.findAll("button");
    const traceBtn = buttons.find((btn) => btn.text().includes("链路诊断中心"));
    expect(traceBtn).toBeDefined();
    await traceBtn?.trigger("click");
    expect(mockRouter.push).toHaveBeenCalledWith({
      name: "workspace-trace-diagnostics",
    });
  });

  it("clears loading mask when iframe loads", async () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("正在建立可观测性指标流连接");

    const iframe = wrapper.find("iframe");
    await iframe.trigger("load");

    expect(wrapper.text()).not.toContain("正在建立可观测性指标流连接");
  });
});
