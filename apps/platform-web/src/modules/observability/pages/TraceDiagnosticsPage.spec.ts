import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TraceDiagnosticsPage from "./TraceDiagnosticsPage.vue";
import { platformHttpClient } from "@/services/http/client";
import { useWorkspaceStore } from "@/stores/workspace";

const mockRoute = { query: {} as Record<string, string> };
const mockRouter = { push: vi.fn() };

vi.mock("vue-router", () => ({
  useRoute: () => mockRoute,
  useRouter: () => mockRouter,
}));

vi.mock("@/services/http/client", () => ({
  platformHttpClient: {
    get: vi.fn(),
  },
}));

describe("TraceDiagnosticsPage (Native Timeline Edition)", () => {
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

  it("renders page header, input and guide card when no traceId", () => {
    const wrapper = renderPage();
    expect(wrapper.text()).toContain("链路诊断中心");
    expect(wrapper.text()).toContain("诊断");
    expect(wrapper.text()).toContain("指标大盘");
    expect(wrapper.text()).toContain("EvalFlow 评测大盘");
    expect(wrapper.text()).toContain("Trace ID 获取途径与排障指引");
    expect(wrapper.text()).toContain("演示：载入 EvalFlow 真实 Trace");
  });

  it("fetches and renders native timeline logs when traceId is provided", async () => {
    const mockLogs = {
      trace_id: "54aaf459b9c5415b90370e5874dbb255",
      total: 1,
      services: ["platform-api"],
      logs: [
        {
          timestamp: "2026-10-22T19:57:05.737561+00:00",
          nanos: "1792670225737713000",
          service: "platform-api",
          level: "info",
          event: "http.request.completed",
          summary: "GET /health -> 401 (0.44ms)",
          span_id: "dd806a17b393455b",
          payload: { status_code: 401 },
          raw: "raw log string",
        },
      ],
    };

    vi.mocked(platformHttpClient.get).mockResolvedValue({
      data: mockLogs,
    } as any);

    mockRoute.query = { traceId: "54aaf459b9c5415b90370e5874dbb255" };
    const wrapper = renderPage();
    await new Promise((r) => setTimeout(r, 50));

    expect(wrapper.text()).toContain("诊断 Trace ID");
    expect(wrapper.text()).toContain("54aaf459b9c5415b90370e5874dbb255");
    expect(wrapper.text()).toContain("GET /health -> 401 (0.44ms)");
    expect(wrapper.text()).toContain("platform-api");
    expect(wrapper.text()).toContain("极速时间轴");
    expect(wrapper.text()).toContain("Grafana Explore");
  });

  it("switches view tabs between native timeline and Grafana explore", async () => {
    mockRoute.query = { traceId: "54aaf459b9c5415b90370e5874dbb255" };
    const wrapper = renderPage();
    const buttons = wrapper.findAll("button");
    const grafanaTab = buttons.find((btn) =>
      btn.text().includes("Grafana Explore"),
    );
    expect(grafanaTab).toBeDefined();

    await grafanaTab?.trigger("click");
    expect(wrapper.find("iframe").exists()).toBe(true);
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

  it("carries x-project-id header when workspace currentProjectId is available", async () => {
    const store = useWorkspaceStore();
    store.currentProjectId = "proj-obs-999";

    vi.mocked(platformHttpClient.get).mockResolvedValue({
      data: {
        trace_id: "tr-test-scoped-1",
        total: 1,
        services: ["platform-api"],
        logs: [],
      },
    } as any);

    mockRoute.query = { traceId: "tr-test-scoped-1" };
    renderPage();
    await new Promise((r) => setTimeout(r, 50));

    expect(platformHttpClient.get).toHaveBeenCalledWith(
      "/api/v1/observability/traces/tr-test-scoped-1/logs",
      {
        headers: {
          "x-project-id": "proj-obs-999",
        },
      },
    );
  });

  it("renders partial log coverage warning banner when response has partial=true", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValue({
      data: {
        trace_id: "tr-test-partial-2",
        total: 1,
        services: ["platform-api"],
        partial: true,
        coverage: "bounded_structured_project_logs_only",
        logs: [
          {
            timestamp: "2026-11-16T12:00:00Z",
            nanos: "1000000000",
            service: "platform-api",
            level: "info",
            event: "http.req",
            summary: "GET /api/v1/test",
            span_id: "span-1234",
            payload: {},
          },
        ],
      },
    } as any);

    mockRoute.query = { traceId: "tr-test-partial-2" };
    const wrapper = renderPage();
    await new Promise((r) => setTimeout(r, 50));

    expect(wrapper.text()).toContain("当前日志查询受项目安全范围约束");
    expect(wrapper.text()).toContain("bounded_structured_project_logs_only");
  });

  it("handles missing raw log safely without crashing when filtering keywords", async () => {
    vi.mocked(platformHttpClient.get).mockResolvedValue({
      data: {
        trace_id: "tr-test-no-raw-3",
        total: 1,
        services: ["platform-api"],
        logs: [
          {
            timestamp: "2026-11-16T12:00:00Z",
            nanos: "2000000000",
            service: "platform-api",
            level: "info",
            event: "http.req",
            summary: "Crash Proof Summary",
            span_id: "span-5678",
            payload: {},
          },
        ],
      },
    } as any);

    mockRoute.query = { traceId: "tr-test-no-raw-3" };
    const wrapper = renderPage();
    await new Promise((r) => setTimeout(r, 50));

    expect(wrapper.text()).toContain("Crash Proof Summary");

    const searchInput = wrapper.find(
      'input[placeholder="按关键字/路径/错误搜索..."]',
    );
    expect(searchInput.exists()).toBe(true);
    await searchInput.setValue("Crash");
    expect(wrapper.text()).toContain("Crash Proof Summary");
  });
});
