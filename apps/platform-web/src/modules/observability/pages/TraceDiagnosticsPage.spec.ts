import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useThemeStore } from "@/stores/theme";
import TraceDiagnosticsPage from "./TraceDiagnosticsPage.vue";

const mockRoute = { query: {} as Record<string, string> };
const mockRouter = { push: vi.fn() };

vi.mock("vue-router", () => ({
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
}));

describe("TraceDiagnosticsPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    mockRoute.query = {};
    vi.clearAllMocks();
  });

  function renderPage() {
    return mount(TraceDiagnosticsPage, {
      global: {
        stubs: {
          BaseButton: {
            template:
              '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          BaseInput: {
            props: ["modelValue", "placeholder"],
            template:
              '<input :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" @keydown="$emit(\'keydown\', $event)" />',
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

  it("renders page header, input and buttons", () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("链路诊断中心");
    expect(wrapper.text()).toContain("诊断");
    expect(wrapper.text()).toContain("指标大盘");
    expect(wrapper.text()).toContain("刷新");
    expect(wrapper.text()).toContain("全屏");
    expect(wrapper.text()).toContain("独立窗口");
  });

  it("shows guide card and demo button when no traceId is provided", () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("Trace ID 获取途径与排障指引");
    expect(wrapper.text()).toContain("演示：载入生产真实 Trace");
  });

  it("switches to Loki explore view and shows trace badge when traceId is provided", () => {
    mockRoute.query = { traceId: "54aaf459b9c5415b90370e5874dbb255" };

    const wrapper = renderPage();
    const iframe = wrapper.find("iframe");
    expect(iframe.exists()).toBe(true);

    const src = iframe.attributes("src") ?? "";
    expect(src).toContain("/explore");
    expect(src).toContain("54aaf459b9c5415b90370e5874dbb255");
    expect(wrapper.text()).toContain("当前诊断 Trace ID");
    expect(wrapper.text()).toContain("54aaf459b9c5415b90370e5874dbb255");
    expect(wrapper.text()).toContain("在 Langfuse 查看大模型链路树");
  });

  it("navigates to dashboard when clicking 指标大盘", async () => {
    const wrapper = renderPage();
    const buttons = wrapper.findAll("button");
    const dashBtn = buttons.find((btn) => btn.text().includes("指标大盘"));
    expect(dashBtn).toBeDefined();
    await dashBtn?.trigger("click");
    expect(mockRouter.push).toHaveBeenCalledWith({
      name: "workspace-observability",
    });
  });

  it("clears loading mask when iframe loads", async () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("正在检索跨微服务全链路日志");

    const iframe = wrapper.find("iframe");
    await iframe.trigger("load");

    expect(wrapper.text()).not.toContain("正在检索跨微服务全链路日志");
  });
});
