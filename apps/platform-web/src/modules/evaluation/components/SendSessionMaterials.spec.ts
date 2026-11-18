import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, expect, it, vi } from "vitest";
import SendSessionMaterials from "./SendSessionMaterials.vue";

const http = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
const props = {
  projectId: "project",
  threadIds: ["thread"],
  show: true,
  canAuthorize: true,
};
const options = {
  global: { stubs: { BaseDialog: { template: "<div><slot /></div>" } } },
};
const sendButton = (wrapper: ReturnType<typeof mount>) =>
  wrapper.findAll("button").find((button) => /转换|重试/.test(button.text()))!;
beforeEach(() => vi.resetAllMocks());

it("requires consent and retries the same immutable business conversion", async () => {
  const wrapper = mount(SendSessionMaterials, { props, ...options });
  expect(sendButton(wrapper).attributes("disabled")).toBeDefined();
  await wrapper.get('input[type="checkbox"]').setValue(true);
  http.post.mockRejectedValueOnce(new Error("lost acknowledgement"));
  await sendButton(wrapper).trigger("click");
  await flushPromises();
  const submitted = http.post.mock.calls[0][1];
  expect(submitted).toMatchObject({
    data_class: "business",
    material_consent: true,
    auto_generate: true,
  });
  expect(
    wrapper.get('input[maxlength="120"]').attributes("disabled"),
  ).toBeDefined();
  http.post.mockResolvedValueOnce({
    data: {
      status: "delivered",
      generation_status: "needs_retry",
      materials: [],
      failures: [],
    },
  });
  await sendButton(wrapper).trigger("click");
  await flushPromises();
  expect(http.post.mock.calls[1][1]).toEqual(submitted);
});

it("does not authorize AI auto generation for a member without manage permission", async () => {
  const wrapper = mount(SendSessionMaterials, {
    props: { ...props, canAuthorize: false },
    ...options,
  });
  await wrapper.get('input[type="checkbox"]').setValue(true);
  http.post.mockResolvedValueOnce({
    data: { status: "delivered", materials: [], failures: [] },
  });
  await sendButton(wrapper).trigger("click");
  await flushPromises();
  expect(http.post.mock.calls[0][1]).toMatchObject({
    auto_generate: false,
    data_class: "business",
  });
  expect(wrapper.text()).toContain("等待项目资料负责人");
});

it("closes dialog immediately on 202 accepted async conversion", async () => {
  const wrapper = mount(SendSessionMaterials, { props, ...options });
  await wrapper.get('input[type="checkbox"]').setValue(true);
  http.post.mockResolvedValueOnce({
    status: 202,
    data: {
      status: "accepted",
      message: "评测集转换任务已提交后台处理",
      task_id: "task-123",
      title: "会话评测集",
    },
  });
  await sendButton(wrapper).trigger("click");
  await flushPromises();
  expect(http.post.mock.calls[0][1]).toMatchObject({
    async_mode: true,
  });
  expect(wrapper.emitted("close")).toHaveLength(1);
});
