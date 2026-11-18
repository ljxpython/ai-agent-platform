import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import { reactive } from "vue";
import EvaluationMovedPage from "./EvaluationMovedPage.vue";

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
vi.mock("@/services/auth/token", () => ({ hasStoredAuthSession: () => true }));
const route = reactive({
  params: { projectId: "project", itemId: "" },
  query: { url: "https://attacker.invalid" },
});
vi.mock("vue-router", () => ({ useRoute: () => route }));
beforeEach(() => {
  vi.resetAllMocks();
  route.params = { projectId: "project", itemId: "" };
});

it("offers an explicit link from server configuration, without executing an evaluation", async () => {
  const id = "550e8400-e29b-41d4-a716-446655440000";
  route.params.itemId = id;
  http.get.mockResolvedValue({
    data: { workbench: true, authoring_url: "http://evalflow.example:9128" },
  });
  const wrapper = mount(EvaluationMovedPage);
  await flushPromises();
  expect(wrapper.get("a").attributes("href")).toBe(
    `http://evalflow.example:9128/#/authoring/${id}`,
  );
  expect(http.get).toHaveBeenCalledOnce();
  expect(http.post).not.toHaveBeenCalled();
  wrapper.unmount();
});

it.each([
  { workbench: false, authoring_url: null },
  { workbench: true, authoring_url: "" },
  { workbench: true, authoring_url: "javascript:alert(1)" },
  { workbench: true, authoring_url: "https://user:pass@example.invalid" },
])("does not offer an unavailable or unsafe destination: %j", async (data) => {
  http.get.mockResolvedValue({ data });
  const wrapper = mount(EvaluationMovedPage);
  await flushPromises();
  expect(wrapper.find("a").exists()).toBe(false);
  expect(wrapper.get('[role="status"]').text()).not.toBe("");
  wrapper.unmount();
});

it("discards late project responses and keeps failures visible", async () => {
  let resolveOld!: (value: unknown) => void;
  http.get.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
  );
  const wrapper = mount(EvaluationMovedPage);
  http.get.mockRejectedValueOnce({
    response: {
      status: 503,
      data: {
        error: { code: "evaluation_unavailable", message: "评测服务暂不可用" },
      },
    },
  });
  route.params.projectId = "another-project";
  await flushPromises();
  resolveOld({
    data: { workbench: true, authoring_url: "https://old.invalid" },
  });
  await flushPromises();
  expect(wrapper.find("a").exists()).toBe(false);
  expect(wrapper.text()).toContain("评测服务暂不可用");
  wrapper.unmount();
});
