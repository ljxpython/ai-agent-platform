// @vitest-environment jsdom
import { mount } from "@vue/test-utils";
import { h, nextTick, ref, type Slots } from "vue";
import { expect, it, vi } from "vitest";
import ChatSessionPool from "./ChatSessionPool.vue";
import { createChatSessionPool } from "../composables/useChatSessionPool";

const counters = vi.hoisted(() => ({ mounts: 0 }));
vi.mock("./ChatSession.vue", async () => {
  const { defineComponent, h, onMounted } = await import("vue");
  return {
    default: defineComponent({
      name: "ChatSession",
      props: { canWrite: Boolean },
      emits: ["thread", "refresh"],
      setup(_, { slots, emit }) {
        onMounted(() => {
          counters.mounts++;
        });
        return () =>
          h("div", { "data-testid": "pooled-session" }, [
            h("button", {
              "data-testid": "thread-ack",
              onClick: () => emit("thread", "new-thread"),
            }),
            h("button", {
              "data-testid": "refresh-ack",
              onClick: () => emit("refresh"),
            }),
            slots.target?.(),
          ]);
      },
    }),
  };
});

it("defers a background thread ACK until its own view attaches", async () => {
  const pool = createChatSessionPool();
  const wrapper = mount(ChatSessionPool, {
    props: { pool },
    attachTo: document.body,
  });
  const entry = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    { graphId: "g", name: "Agent", context: {} },
    undefined,
    "draft",
  );
  await nextTick();
  const ack = wrapper.find('[data-testid="thread-ack"]');
  await ack.trigger("click");
  expect(entry.threadId.value).toBe("new-thread");
  expect(entry.pendingThreadRoute).toBe("new-thread");
  const onThread = vi.fn();
  const outlet = document.createElement("div");
  document.body.append(outlet);
  pool.attachView(entry, {
    outlet,
    slots: {} as Slots,
    focusMode: ref(false),
    canWrite: ref(true),
    projectName: ref("Project"),
    threadTitle: ref("Thread"),
    onThread,
    onFork: () => {},
    onRefresh: () => {},
    onRevoked: () => {},
  });
  expect(onThread).toHaveBeenCalledTimes(1);
  expect(onThread).toHaveBeenCalledWith("new-thread");
  expect(entry.pendingThreadRoute).toBeUndefined();
  wrapper.unmount();
  outlet.remove();
});

it("moves one mounted session between an outlet and the parked host", async () => {
  counters.mounts = 0;
  const pool = createChatSessionPool();
  const wrapper = mount(ChatSessionPool, {
    props: { pool },
    attachTo: document.body,
  });
  const outlet = document.createElement("div");
  document.body.append(outlet);
  const entry = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    { graphId: "g", name: "Agent", context: {} },
    "t",
  );
  await nextTick();
  const detach = pool.attachView(entry, {
    outlet,
    slots: { target: () => h("span", "Original toolbar") } as Slots,
    focusMode: ref(false),
    canWrite: ref(true),
    projectName: ref("Project"),
    threadTitle: ref("Thread"),
    onThread: () => {},
    onFork: () => {},
    onRefresh: () => {},
    onRevoked: () => {},
  });
  await nextTick();
  expect(wrapper.findComponent({ name: "ChatSession" }).props("canWrite")).toBe(
    true,
  );
  expect(outlet.textContent).toContain("Original toolbar");
  expect(counters.mounts).toBe(1);
  detach();
  await nextTick();
  expect(outlet.textContent).toBe("");
  expect(wrapper.findComponent({ name: "ChatSession" }).props("canWrite")).toBe(
    true,
  );
  entry.canWrite.value = false;
  await nextTick();
  expect(wrapper.findComponent({ name: "ChatSession" }).props("canWrite")).toBe(
    false,
  );
  expect(counters.mounts).toBe(1);
  wrapper.unmount();
  outlet.remove();
});

it("defers refresh on inactive entry and does not call view onRefresh directly", async () => {
  const pool = createChatSessionPool();
  const wrapper = mount(ChatSessionPool, {
    props: { pool },
    attachTo: document.body,
  });
  const outlet = document.createElement("div");
  document.body.append(outlet);
  const entryA = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    { graphId: "g", name: "AgentA", context: {} },
    "thread-a",
  );
  const entryB = pool.acquire(
    "u:e:p",
    "p",
    "chat",
    { graphId: "g", name: "AgentB", context: {} },
    "thread-b",
  );
  await nextTick();

  const onRefresh = vi.fn();
  pool.attachView(entryB, {
    outlet,
    slots: {} as Slots,
    focusMode: ref(false),
    canWrite: ref(true),
    projectName: ref("Project"),
    threadTitle: ref("Thread"),
    onThread: () => {},
    onFork: () => {},
    onRefresh,
    onRevoked: () => {},
  });
  await nextTick();

  expect(entryA.visible.value).toBe(false);
  expect(entryB.visible.value).toBe(true);

  // 触发 entryA (非活动) 的 refresh 事件
  const refreshBtns = document.querySelectorAll<HTMLButtonElement>(
    '[data-testid="refresh-ack"]',
  );
  expect(refreshBtns.length).toBe(2);
  // 第一个就是 entryA 的按钮
  refreshBtns[0].click();
  await nextTick();
  expect(onRefresh).not.toHaveBeenCalled();
  expect(entryA.needsRefresh).toBe(true);

  // 触发 entryB (当前活动) 的 refresh 事件
  refreshBtns[1].click();
  await nextTick();
  expect(onRefresh).toHaveBeenCalledTimes(1);

  wrapper.unmount();
  outlet.remove();
});
