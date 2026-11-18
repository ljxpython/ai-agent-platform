import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AssistantChatView from "./AssistantChatView.vue";
import AssistantComposer from "./AssistantComposer.vue";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";

const mock = vi.hoisted(() => ({ session: null as any }));
vi.mock("../composables/usePlatformAssistantSession", () => ({
  usePlatformAssistantSession: () => mock.session,
}));
vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({ userAvatar: "" }) }));

describe("助手发送诊断", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    mock.session = {
      messages: ref([]),
      threadId: ref(null),
      turnStatus: ref("idle"),
      errorBanner: ref(null),
      pendingReview: ref(null),
      startNewSession: vi.fn(),
      sendMessage: vi.fn(),
      evidenceLookup: {
        isEvidenceDrawerOpen: ref(false),
        activeEvidence: ref(null),
        evidenceMap: ref(new Map()),
      },
    };
  });
  it("会话已因撤权清空时保留权限提示，不重复重置", async () => {
    const store = usePlatformAssistantStore();
    store.activeThreadId = "old-thread";
    mock.session.threadId.value = "old-thread";
    mock.session.startNewSession.mockImplementation(() => {
      mock.session.errorBanner.value = null;
    });
    const wrapper = mount(AssistantChatView, {
      global: {
        stubs: {
          AssistantComposer: true,
          AssistantContextPill: true,
          EvidenceDetailDrawer: true,
          BaseIcon: true,
        },
      },
    });
    mock.session.threadId.value = null;
    mock.session.errorBanner.value =
      "此会话或资料的读取权限已变更，请新建会话。";
    store.newSession();
    await flushPromises();
    expect(mock.session.startNewSession).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("读取权限已变更");
  });
  it.each(["error", "idle"])(
    "发送结果为 %s 时按结果保留或清除原诊断",
    async (status) => {
      const store = usePlatformAssistantStore();
      store.attachedContext = { title: "错误", diagnosticMarkdown: "已有诊断" };
      mock.session.sendMessage.mockImplementation(async () => {
        mock.session.turnStatus.value = status;
      });
      const wrapper = mount(AssistantChatView, {
        global: {
          stubs: {
            AssistantComposer: {
              template: "<button @click=\"$emit('send','排查')\">发送</button>",
            },
            AssistantContextPill: true,
            EvidenceDetailDrawer: true,
            BaseIcon: true,
          },
        },
      });
      wrapper.findComponent(AssistantComposer).vm.$emit("send", "排查");
      await flushPromises();
      expect(mock.session.sendMessage).toHaveBeenCalled();
      expect(store.attachedContext !== null).toBe(status === "error");
    },
  );
});
