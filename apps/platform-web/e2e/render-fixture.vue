<script setup lang="ts">
import { nextTick, ref, shallowRef } from "vue";
import { AIMessage, HumanMessage, ToolMessage } from "@langchain/core/messages";
import Transcript from "../src/modules/chat/components/Transcript.vue";
import MessageContent from "../src/modules/chat/components/MessageContent.vue";
import BaseDialog from "../src/components/base/BaseDialog.vue";
import { contentItems } from "../src/modules/chat/transcript";

const draft = ref("");
const dialog = ref(false);
const messages = shallowRef([
  new HumanMessage({ id: "human", content: "显示全部内容" }),
  new AIMessage({ id: "work", content: "工具前正文", tool_calls: [
    { id: "edit", name: "edit_file", args: { old_string: "old", new_string: "new", file_path: "/demo.txt" } },
    { id: "exec", name: "execute", args: { command: "false" } },
    { id: "unknown", name: "unrecognized_tool", args: {} },
  ] }),
  new ToolMessage({ tool_call_id: "exec", content: JSON.stringify({ exit_code: 7, output: "failed", truncated: true }), status: "error" }),
  new ToolMessage({ tool_call_id: "edit", content: "rejected", status: "error" }),
  new ToolMessage({ tool_call_id: "unknown", content: "unknown tool result" }),
  new AIMessage({ id: "answer", content: [
    { type: "text", text: '工具后正文\n<script>window.xss=1<\/script>\n[x](javascript:alert(1))\n![x](data:image/svg+xml;base64,AAAA)\n```js\nconst value = "safe";' },
    { type: "reasoning", reasoning: "公开推理说明" },
  ] }),
]);
const artifact = contentItems([
  { type: "code", language: "html", code: "<script>window.xss=2<\/script>" },
  { type: "document", content: "文档产物可读" },
  { type: "markdown", content: "**Markdown 产物可读**" },
  { type: "file", filename: "未公开下载文件" },
], "artifact");
const longContent = contentItems("长输出 ".repeat(10000), "long");
const setLong = async () => {
  messages.value = Array.from({ length: 500 }, (_, i) => [
    new HumanMessage({ id: `h${i}`, content: `问题 ${i}` }),
    new AIMessage({ id: `a${i}`, content: `回答 ${i}`, ...(i < 200 ? { tool_calls: [{ id: `t${i}`, name: "read_file", args: { path: `/${i}` } }] } : {}) }),
  ]).flat();
  await nextTick();
};
Object.assign(window, {
  renderFixture: {
    setLong,
    async tick(i: number) {
      messages.value = [...messages.value.slice(0, -1), new AIMessage({ id: "a499", content: `stream ${i}` })];
      await nextTick();
    },
  },
});
</script>
<template>
  <main class="mx-auto max-w-4xl space-y-4 p-4 text-gray-900 dark:bg-dark-900 dark:text-white">
    <label>输入测试<input v-model="draft" class="pw-input"></label>
    <button @click="dialog = true">打开测试弹窗</button>
    <Transcript :messages="messages" :calls="[]" :running="true" />
    <MessageContent :blocks="artifact" />
    <MessageContent :blocks="longContent" />
    <BaseDialog :show="dialog" title="测试弹窗" @close="dialog = false"><input aria-label="弹窗输入"><button>末尾按钮</button></BaseDialog>
  </main>
</template>
