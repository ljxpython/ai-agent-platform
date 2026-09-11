<script setup lang="ts">
import { useToolCalls, type AnyStream } from "@langchain/vue";
import { useTranscriptMessages } from "../composables/useTranscriptMessages";
import Transcript from "./Transcript.vue";
import type { ToolItem } from "../transcript";

const props = defineProps<{
  stream: AnyStream;
  namespace: readonly string[];
  running: boolean;
}>();
defineEmits<{ inspect: [tool: ToolItem] }>();
const messages = useTranscriptMessages(props.stream, props.namespace);
const calls = useToolCalls(props.stream, () => ({
  namespace: props.namespace,
}));
</script>

<template>
  <Transcript
    v-if="messages.length || calls.length"
    :messages="messages"
    :calls="calls"
    :running="running"
    :namespace="namespace"
    @inspect="$emit('inspect', $event)"
  />
  <p
    v-else
    class="text-xs text-gray-500"
  >
    {{
      running
        ? "等待此子任务的公开内容"
        : "没有保存可回放的过程，请查看委派工具的最终结果"
    }}
  </p>
</template>
