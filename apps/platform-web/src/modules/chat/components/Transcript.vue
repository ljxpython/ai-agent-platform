<script setup lang="ts">
import { computed, ref } from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import { buildTranscript, type ToolItem } from "../transcript";
import MessageContent from "./MessageContent.vue";
import ToolResult from "./ToolResult.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  messages: readonly BaseMessage[];
  calls: readonly AssembledToolCall[];
  running: boolean;
  namespace?: readonly string[];
  canEdit?: boolean;
}>();
const emit = defineEmits<{
  inspect: [tool: ToolItem];
  edit: [id: string, text: string];
}>();
const turns = computed(() =>
  buildTranscript(props.messages, props.calls, props.running, props.namespace),
);
const copyError = ref("");
const expanded = ref<Record<string, boolean>>({});
function workOpen(key: string) {
  return (
    expanded.value[key] ??
    (props.running && turns.value[turns.value.length - 1]?.key === key)
  );
}
async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    copyError.value = "";
  } catch {
    copyError.value = "复制失败，请手动选择文本复制";
  }
}
</script>

<template>
  <div
    class="space-y-8"
    data-testid="transcript"
  >
    <p
      v-if="copyError"
      role="alert"
      class="text-xs text-red-600"
    >
      {{ copyError }}
    </p>
    <article
      v-for="turn in turns"
      :key="turn.key"
      v-memo="[JSON.stringify(turn), workOpen(turn.key), canEdit]"
      class="min-w-0 space-y-4"
    >
      <div
        v-if="turn.user"
        class="pw-chat-turn items-end"
      >
        <div class="pw-chat-turn-heading self-end">
          你
        </div>
        <div class="w-auto max-w-[90%] self-end rounded-2xl rounded-tr-sm border border-primary-200 bg-primary-50/90 px-5 py-3.5 text-primary-950 shadow-sm dark:border-primary-900/50 dark:bg-primary-950/30 dark:text-primary-100">
          <MessageContent :blocks="turn.user.blocks" />
        </div>
        <button
          v-if="canEdit && turn.user.id"
          type="button"
          class="pw-table-tool-button h-8 rounded-lg px-3 text-xs"
          @click="
            emit(
              'edit',
              turn.user.id,
              turn.user.blocks
                .filter((b) => b.kind === 'text')
                .map((b) => b.text)
                .join('\n'),
            )
          "
        >
          编辑并创建分支
        </button>
      </div>
      <div
        v-if="turn.work.length || turn.answer.length"
        class="pw-chat-turn-heading"
      >
        <span class="pw-chat-agent-mark"><BaseIcon
          name="sparkle"
          class="h-4 w-4"
        /></span>
        <span class="font-semibold text-gray-900 dark:text-white">Agent</span>
      </div>
      <div
        v-if="turn.work.length || turn.answer.length"
        class="w-full max-w-[780px] space-y-4 self-start rounded-2xl border border-gray-200/90 bg-white p-5 shadow-sm dark:border-dark-800 dark:bg-dark-900"
      >
        <button
          v-if="turn.work.length"
          type="button"
          class="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-900 dark:hover:text-white"
          :aria-expanded="workOpen(turn.key)"
          @click="expanded[turn.key] = !workOpen(turn.key)"
        >
          <span aria-hidden="true">{{ workOpen(turn.key) ? "▾" : "▸" }}</span>
          工作过程 · {{ turn.work.length }} 项
        </button>
        <div
          v-for="item in [...turn.work, ...turn.answer]"
          v-show="!turn.work.includes(item) || workOpen(turn.key)"
          :key="item.key"
          class="pw-chat-agent-message min-w-0 space-y-3 text-sm leading-7"
        >
          <MessageContent :blocks="item.blocks" />
          <ToolResult
            v-for="tool in item.tools"
            :key="tool.key"
            :tool="tool"
            @inspect="emit('inspect', $event)"
          />
        </div>
      </div>
      <button
        v-if="turn.answer.length"
        type="button"
        class="pw-table-tool-button h-8 w-fit rounded-lg px-3 text-xs"
        @click="
          copy(
            [...turn.work, ...turn.answer]
              .flatMap((item) =>
                item.blocks
                  .filter((block) => block.kind === 'text')
                  .map((block) => block.text),
              )
              .join('\n\n'),
          )
        "
      >
        复制
      </button>
    </article>
    <div
      v-if="running"
      class="pw-chat-live-step"
      role="status"
    >
      <span class="pw-chat-live-dot animate-pulse" />Agent 正在处理你的消息…
    </div>
  </div>
</template>
