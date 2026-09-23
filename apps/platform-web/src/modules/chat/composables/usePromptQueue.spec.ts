import { describe, expect, it, beforeEach } from "vitest";
import { ref } from "vue";
import { usePromptQueue } from "./usePromptQueue";

describe("usePromptQueue", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("enqueues and dequeues in FIFO order", () => {
    const { queue, enqueue, dequeue } = usePromptQueue();
    expect(queue.value).toHaveLength(0);

    const item1 = enqueue("Task 1");
    const item2 = enqueue("Task 2");

    expect(queue.value).toHaveLength(2);
    expect(queue.value[0].content).toBe("Task 1");
    expect(queue.value[1].content).toBe("Task 2");

    const popped = dequeue();
    expect(popped?.id).toBe(item1.id);
    expect(queue.value).toHaveLength(1);
    expect(queue.value[0].id).toBe(item2.id);

    const popped2 = dequeue();
    expect(popped2?.id).toBe(item2.id);
    expect(queue.value).toHaveLength(0);

    expect(dequeue()).toBeUndefined();
  });

  it("removes items by ID", () => {
    const { queue, enqueue, remove } = usePromptQueue();
    const item1 = enqueue("Task 1");
    const item2 = enqueue("Task 2");
    const item3 = enqueue("Task 3");

    const removed = remove(item2.id);
    expect(removed).toBe(true);
    expect(queue.value).toHaveLength(2);
    expect(queue.value.map((i) => i.content)).toEqual(["Task 1", "Task 3"]);

    expect(remove("non-existent")).toBe(false);
  });

  it("moves items up and down safely", () => {
    const { queue, enqueue, moveUp, moveDown } = usePromptQueue();
    enqueue("Task A");
    enqueue("Task B");
    enqueue("Task C");

    // move B up -> should be [B, A, C]
    expect(moveUp(1)).toBe(true);
    expect(queue.value.map((i) => i.content)).toEqual(["Task B", "Task A", "Task C"]);

    // move first item up -> invalid
    expect(moveUp(0)).toBe(false);

    // move B down -> should be [A, B, C]
    expect(moveDown(0)).toBe(true);
    expect(queue.value.map((i) => i.content)).toEqual(["Task A", "Task B", "Task C"]);

    // move last item down -> invalid
    expect(moveDown(2)).toBe(false);
    expect(moveDown(99)).toBe(false);
  });

  it("persists to and restores from localStorage", async () => {
    const storageKey = ref("pw:test-queue:1");
    const queue1 = usePromptQueue(storageKey);
    queue1.enqueue("Persisted 1");
    queue1.enqueue("Persisted 2");

    // Check localStorage
    const raw = localStorage.getItem("pw:test-queue:1");
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw!)).toHaveLength(2);

    // Create another instance with same key
    const queue2 = usePromptQueue(storageKey);
    expect(queue2.queue.value).toHaveLength(2);
    expect(queue2.queue.value[0].content).toBe("Persisted 1");
  });
});
