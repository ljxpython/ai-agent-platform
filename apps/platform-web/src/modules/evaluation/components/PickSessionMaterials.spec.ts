import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import PickSessionMaterials from "./PickSessionMaterials.vue";

const http = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
const options = {
  props: { show: false, projectId: "project", agentId: "agent" },
  global: { stubs: { BaseDialog: { template: "<div><slot /></div>" } } },
};
const page = (start = 0, size = 1, next: number | null = null) => ({
  data: {
    items: Array.from({ length: size }, (_, i) => ({
      thread_id: `thread-${start + i}`,
      title: `会话${start + i}`,
      created_at: "2026-11-18",
      status: "idle",
    })),
    next_offset: next,
    limited: false,
    notice: "有权查看的会话",
    scanned: size,
  },
});
beforeEach(() => vi.resetAllMocks());

it("keeps date/status filters and pagination without sending or rendering feedback", async () => {
  http.post
    .mockResolvedValueOnce(page(0, 1, 100))
    .mockResolvedValueOnce(page(1));
  const wrapper = mount(PickSessionMaterials, options);
  await wrapper.setProps({ show: true });
  await flushPromises();
  expect(wrapper.text()).not.toMatch(/好评|差评|我的反馈/);
  expect(http.post.mock.calls[0][1]).not.toHaveProperty("feedback");
  await wrapper.get("select").setValue("error");
  const next = wrapper
    .findAll("button")
    .find((b) => b.text().includes("下一批"))!;
  await next.trigger("click");
  await flushPromises();
  expect(http.post.mock.calls[1][1]).toMatchObject({
    agent_id: "agent",
    offset: 100,
    status: "error",
  });
  expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(2);
  wrapper.unmount();
});

it("limits selection to 20 sessions and emits the selected IDs", async () => {
  http.post.mockResolvedValueOnce(page(0, 21));
  const wrapper = mount(PickSessionMaterials, options);
  await wrapper.setProps({ show: true });
  await flushPromises();
  const boxes = wrapper.findAll('input[type="checkbox"]');
  for (const box of boxes.slice(0, 20)) await box.setValue(true);
  expect(boxes[20].attributes("disabled")).toBeDefined();
  await wrapper
    .findAll("button")
    .find((b) => b.text().includes("使用选中的"))!
    .trigger("click");
  expect(wrapper.emitted("select")?.[0][0]).toHaveLength(20);
  wrapper.unmount();
});

it("clears selection and ignores responses from the previous project", async () => {
  let finish!: (value: unknown) => void;
  http.post.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const wrapper = mount(PickSessionMaterials, options);
  await wrapper.setProps({ show: true });
  http.post.mockResolvedValueOnce(page(10));
  await wrapper.setProps({ projectId: "another-project" });
  await flushPromises();
  finish(page(0));
  await flushPromises();
  expect(wrapper.text()).toContain("会话10");
  expect(wrapper.text()).not.toContain("会话0");
  expect(http.post.mock.calls[1][2]).toMatchObject({
    headers: { "X-Project-Id": "another-project" },
  });
  wrapper.unmount();
});
