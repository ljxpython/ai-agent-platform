import { config, flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MessageFeedback from "./MessageFeedback.vue";

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("@/services/http/client", () => ({ platformHttpClient: http }));
const props = {
  projectId: "p",
  threadId: "t",
  messageId: "m",
  allowExport: true,
};
const feedback = {
  revision: 1,
  event_id: "event",
  rating: "positive",
  comment: "",
};

async function show() {
  const wrapper = mount(MessageFeedback, { props });
  await wrapper.get("button").trigger("click");
  await flushPromises();
  return wrapper;
}
function button(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll("button").find((b) => b.text() === label)!;
}
async function prepare(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('[aria-label="合成场景"]').setValue("计算 2+3");
  await wrapper.get('[aria-label="正确预期"]').setValue("5");
  await wrapper.get('input[type="checkbox"]').setValue(true);
}
beforeEach(() => {
  config.global.stubs.RouterLink = RouterLinkStub;
  vi.resetAllMocks();
  http.get.mockResolvedValue({ data: feedback });
});

describe("MessageFeedback", () => {
  it("refreshes projection independently of delivery and clears stale export status", async () => {
    http.get.mockResolvedValueOnce({
      data: {
        ...feedback,
        link_status: "linked",
        mlflow_trace_ids: ["tr-test"],
        export: {
          export_id: "old",
          status: "exported",
          scenario: "2+3",
          expected: "5",
        },
      },
    });
    const wrapper = await show();
    expect(wrapper.text()).toContain("反馈已关联原生评估（1 条 Trace）");
    http.get.mockResolvedValueOnce({
      data: {
        ...feedback,
        link_status: "unavailable",
        link_reason: "source_revoked_or_expired",
        export: {
          export_id: "old",
          status: "revoked",
          scenario: "",
          expected: "",
        },
      },
    });
    await button(wrapper, "刷新状态").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("导出授权已撤销，关联题库不可新运行");
    expect(wrapper.text()).toContain("原生评价撤销由后台核对");
    expect(wrapper.text()).not.toContain("反馈已关联");
    expect(wrapper.text()).not.toContain("exported");
    expect(button(wrapper, "发送到评测审核")).toBeUndefined();
  });

  it.each([
    ["pending", "", "反馈关联处理中"],
    ["unavailable", "export_authorization_required", "尚未授权关联评测"],
    ["unavailable", "projection_deadline_exceeded", "暂无法关联原生评估"],
  ])("shows projection %s / %s truthfully", async (status, reason, message) => {
    http.get.mockResolvedValue({
      data: { ...feedback, link_status: status, link_reason: reason },
    });
    const wrapper = await show();
    expect(wrapper.text()).toContain(message);
    expect(wrapper.text()).not.toContain("反馈已关联");
  });

  it("restores delivery and invalidates old export after editing feedback", async () => {
    http.get.mockResolvedValue({
      data: {
        ...feedback,
        export: {
          export_id: "old",
          status: "exported",
          scenario: "2+3",
          expected: "5",
        },
      },
    });
    const wrapper = await show();
    expect(
      button(wrapper, "发送到评测审核").attributes("disabled"),
    ).toBeDefined();
    http.post.mockResolvedValue({
      data: { ...feedback, revision: 2, event_id: "new" },
    });
    await button(wrapper, "保存反馈").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("反馈已保存");
    expect(wrapper.text()).not.toContain("问题待确认");
    expect(button(wrapper, "发送到评测审核")).toBeUndefined();
  });

  it("keeps authorization editable after a definite validation rejection", async () => {
    const wrapper = await show();
    await prepare(wrapper);
    http.post.mockRejectedValue({ status: 422, message: "材料无效" });
    await button(wrapper, "授权合成复现").trigger("click");
    await flushPromises();
    expect(
      wrapper.findAll("fieldset")[1].attributes("disabled"),
    ).toBeUndefined();
    expect(button(wrapper, "发送到评测审核")).toBeUndefined();
    expect(wrapper.get('[role="alert"]').text()).toContain("材料无效");
  });

  it("retries exactly the same export after a lost response", async () => {
    const wrapper = await show();
    await prepare(wrapper);
    http.post.mockRejectedValueOnce(new TypeError("network"));
    await button(wrapper, "授权合成复现").trigger("click");
    await flushPromises();
    const original = http.post.mock.calls[0][1];
    expect(wrapper.findAll("fieldset")[1].attributes("disabled")).toBeDefined();
    http.post.mockResolvedValue({
      data: { export_id: original.export_id, status: "ready" },
    });
    await button(wrapper, "重试原授权请求").trigger("click");
    await flushPromises();
    expect(http.post.mock.calls[1][1]).toEqual(original);
    expect(button(wrapper, "发送到评测审核")).toBeDefined();
  });

  it("ignores a late read after switching to another message", async () => {
    let resolve!: (value: unknown) => void;
    http.get.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const wrapper = mount(MessageFeedback, { props });
    await wrapper.get("button").trigger("click");
    await wrapper.setProps({ messageId: "other" });
    resolve({ data: feedback });
    await flushPromises();
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(wrapper.get("button").attributes("disabled")).toBeUndefined();
  });

  it("reconciles a feedback write with a lost response without submitting twice", async () => {
    const wrapper = await show();
    http.post.mockImplementationOnce(async (_path, body) => {
      http.get.mockResolvedValue({
        data: { ...feedback, event_id: body.event_id, revision: 2 },
      });
      throw new TypeError("network");
    });
    await button(wrapper, "保存反馈").trigger("click");
    await flushPromises();
    expect(http.post).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("反馈已保存");
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });
});
