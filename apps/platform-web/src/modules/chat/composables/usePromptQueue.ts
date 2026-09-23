import { ref, watch, type Ref, type ComputedRef } from "vue";

export interface QueuedPromptItem {
  id: string;
  content: unknown;
  createdAt: number;
}

export function usePromptQueue(storageKeyRef?: Ref<string> | ComputedRef<string>) {
  const queue = ref<QueuedPromptItem[]>([]);

  // 从本地存储还原
  function loadFromStorage() {
    if (!storageKeyRef?.value || typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(storageKeyRef.value);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          queue.value = parsed.filter(
            (item) => item && typeof item.id === "string" && item.content != null,
          );
        }
      }
    } catch {
      // 容错忽略格式异常
    }
  }

  // 持久化到本地存储
  function saveToStorage() {
    if (!storageKeyRef?.value || typeof window === "undefined") return;
    try {
      if (queue.value.length === 0) {
        localStorage.removeItem(storageKeyRef.value);
      } else {
        localStorage.setItem(storageKeyRef.value, JSON.stringify(queue.value));
      }
    } catch {
      // 容错
    }
  }

  if (storageKeyRef) {
    watch(
      storageKeyRef,
      () => {
        loadFromStorage();
      },
      { immediate: true },
    );

    watch(
      queue,
      () => {
        saveToStorage();
      },
      { deep: true },
    );
  }

  function enqueue(content: unknown): QueuedPromptItem {
    const item: QueuedPromptItem = {
      id: crypto.randomUUID(),
      content: JSON.parse(JSON.stringify(content)),
      createdAt: Date.now(),
    };
    queue.value.push(item);
    saveToStorage();
    return item;
  }

  function dequeue(): QueuedPromptItem | undefined {
    const item = queue.value.shift();
    if (item) saveToStorage();
    return item;
  }

  function remove(id: string): boolean {
    const idx = queue.value.findIndex((item) => item.id === id);
    if (idx === -1) return false;
    queue.value.splice(idx, 1);
    saveToStorage();
    return true;
  }

  function moveUp(index: number): boolean {
    if (index <= 0 || index >= queue.value.length) return false;
    const item = queue.value[index];
    queue.value.splice(index, 1);
    queue.value.splice(index - 1, 0, item);
    saveToStorage();
    return true;
  }

  function moveDown(index: number): boolean {
    if (index < 0 || index >= queue.value.length - 1) return false;
    const item = queue.value[index];
    queue.value.splice(index, 1);
    queue.value.splice(index + 1, 0, item);
    saveToStorage();
    return true;
  }

  function clear(): void {
    queue.value = [];
    saveToStorage();
  }

  return {
    queue,
    enqueue,
    dequeue,
    remove,
    moveUp,
    moveDown,
    clear,
  };
}
