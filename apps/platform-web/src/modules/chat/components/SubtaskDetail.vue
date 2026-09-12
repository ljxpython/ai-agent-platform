<script setup lang="ts">
import { computed } from "vue";
import { useToolCalls, type AnyStream } from "@langchain/vue";
import { useTranscriptMessages } from "../composables/useTranscriptMessages";
import { buildTranscript, type MessageItem, type ToolItem } from "../transcript";
import ToolResult from "./ToolResult.vue";
import MessageContent from "./MessageContent.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  stream: AnyStream;
  namespace: readonly string[];
  running: boolean;
}>();

const emit = defineEmits<{ inspect: [tool: ToolItem] }>();

const messages = useTranscriptMessages(props.stream, props.namespace);
const calls = useToolCalls(props.stream, () => ({
  namespace: props.namespace,
}));

const turns = computed(() =>
  buildTranscript(messages.value, calls.value, props.running, props.namespace),
);

/** Extract the delegated prompt / instructions from the parent agent (never labeled as 'you') */
const taskDirective = computed<MessageItem | undefined>(() => {
  for (const turn of turns.value) {
    if (turn.user) return turn.user;
  }
  return undefined;
});

/** Collect all tool execution calls performed by this subagent */
const subtaskTools = computed<ToolItem[]>(() => {
  const tools: ToolItem[] = [];
  const seen = new Set<string>();
  for (const turn of turns.value) {
    for (const item of [...turn.work, ...turn.answer]) {
      for (const t of item.tools) {
        if (!seen.has(t.id)) {
          seen.add(t.id);
          tools.push(t);
        }
      }
    }
  }
  return tools;
});

/** Collect intermediate reasoning or notes from the subagent */
const processNotes = computed<MessageItem[]>(() => {
  const notes: MessageItem[] = [];
  for (const turn of turns.value) {
    for (const item of turn.work) {
      if (item.blocks.length && !item.tools.length) {
        notes.push(item);
      }
    }
  }
  return notes;
});
</script>

<template>
  <div class="space-y-3">
    <!-- 1. Task Directive (Delegated by root agent, NOT human user) -->
    <div
      v-if="taskDirective"
      class="rounded-lg border border-primary-100 bg-primary-50/50 p-2.5 text-xs text-gray-700 dark:border-primary-950/60 dark:bg-primary-950/20 dark:text-dark-200"
    >
      <div class="mb-1.5 flex items-center gap-1.5 font-medium text-primary-700 dark:text-primary-400">
        <BaseIcon
          name="sparkle"
          class="h-3.5 w-3.5"
        />
        <span>主智能体指派任务</span>
      </div>
      <MessageContent :blocks="taskDirective.blocks" />
    </div>

    <!-- 2. Intermediate reasoning or notes -->
    <div
      v-if="processNotes.length"
      class="space-y-2"
    >
      <div
        v-for="note in processNotes"
        :key="note.key"
        class="text-xs leading-relaxed text-gray-600 dark:text-dark-300"
      >
        <MessageContent :blocks="note.blocks" />
      </div>
    </div>

    <!-- 3. Subagent Internal Tool Calls (Rendered neatly inside this card) -->
    <div
      v-if="subtaskTools.length"
      class="space-y-2"
    >
      <div class="flex items-center justify-between text-[11px] font-medium text-gray-500 dark:text-dark-400">
        <span>执行步骤（{{ subtaskTools.length }} 项操作）</span>
        <span
          v-if="running"
          class="flex items-center gap-1 text-primary-600 dark:text-primary-400"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-primary-500 animate-pulse" />
          运行中
        </span>
      </div>
      <div class="space-y-1.5">
        <ToolResult
          v-for="tool in subtaskTools"
          :key="tool.key"
          :tool="tool"
          :stream="stream"
          @inspect="emit('inspect', $event)"
        />
      </div>
    </div>

    <!-- 4. Empty / loading fallback -->
    <div
      v-else-if="running"
      class="flex items-center gap-2 py-1.5 text-xs text-primary-600 dark:text-primary-400"
    >
      <span class="h-2 w-2 rounded-full bg-primary-500 animate-pulse" />
      <span>子智能体正在执行只读分析...</span>
    </div>
    <p
      v-else-if="!taskDirective && !subtaskTools.length"
      class="text-xs text-gray-400 dark:text-dark-500"
    >
      暂无此子任务的内部执行步骤记录
    </p>
  </div>
</template>
