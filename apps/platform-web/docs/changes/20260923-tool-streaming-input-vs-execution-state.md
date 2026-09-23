# 工具卡片区分「正在生成参数」与「执行中」状态优化

## 背景与问题
当大模型通过流式输出（`tool_call_chunks`）构造超长工具入参（例如 `write_file` 写入 2 万字以上的 Markdown 报告或代码文件）时，工具卡片从第一个 chunk 到达起即显示 `执行中`，持续数分钟后才真正进入 `tools` 节点执行（本地磁盘落盘仅耗时 1~2ms）。这导致用户误以为工具执行本身卡死。

## 改动内容
1. **Transcript 流式入参状态识别（`src/modules/chat/transcript.ts`）**：
   - 在 `ToolItem` 新增 `streamingInput?: boolean` 与 `streamingChars?: number` 字段。
   - 在 `buildTranscript` 中，当会话处于运行态（`running === true`）且末尾 `AIMessage` 尚未产出结束标记（无 `finish_reason` / `stop_reason` / `usage_metadata`）时，将其未完成的 `tool_calls` 标记为 `streamingInput: true`，并实时计算已流式生成的参数字符数（优先统计 `write_file.content`、`edit_file.new_string`，否则统计 JSON 序列化长度）。
2. **ToolResult 卡片状态徽章与实时内容预览（`src/modules/chat/components/ToolResult.vue`）**：
   - 当 `streamingInput === true` 时，状态胶囊显示靛蓝色呼吸态 **`正在生成参数 · 已生成 X.Xk 字符`**（满 1000 字符按 `k` 格式化）。
   - 当模型输出完毕（`finish_reason: "tool_calls"`）、真正进入工具执行阶段时，状态胶囊无缝切换为蓝色 **`执行中`**。
   - 针对 `write_file` 工具，在 `streamingInput` 阶段展开卡片时提供 **`正在流式生成写入内容 (N 字符)`** 实时预览面板。

## 涉及文件
- `apps/platform-web/src/modules/chat/transcript.ts`
- `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- `apps/platform-web/src/modules/chat/transcript.test.ts`
- `apps/platform-web/src/modules/chat/components/ToolResult.spec.ts`
