import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import QueuedMessagesBanner from "./QueuedMessagesBanner.vue";

describe("QueuedMessagesBanner.vue", () => {
  it("renders queued messages with content preview", () => {
    const wrapper = mount(QueuedMessagesBanner, {
      props: {
        receipts: [
          {
            message_id: "m-1",
            thread_id: "t-1",
            target_run_id: "r-1",
            sequence: 1,
            status: "queued",
            content: "帮我补充一下单元测试",
          },
        ],
        canWrite: true,
        canSend: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("排队补充消息");
    expect(wrapper.text()).toContain("排队等待中");
    expect(wrapper.text()).toContain("帮我补充一下单元测试");
  });

  it("renders not_consumed status and emits resendAsNew and restoreDraft", async () => {
    const wrapper = mount(QueuedMessagesBanner, {
      props: {
        receipts: [
          {
            message_id: "m-2",
            thread_id: "t-1",
            target_run_id: "r-1",
            sequence: 2,
            status: "not_consumed",
            reason: "run_ended",
            content: "继续",
          },
        ],
        canWrite: true,
        canSend: true,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("未消费");
    expect(wrapper.text()).toContain("上一回合已终止，未消费");
    expect(wrapper.text()).toContain("继续");

    // Click resend button
    const resendBtn = wrapper.findAll("button").find((b) => b.text().includes("作为新消息发送"));
    expect(resendBtn).toBeDefined();
    await resendBtn?.trigger("click");
    expect(wrapper.emitted("resendAsNew")?.[0]).toEqual(["继续", "m-2"]);

    // Click restore button
    const restoreBtn = wrapper.findAll("button").find((b) => b.text().includes("恢复到输入框"));
    expect(restoreBtn).toBeDefined();
    await restoreBtn?.trigger("click");
    expect(wrapper.emitted("restoreDraft")?.[0]).toEqual(["继续", "m-2"]);
  });

  it("handles refresh button click", async () => {
    const wrapper = mount(QueuedMessagesBanner, {
      props: {
        receipts: [],
        receiptError: "网络连接超时",
        canWrite: true,
        canSend: false,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("网络连接超时");
    const refreshBtn = wrapper.findAll("button").find((b) => b.text().includes("刷新"));
    await refreshBtn?.trigger("click");
    expect(wrapper.emitted("refresh")).toBeDefined();
  });

  it("renders queueItems with order indicators and handles moveUp, moveDown, restoreDraft, and removeItem", async () => {
    const queueItems = [
      { id: "q-1", content: "第一条待执行指令", createdAt: 1000 },
      { id: "q-2", content: "第二条排队指令", createdAt: 2000 },
      { id: "q-3", content: "第三条排队指令", createdAt: 3000 },
    ];

    const wrapper = mount(QueuedMessagesBanner, {
      props: {
        queueItems,
        canWrite: true,
        canSend: true,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("待执行消息队列");
    expect(wrapper.text()).toContain("3");
    expect(wrapper.text()).toContain("#1 等待自动执行");
    expect(wrapper.text()).toContain("· 当前轮次完成后自动发送");
    expect(wrapper.text()).toContain("#2 排队等待中");
    expect(wrapper.text()).toContain("#3 排队等待中");
    expect(wrapper.text()).toContain("第一条待执行指令");
    expect(wrapper.text()).toContain("第二条排队指令");

    // Click Move Down on first item (index 0)
    const downBtns = wrapper.findAll("button").filter((b) => b.text().includes("下移"));
    expect(downBtns.length).toBe(2); // Item 0 and Item 1 have down buttons
    await downBtns[0].trigger("click");
    expect(wrapper.emitted("moveDown")?.[0]).toEqual([0]);

    // Click Move Up on second item (index 1)
    const upBtns = wrapper.findAll("button").filter((b) => b.text().includes("上移"));
    expect(upBtns.length).toBe(2); // Item 1 and Item 2 have up buttons
    await upBtns[0].trigger("click");
    expect(wrapper.emitted("moveUp")?.[0]).toEqual([1]);

    // Click Restore Draft on first item
    const restoreBtns = wrapper.findAll("button").filter((b) => b.text().includes("恢复草稿"));
    expect(restoreBtns.length).toBe(3);
    await restoreBtns[0].trigger("click");
    expect(wrapper.emitted("restoreDraft")?.[0]).toEqual(["第一条待执行指令", "q-1"]);

    // Click Delete on first item
    const deleteBtns = wrapper.findAll("button").filter((b) => b.text().includes("删除"));
    expect(deleteBtns.length).toBe(3);
    await deleteBtns[0].trigger("click");
    expect(wrapper.emitted("removeItem")?.[0]).toEqual(["q-1"]);

    // Click Clear Queue
    const clearBtn = wrapper.findAll("button").find((b) => b.text().includes("清空队列"));
    expect(clearBtn).toBeDefined();
    await clearBtn?.trigger("click");
    expect(wrapper.emitted("clearQueue")).toBeDefined();
  });

  it("renders pure waiting status for queued items", () => {
    const queueItems = [
      { id: "q-1", content: "第一条待执行指令", createdAt: 1000 },
      { id: "q-2", content: "第二条等待中指令", createdAt: 2000 },
    ];

    const wrapper = mount(QueuedMessagesBanner, {
      props: {
        queueItems,
        canWrite: true,
        canSend: true,
      },
      global: {
        stubs: {
          BaseIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain("#1 等待自动执行");
    expect(wrapper.text()).toContain("· 当前轮次完成后自动发送");
    expect(wrapper.text()).toContain("#2 排队等待中");
    expect(wrapper.text()).toContain("· 顺延等待处理");
  });
});

