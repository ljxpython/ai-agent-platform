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
      emits: ["thread"],
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
  expect(outlet.textContent).toContain("Original toolbar");
  expect(counters.mounts).toBe(1);
  detach();
  await nextTick();
  expect(outlet.textContent).toBe("");
  expect(counters.mounts).toBe(1);
  wrapper.unmount();
  outlet.remove();
});
