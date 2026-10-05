<script setup lang="ts">
import { Teleport, computed, defineComponent, h, ref } from "vue";
import ChatSession from "./ChatSession.vue";
import type {
  ChatSessionPool,
  PoolEntry,
} from "../composables/useChatSessionPool";

const props = defineProps<{ pool: ChatSessionPool }>();
const parked = ref<HTMLElement | null>(null);
const items = computed(() => [...props.pool.entries.values()]);

function renderEntry(entry: PoolEntry) {
  const view = entry.view.value;
  const target = view?.outlet ?? parked.value;
  if (!target) return null;
  return h(Teleport, { key: entry.instanceId, to: target }, [
    h(
      ChatSession,
      {
        ref: (instance) => {
          entry.sessionRef.value = instance as InstanceType<
            typeof ChatSession
          > | null;
        },
        projectId: entry.projectId,
        projectName: view?.projectName.value ?? "",
        graphId: entry.target.graphId,
        agentId: entry.target.agentId,
        targetName: entry.target.name,
        threadId: entry.threadId.value,
        initialThread: entry.initialThread.value,
        threadTitle: view?.threadTitle.value ?? "",
        canWrite: Boolean(entry.canWrite.value && !entry.target.disabled),
        focusMode: view?.focusMode.value ?? false,
        visible: entry.visible.value,
        onAccessRevoked: () => {
          const view = entry.view.value;
          props.pool.remove(entry);
          view?.onRevoked();
        },
        draft: entry.draft.value,
        context: entry.context.value,
        attachments: entry.attachments.value,
        recursionLimit: entry.recursionLimit.value,
        "onUpdate:draft": (value: string) => {
          entry.draft.value = value;
        },
        "onUpdate:context": (value: typeof entry.context.value) => {
          entry.context.value = value;
        },
        "onUpdate:attachments": (value: typeof entry.attachments.value) => {
          entry.attachments.value = value;
        },
        "onUpdate:recursionLimit": (value: number) => {
          entry.recursionLimit.value = value;
        },
        onThread: (id: string) => {
          props.pool.bindThread(entry, id);
          const current = entry.view.value;
          if (current) current.onThread(id);
          else entry.pendingThreadRoute = id;
        },
        onForkThread: (id: string) => {
          entry.view.value?.onFork(id);
        },
        onRefresh: () => {
          const current = entry.view.value;
          if (current && entry.visible.value) {
            current.onRefresh();
          } else {
            entry.needsRefresh = true;
          }
        },
        onReconnect: () => {
          void entry.sessionRef.value?.reconnectStream();
        },
      },
      view?.slots ?? {},
    ),
  ]);
}

const SessionNodes = defineComponent({
  setup: () => () => items.value.map(renderEntry),
});
</script>

<template>
  <div ref="parked" hidden inert aria-hidden="true" />
  <SessionNodes />
</template>
