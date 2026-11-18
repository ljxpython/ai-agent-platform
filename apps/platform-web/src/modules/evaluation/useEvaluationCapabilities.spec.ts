import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { useEvaluationCapabilities } from "./useEvaluationCapabilities";

const http = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
vi.mock("@/utils/http-error", () => ({
  resolvePlatformHttpErrorMessage: () => "评测服务暂不可用",
}));
beforeEach(() => vi.resetAllMocks());

function setup(project = "project") {
  const projectId = ref(project);
  let state!: ReturnType<typeof useEvaluationCapabilities>;
  const wrapper = mount(
    defineComponent({
      setup() {
        state = useEvaluationCapabilities(projectId);
        return () => h("div");
      },
    }),
  );
  return { projectId, wrapper, state };
}

it("does not request capabilities without a project", async () => {
  const { wrapper, state } = setup("");
  await flushPromises();
  expect(http.get).not.toHaveBeenCalled();
  expect(state.available.value).toBe(false);
  expect(state.unavailableReason.value).toContain("未启用");
  wrapper.unmount();
});

it("resets capabilities on project change and ignores a late previous response", async () => {
  let finish!: (value: unknown) => void;
  http.get.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const { projectId, wrapper, state } = setup();
  http.get.mockResolvedValueOnce({ data: { workbench: false } });
  projectId.value = "other-project";
  await flushPromises();
  finish({
    data: { workbench: true, authoring_url: "https://previous.example" },
  });
  await flushPromises();
  expect(state.available.value).toBe(false);
  expect(state.authoringUrl.value).toBe("");
  expect(http.get.mock.calls[1][1].headers["X-Project-Id"]).toBe(
    "other-project",
  );
  wrapper.unmount();
});

it("fails closed when the service cannot confirm access", async () => {
  http.get.mockResolvedValueOnce({
    data: { workbench: true, authoring_url: "https://evalflow.example" },
  });
  const { projectId, wrapper, state } = setup();
  await flushPromises();
  expect(state.available.value).toBe(true);
  http.get.mockRejectedValueOnce(new Error("unavailable"));
  projectId.value = "other-project";
  await flushPromises();
  expect(state.available.value).toBe(false);
  expect(state.authoringUrl.value).toBe("");
  expect(state.unavailableReason.value).toBe("评测服务暂不可用");
  wrapper.unmount();
});
