import { effectScope, ref } from "vue";
import { expect, it, vi } from "vitest";
import type { ChatAttachmentBlock } from "@/utils/chat-content";
const mocks = vi.hoisted(() => ({ convert: vi.fn(), toast: vi.fn() }));
vi.mock("@/stores/ui", () => ({
  useUiStore: () => ({ pushToast: mocks.toast }),
}));
vi.mock("@/utils/chat-content", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/utils/chat-content")>()),
  fileToChatAttachmentBlock: mocks.convert,
}));
import { useChatAttachments } from "./useChatAttachments";

it("deduplicates a batch and keeps accepted draft attachments across disposal without late writes", async () => {
  const block: ChatAttachmentBlock = {
    type: "image",
    mimeType: "image/png",
    data: "eA==",
    metadata: { name: "a.png" },
  };
  const draft = ref<ChatAttachmentBlock[]>([]);
  const scope = effectScope();
  const uploads = scope.run(() => useChatAttachments(draft))!;
  mocks.convert.mockResolvedValueOnce(block);
  const file = new File(["x"], "a.png", { type: "image/png" });
  expect(await uploads.appendFiles([file, file])).toBe(1);
  expect(mocks.convert).toHaveBeenCalledTimes(1);
  let finish!: (value: ChatAttachmentBlock) => void;
  mocks.convert.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = uploads.appendFiles([
    new File(["y"], "b.png", { type: "image/png" }),
  ]);
  scope.stop();
  finish({ ...block, metadata: { name: "b.png" } });
  expect(await pending).toBe(0);
  expect(draft.value).toEqual([block]);
});
