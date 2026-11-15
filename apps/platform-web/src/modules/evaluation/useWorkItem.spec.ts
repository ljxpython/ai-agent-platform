import { defineComponent, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useWorkItem } from "./useWorkItem";

const api = vi.hoisted(() => ({
  readWorkItem: vi.fn(),
  commandWorkItem: vi.fn(),
}));
vi.mock("@/services/evaluation/workbench", () => api);
const wrappers: ReturnType<typeof mount>[] = [];
beforeEach(() => vi.resetAllMocks());
afterEach(() => wrappers.splice(0).forEach((wrapper) => wrapper.unmount()));

function setup() {
  const project = ref("p1");
  const id = ref("i1");
  let state!: ReturnType<typeof useWorkItem>;
  wrappers.push(
    mount(
      defineComponent({
        setup() {
          state = useWorkItem(project, id);
          return () => null;
        },
      }),
    ),
  );
  return {
    project,
    id,
    get state() {
      return state;
    },
  };
}

it("does not carry a late response into another work item", async () => {
  let finish!: (value: unknown) => void;
  api.readWorkItem.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const screen = setup();
  api.readWorkItem.mockResolvedValueOnce({ id: "i2", title: "新问题" });
  screen.id.value = "i2";
  await flushPromises();
  finish({ id: "i1", title: "旧私有资料" });
  await flushPromises();
  expect(screen.state.item.value?.id).toBe("i2");
});

it("retains the exact original request when the write receipt is unknown", async () => {
  api.readWorkItem.mockResolvedValue({ id: "i1" });
  const screen = setup();
  await flushPromises();
  api.commandWorkItem.mockRejectedValueOnce(new TypeError("network"));
  await screen.state.act("approve", { revision: 1 });
  const original = api.commandWorkItem.mock.calls[0][3];
  expect(screen.state.pending.value).not.toBeNull();
  api.commandWorkItem.mockResolvedValue({ id: "i1", status: "preparing" });
  await screen.state.act("approve", { revision: 2 }, true);
  expect(api.commandWorkItem.mock.calls[1][3]).toEqual(original);
  expect(screen.state.pending.value).toBeNull();
});

it("waits for real cancellation state and clears denied contents", async () => {
  api.readWorkItem.mockResolvedValue({ id: "i1", status: "running" });
  const screen = setup();
  await flushPromises();
  api.commandWorkItem.mockResolvedValue({ id: "i1", status: "cancelling" });
  await screen.state.act("cancel", { kind: "assistant", target_id: "j1" });
  expect(screen.state.item.value?.status).toBe("cancelling");
  api.readWorkItem.mockRejectedValue({ status: 403, message: "无权读取" });
  await screen.state.refresh();
  expect(screen.state.item.value).toBeNull();
});

it("clears an unknown receipt only when its matching action is persisted", async () => {
  api.readWorkItem.mockResolvedValue({ id: "i1" });
  const screen = setup();
  await flushPromises();
  api.commandWorkItem.mockRejectedValueOnce(new TypeError("network"));
  await screen.state.act("generate", { feedback: "两轮" });
  const requestId = screen.state.pending.value!.command.request_id;
  api.readWorkItem.mockResolvedValue({
    id: "i1",
    history: [{ action: "cancel", request_id: requestId }],
  });
  await screen.state.refresh();
  expect(screen.state.pending.value).not.toBeNull();
  api.readWorkItem.mockResolvedValue({
    id: "i1",
    history: [{ action: "generate", request_id: requestId }],
  });
  await screen.state.refresh();
  expect(screen.state.pending.value).toBeNull();
  expect(api.commandWorkItem).toHaveBeenCalledTimes(1);
});

it("replaces body with the closed view after revocation", async () => {
  api.readWorkItem.mockResolvedValueOnce({ id: "i1", description: "合成正文" });
  const screen = setup();
  await flushPromises();
  api.commandWorkItem.mockResolvedValue({ status: "revoked" });
  api.readWorkItem.mockResolvedValue({
    id: "i1",
    status: "materials_unavailable",
  });
  await screen.state.act("revoke", { grant_id: "g1" });
  expect(screen.state.item.value?.description).toBeUndefined();
  expect(screen.state.item.value?.status).toBe("materials_unavailable");
});

it("does not let an earlier poll restore revoked contents", async () => {
  api.readWorkItem.mockResolvedValueOnce({ id: "i1", description: "合成正文" });
  const screen = setup();
  await flushPromises();
  let finish!: (value: unknown) => void;
  api.readWorkItem.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const poll = screen.state.refresh(true);
  expect(screen.state.loading.value).toBe(false);
  api.commandWorkItem.mockResolvedValue({ status: "revoked" });
  api.readWorkItem.mockResolvedValue({
    id: "i1",
    status: "materials_unavailable",
  });
  await screen.state.act("revoke", { grant_id: "g1" });
  finish({ id: "i1", description: "过期正文" });
  await poll;
  expect(screen.state.item.value?.description).toBeUndefined();
  expect(screen.state.item.value?.status).toBe("materials_unavailable");
});
