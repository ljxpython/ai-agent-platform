import { mount } from "@vue/test-utils";
import { defineComponent, h, KeepAlive, nextTick, ref } from "vue";
import { describe, expect, it, vi } from "vitest";
import { createSessionService } from "@/services/threads/session.service";
import { useThreadActivity } from "./useThreadActivity";

describe("useThreadActivity", () => {
  it("reports opening and reactivation, while cached background changes do not touch", async () => {
    const project = ref<string>();
    const thread = ref<string>();
    const visible = ref(true);
    const activity = vi.fn().mockResolvedValue({});
    const service = { ...createSessionService("project"), activity };
    const Page = defineComponent({
      setup() {
        useThreadActivity(
          () => project.value,
          () => thread.value,
          () => service,
        );
        return () => h("div");
      },
    });
    const wrapper = mount(
      defineComponent({
        setup: () => () => h(KeepAlive, () => (visible.value ? h(Page) : null)),
      }),
    );
    expect(activity).not.toHaveBeenCalled();
    project.value = "project";
    thread.value = "first";
    await nextTick();
    expect(activity).toHaveBeenCalledWith("first");
    expect(activity).toHaveBeenCalledTimes(1);
    await nextTick();
    expect(activity).toHaveBeenCalledTimes(1);
    visible.value = false;
    await nextTick();
    thread.value = "second";
    await nextTick();
    expect(activity).toHaveBeenCalledTimes(1);
    visible.value = true;
    await nextTick();
    expect(activity).toHaveBeenLastCalledWith("second");
    expect(activity).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
