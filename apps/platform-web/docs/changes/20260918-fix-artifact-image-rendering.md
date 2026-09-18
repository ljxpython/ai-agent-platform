# 修复：产物图片渲染全链路缺陷

## 背景

`present_artifacts` 工具产物统一写入 `/workspace/outputs/` 目录后，前端各层路径白名单均未同步更新，导致合法产物图片被全链路判定为非法，用户看到裂图或完全不渲染。同时存在图片原地切块机制缺失的排版问题。

## 改了什么

### 1. `src/modules/chat/transcript.ts`

- **`WORKSPACE_IMAGE_PATH_REGEX`**：正则加入 `outputs` 目录分支，覆盖 `present_artifacts` 标准产物路径。
- **原地切块（Split by Image Block）**：新增 `splitTextByImages` 内部函数，将文本中的 Markdown 图片标记 `![alt](/workspace/...)` 或裸路径在原位切成 `[前段文本] → [ThreadImage块] → [后段文本]` 有序序列，而不是追加到文本末尾。同时把图片 token 从文本中移除，防止 `markdown-it` 渲染出裂图 `<img>` 标签。
- **修复 `g` flag 全局正则 `lastIndex` 污染**：在每次 `test()` 前 reset `lastIndex`，避免循环中跨调用状态累积导致随机漏匹配。

### 2. `src/services/threads/images.service.ts`

- **`isValidImageRef` allowedPrefixes**：加入 `/workspace/outputs/`，使 `present_artifacts` 返回的 `RuntimeImageRef` 能通过校验，进入后续图片渲染流程。

### 3. `src/modules/chat/components/ToolResult.vue`

- **`runtimeImages` computed**：在查 `tool.artifact` 之后、查字符串 output 正则扫描之前，新增对结构化 `tool.output` 的 `extractRuntimeImages` 调用。`present_artifacts` 的产物是结构化对象而非字符串，此前完全被丢弃。

### 4. `src/modules/chat/components/ChatMessageList.vue`

- **fork 按钮 disabled 逻辑**：加入 `!getForkCheckpointId(displayEntry)` 判断，无有效历史快照时按钮 disabled + tooltip 显示"暂无可用历史快照"，防止用户点击后进入无效的分页回溯流程最终报错。

## 涉及文件

- `src/modules/chat/transcript.ts`
- `src/services/threads/images.service.ts`
- `src/modules/chat/components/ToolResult.vue`
- `src/modules/chat/components/ChatMessageList.vue`
- `src/modules/chat/transcript.test.ts`（更新测试预期，匹配原地切块新行为）
- `src/modules/chat/components/ChatMessageList.spec.ts`（更新 fork 按钮测试，补充 metadata）
