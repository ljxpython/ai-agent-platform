# 前端错误展示与容错接入实现记录

## 改动时间
2026-10-07

## 相关任务
- Task T08：前端交接与有限展示接入

## 改动文件
- `apps/platform-web/src/modules/chat/transcript.ts`
- `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- `apps/platform-web/src/modules/chat/transcript.test.ts`
- `apps/platform-web/src/modules/chat/components/ToolResult.spec.ts`
- `apps/platform-web/src/modules/chat/components/SubtaskDetail.spec.ts`

## 具体改动

### 1. 抽取纯函数 `parseToolErrorSummary`
**位置：** `apps/platform-web/src/modules/chat/transcript.ts`

**改动内容：**
- 新增 `ToolErrorInfo` 接口：`{ summary: string; recoveryHint?: string; rawJson?: string; isStructured: boolean }`
- 新增纯函数 `parseToolErrorSummary(output: unknown, streamError?: string): ToolErrorInfo`：
  - 支持直接第一方 JSON 字符串反序列化，提取受支持的 `error` 摘要与 `recovery` 建议；
  - 支持 MCP Content Blocks 数组（`[{"type": "text", "text": "..."}]`）自动解包与 JSON 解析；
  - 支持非 JSON 纯文本（如终端 stderr、底层文件报错），长度超出 100 字符时受控截断并添加 `…` 省略号；
  - 支持 `streamError` 兜底（如将 `tool.execution_failed` 转化为中文“工具执行失败”）；
  - 将 `recovery` 映射为统一中文行动建议（`correct_input` → “可修正参数”，`choose_alternative` → “可选择其他方式”，`do_not_repeat` → “先核对结果”）。

### 2. 改造 `ToolResult.vue` 视图与展示层
**位置：** `apps/platform-web/src/modules/chat/components/ToolResult.vue`

**改动内容：**
- 引入 `parseToolErrorSummary` 计算 `errorInfo`；
- 优化 `result` 计算属性，支持从 MCP 内容块数组中反序列化 JSON，避免被 `asObject` 误判为数组返回 `{}`；
- **折叠态错误条修复：** 只要 `tool.status === 'error'` 即渲染红色错误条，彻底修复此前强依赖 `tool.error` 导致在 ToolMessage 报错时折叠条不渲染的空指针/缺失缺陷；展示警告图标、错误摘要文本以及独立的微胶囊 Tag 徽章；
- **展开态输出展示重构：** 当工具为错误状态时，若为结构化错误展示格式化只读 JSON 代码块，非结构化错误展示等宽日志块（带有 `pw-tool-error-output` 标记），避免把未经排版的原始单行 JSON 直接塞给富文本正文；
- 与原有的 `unknown` 终态黄色告警框清晰分层，避免双重冲突提示。

### 3. 子任务 `SubtaskDetail.vue` 兼容与隔离
**位置：** `apps/platform-web/src/modules/chat/components/SubtaskDetail.vue`
- 复用改造后的 `ToolResult.vue`，保持 scoped ID 与独立 namespace 投影。子智能体内部工具报错时正常传递 `status="error"` 与错误输出，不污染父级。

## 验证证据
- `apps/platform-web/src/modules/chat/transcript.test.ts`：18 passed（新增 8 项纯函数场景测试）
- `apps/platform-web/src/modules/chat/components/ToolResult.spec.ts`：10 passed（新增 4 项组件错误与徽章展示测试）
- `apps/platform-web/src/modules/chat/components/SubtaskDetail.spec.ts`：3 passed（新增 1 项子图内部工具失败传递测试）
- 3 套单测联合回归：31 passed (31)，耗时 752ms
- 静态门禁：
  - `pnpm lint`（ESLint）：0 error / 0 warning
  - `pnpm typecheck`（vue-tsc）：0 error
  - `pnpm build`（Vite 生产构建）：dist 打包成功，耗时 1.48s
