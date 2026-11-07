import { beforeEach, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { ref } from "vue";
import { useChatActions } from "./useChatActions";
import type { useChatSession } from "./useChatSession";
import type { ChatCheckpoint } from "@/services/threads/session.service";

beforeEach(() => setActivePinia(createPinia()));

function setup() {
  const fork = vi.fn().mockResolvedValue(true);
  const service = { history: vi.fn(), state: vi.fn() };
  const actions = useChatActions({
    projectId: "project",
    displayedMessages: () => [],
    messageMetadata: () => ({}),
    recursionLimit: ref(100),
    session: {
      threadId: ref("thread"),
      canSend: ref(true),
      service,
      fork,
    } as unknown as ReturnType<typeof useChatSession>,
  });
  return { actions, fork, service };
}
function state(id: string, parent: string | undefined, contains = true) {
  return {
    checkpoint: { checkpoint_id: id },
    parent_checkpoint: parent ? { checkpoint_id: parent } : null,
    values: {
      messages: contains ? [{ id: "user", type: "human", content: "old" }] : [],
    },
  } as ChatCheckpoint;
}

it("uses the parent before the edited message on the current lineage", () => {
  const { actions } = setup();
  actions.history.value = [
    state("head", "input"),
    state("sibling", "other", false),
    state("input", "before"),
    state("before", undefined, false),
  ];
  expect(actions.findParentCheckpointForMessage("user")?.checkpoint_id).toBe(
    "before",
  );
});

it("does not confuse equal text from an earlier turn with the edited message ID", () => {
  const { actions } = setup();
  const previous = state("before", undefined, false);
  previous.values.messages = [
    { id: "different", type: "human", content: "old" },
  ];
  actions.history.value = [state("head", "before"), previous];
  expect(actions.findParentCheckpointForMessage("user")?.checkpoint_id).toBe(
    "before",
  );
});

it("waits for on-demand history before allowing edited submission", async () => {
  const { actions, fork, service } = setup();
  let finish!: (rows: ChatCheckpoint[]) => void;
  service.history.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const loading = actions.edit("user", "old");
  actions.editDraft.value = "new";
  await actions.submitEditedBranch();
  expect(fork).not.toHaveBeenCalled();
  finish([state("head", "before"), state("before", undefined, false)]);
  await loading;
  await actions.submitEditedBranch();
  expect(fork).toHaveBeenCalledWith({ checkpoint_id: "before" }, "new", 100);
});
