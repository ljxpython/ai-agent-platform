import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import InspectionConsent from "./InspectionConsent.vue";

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
const props = { scope: { projectId: "p", threadId: "t", runId: "r" } };
function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll("button").find((b) => b.text() === label)!;
}
beforeEach(() => {
  vi.resetAllMocks();
  http.get.mockImplementation(async (url) => ({
    data: url.includes("capabilities")
      ? {
          quality_inspection: true,
          inspection_policy: {
            judge_route: "managed",
            budget_policy_version: "v1",
          },
        }
      : url.includes("inspection/context")
        ? { agent_id: "platform-agent", graph_id: "dearflow_agent" }
        : [],
  }));
});

it("keeps uncertain consent immutable and reuses its id", async () => {
  const wrapper = mount(InspectionConsent, { props });
  await wrapper.get("button").trigger("click");
  await flushPromises();
  await wrapper.get('[aria-label="巡检合成输入"]').setValue("2+3");
  await wrapper.get('[aria-label="巡检合成输出"]').setValue("5");
  await wrapper.get('input[type="checkbox"]').setValue(true);
  http.post.mockRejectedValueOnce(new TypeError("network"));
  await button(wrapper, "授权质量巡检").trigger("click");
  await flushPromises();
  const original = http.post.mock.calls[0][1];
  expect(original.purpose).toBe("quality_inspection");
  expect(original.agent_id).toBe("platform-agent");
  expect(original.allowed_fields).toEqual(["input", "output"]);
  expect(wrapper.get("fieldset").attributes("disabled")).toBeDefined();
  http.post.mockResolvedValueOnce({
    data: { export_id: original.export_id, status: "ready" },
  });
  await button(wrapper, "重试同一巡检授权").trigger("click");
  await flushPromises();
  expect(http.post.mock.calls[1][1]).toEqual(original);
  http.post.mockResolvedValueOnce({
    data: {
      export_id: original.export_id,
      status: "exported",
      receipt: { status: "queued" },
    },
  });
  await button(wrapper, "提交巡检抽样").trigger("click");
  await flushPromises();
  expect(wrapper.text()).toContain("queued");
  http.post.mockResolvedValueOnce({
    data: { export_id: original.export_id, status: "revoked" },
  });
  await button(wrapper, "撤销巡检授权").trigger("click");
  await flushPromises();
  expect(button(wrapper, "提交巡检抽样")).toBeUndefined();
  expect(wrapper.text()).toContain("revoked");
});

it("restores an existing grant after reload", async () => {
  const prior = http.get.getMockImplementation()!;
  http.get.mockImplementation((url, options) =>
    url.includes("inspection/exports")
      ? Promise.resolve({ data: [{ export_id: "old", status: "exported" }] })
      : prior(url, options),
  );
  const wrapper = mount(InspectionConsent, { props });
  await wrapper.get("button").trigger("click");
  await flushPromises();
  expect(wrapper.text()).toContain("old");
  expect(button(wrapper, "授权质量巡检")).toBeUndefined();
});

it("ignores a delayed read when the run changes", async () => {
  let resolve!: (value: unknown) => void;
  http.get.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const wrapper = mount(InspectionConsent, { props });
  await wrapper.get("button").trigger("click");
  await wrapper.setProps({ scope: { ...props.scope, runId: "other" } });
  resolve({ data: { status: "success", assistant_id: "agent" } });
  await flushPromises();
  expect(wrapper.find("section").exists()).toBe(false);
});
