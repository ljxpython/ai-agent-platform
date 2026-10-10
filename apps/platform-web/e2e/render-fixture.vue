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
  new AIMessage({
    id: "work",
    content: "工具前正文",
    tool_calls: [
      {
        id: "edit",
        name: "edit_file",
        args: { old_string: "old", new_string: "new", file_path: "/demo.txt" },
      },
      { id: "exec", name: "execute", args: { command: "false" } },
      { id: "unknown", name: "unrecognized_tool", args: {} },
    ],
  }),
  new ToolMessage({
    tool_call_id: "exec",
    content: JSON.stringify({
      exit_code: 7,
      output: "failed",
      truncated: true,
    }),
    status: "error",
  }),
  new ToolMessage({
    tool_call_id: "edit",
    content: "rejected",
    status: "error",
  }),
  new ToolMessage({ tool_call_id: "unknown", content: "unknown tool result" }),
  new AIMessage({
    id: "answer",
    content: [
      {
        type: "text",
        text:
          "工具后正文\n<script>window.xss=1</" +
          'script>\n[x](javascript:alert(1))\n![x](data:image/svg+xml;base64,AAAA)\n```js\nconst value = "safe";',
      },
      { type: "reasoning", reasoning: "公开推理说明" },
    ],
  }),
]);
const artifact = contentItems(
  [
    {
      type: "code",
      language: "html",
      code: "<script>window.xss=2</" + "script>",
    },
    { type: "document", content: "文档产物可读" },
    { type: "markdown", content: "**Markdown 产物可读**" },
    { type: "file", filename: "未公开下载文件" },
  ],
  "artifact",
);
const longContent = contentItems("长输出 ".repeat(10000), "long");
const setLong = async () => {
  messages.value = Array.from({ length: 500 }, (_, i) => [
    new HumanMessage({ id: `h${i}`, content: `问题 ${i}` }),
    new AIMessage({
      id: `a${i}`,
      content: `回答 ${i}`,
      ...(i < 200
        ? {
            tool_calls: [
              { id: `t${i}`, name: "read_file", args: { path: `/${i}` } },
            ],
          }
        : {}),
    }),
  ]).flat();
  await nextTick();
};
Object.assign(window, {
  renderFixture: {
    setLong,
    async setReasoning() {
      messages.value = [
        new AIMessage({
          id: "qwen",
          content: "Qwen OK",
          additional_kwargs: { reasoning_content: "Qwen 思考内容" },
        }),
        new AIMessage({
          id: "deepseek",
          content: "DeepSeek OK",
          additional_kwargs: { reasoning: "DeepSeek 思考内容" },
        }),
      ];
      await nextTick();
    },
    async tick(i: number) {
      messages.value = [
        ...messages.value.slice(0, -1),
        new AIMessage({ id: "a499", content: `stream ${i}` }),
      ];
      await nextTick();
    },
    async setF04Samples() {
      messages.value = [
        new HumanMessage({
          id: "user_req",
          content: "请解析超大财报文档并汇总摘要",
        }),
        new AIMessage({
          id: "assistant_call",
          content: "正在调用 search_web 检索全网数据...",
          tool_calls: [
            {
              id: "budget-large",
              name: "search_web",
              args: { query: "2026 年行业技术发展全景图与超长统计报告" },
            },
          ],
        }),
        new ToolMessage({
          tool_call_id: "budget-large",
          content:
            "Tool result too large, the result of this tool call budget-large was saved in the filesystem at this path: /large_tool_results/3afa3b3de3c839f459926cc015a69943cfcc546bc0c130f85f723448292901b0/budget-large\n\nYou can read the result from the filesystem by using the read_file tool, but make sure to only read part of the result at a time.\n\nYou can do this by specifying an offset and limit in the read_file tool call. For example, to read the first 100 lines, you can use the read_file tool with offset=0 and limit=100.\n\nHere is a preview showing the head and tail of the result (lines of the form `... [N lines truncated] ...` indicate omitted lines in the middle of the content):\n\n1  ROW_0000 营业收入大幅增长...\n... [1490 lines truncated] ...\n1500  ROW_1499 净利润符合预期。\n",
          status: "success",
          artifact: {
            evidence: [
              {
                title: "SEC 10-K Filings 2026.pdf",
                source_url: "https://example.com/sec/10k",
                kind: "page_text",
                page: 601,
              },
            ],
          },
        }),
        new AIMessage({
          id: "assistant_read",
          content: "正在读取大结果片段进行深度分析...",
          tool_calls: [
            {
              id: "read-middle-8c677b211ee1",
              name: "read_file",
              args: {
                file_path:
                  "/large_tool_results/3afa3b3de3c839f459926cc015a69943cfcc546bc0c130f85f723448292901b0/budget-large",
                offset: 600,
                limit: 1,
              },
            },
          ],
        }),
        new ToolMessage({
          tool_call_id: "read-middle-8c677b211ee1",
          content:
            "601  F04_MIDDLE_main\n\n[Read 1 line (lines 601-601 of 1500 total). 899 lines remaining from offset 601.]",
          status: "success",
        }),
        new AIMessage({
          id: "assistant_ans",
          content:
            "已完成超大结果外置保存，中间截断预览已就绪，已按需读取第 601 行关键数据：F04_MIDDLE_main。",
        }),
      ];
      await nextTick();
    },
  },
});
</script>
<template>
  <main
    class="mx-auto max-w-4xl space-y-4 p-4 text-gray-900 dark:bg-dark-900 dark:text-white"
  >
    <label>输入测试<input v-model="draft" class="pw-input" /></label>
    <button @click="dialog = true">打开测试弹窗</button>
    <Transcript :messages="messages" :calls="[]" :running="true" />
    <MessageContent :blocks="artifact" />
    <MessageContent :blocks="longContent" />
    <BaseDialog :show="dialog" title="测试弹窗" @close="dialog = false"
      ><input aria-label="弹窗输入" /><button>末尾按钮</button></BaseDialog
    >
  </main>
</template>
