# 前端交接：工具错误反馈

## 同事接手范围

本专项主改动在 Runtime。前端继续使用正式 Chat/SDK/Transcript/ToolResult/SubtaskDetail，补安全错误摘要与验证；不新增页面、配置开关、工具执行 API 或后台状态机。

交接状态：2026-10-07 Runtime/API 实现与全部非前端验收已完成，无剩余非前端阻塞。以下样例使用已实施字段，样例 ID 为合成值；真实模型主/子图、HTTP 主/子图、五种控制、三角色重启和 Runtime 代码回退已通过。真实 ID 与证据见 [后端验证记录](implementation/03-isolated-verification.md)；前端开发、浏览器验收尚未执行。

## 前端已有能力与识别到的缺口

- `src/modules/chat/transcript.ts:buildTranscript()` 以消息顶层 `status="error"` 判定工具失败，并优先于 assembled call 的 finished。
- `src/modules/chat/components/ToolResult.vue` 原有失败标签、`result` JSON 解析及展开输出，但存在关键断层：
  1. 现有 `<p v-if="tool.status === 'error' && tool.error...">` 依赖 `tool.error`，但 SDK ToolMessage 报错时 `tool.error` 往往为 `undefined`（错误存放在 `tool.output` 中），导致折叠态红色错误条无法渲染；
  2. 现有 `result` 计算属性使用 `asObject(props.tool.output)`，当遇到 MCP Content Blocks 数组时 `asObject` 判定为数组而返回空对象 `{}`，导致图表/外部 MCP 结构化错误解析彻底失效；
  3. 缺乏非 JSON 纯文本错误的折叠态摘要提取与有界截断机制。
- `src/modules/chat/components/SubtaskDetail.vue` 使用独立 namespace 投影，不把子图工具混入父消息。
- Chat lifecycle 和连接恢复由 SDK/既有会话逻辑维护；不能用“某个工具失败”推导整个 Run 失败。

同事主要做三件事：
1. 在 `transcript.ts` 抽取纯函数 `parseToolErrorSummary`，统一处理普通 JSON、MCP 文本块数组、非 JSON 纯文本、stream 兜底错误与 Tag 徽章文案；
2. 改造 `ToolResult.vue`，保证折叠态稳定展示安全摘要及恢复建议徽章，展开态优雅展示结构化错误/代码块，消除空指针与解析盲区；
3. 补全核心单元测试（`transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts`），保证 Agent 后续回答、历史与子任务显示正常，完成浏览器联合验收。

## 消息与状态契约

### A. 可恢复的第一方错误

```json
{
  "type": "tool",
  "id": "message-demo-error-1",
  "tool_call_id": "call-demo-search-1",
  "name": "search_web",
  "status": "error",
  "content": "{\"status\":\"error\",\"code\":\"tool.invalid_input\",\"error\":\"工具输入不符合要求，请修正参数后继续。\",\"error_type\":\"ToolException\",\"name\":\"search_web\",\"recovery\":\"correct_input\",\"outcome\":\"not_started\"}"
}
```

示意消费的是 SDK 已组装的消息对象；不要把该 JSON 拼成自定义 SSE event。外层 `status` 决定工具状态。JSON 内 `error/code/recovery/outcome` 是展示信息，不能决定 Run 状态、授权或重试。

后续模型仍可回答或发起新调用：先前 call 保持失败，新 call 使用新的 ID。整轮 Run 最后可以 success，成功回答不抹掉之前失败卡。

| code | recovery / outcome | 展示含义 | Tag 徽章文案 |
| --- | --- | --- | --- |
| tool.invalid_input | correct_input / not_started | 参数不符合要求 | 可修正参数 |
| tool.upstream_unavailable | choose_alternative / failed | 暂时无可用结果 | 可选择其他方式 |
| tool.operation_failed | choose_alternative / not_started | 已知未提交（如配置或容量问题） | 可选择其他方式 |
| tool.outcome_unknown | do_not_repeat / unknown | 终态未知，避免重复提交 | 先核对结果 |

- **Tag 徽章规范**：`recovery` 文案不硬拼入错误正文，而是作为独立的微胶囊 Tag 徽章渲染（浅红底/深红字，暗色模式对应自适应配色），对标平台 control-plane 视觉规范。
- **生图/部署 unknown 告警分层**：当 `outcome === "unknown"` 或 `result.status === "unknown"` 时，折叠态摘要仅展示简明错误说明与“先核对结果”Tag 徽章；展开态继续保留现有的专用黄色对账告警框（含 `task_id` 和防重复点击告警），层次清晰，不重复堆砌文案。

图表错误经 MCP adapter 返回内容块，文本块里的 text 才是上述 JSON：

```json
[{"type":"text","text":"{\"status\":\"error\",\"code\":\"tool.invalid_input\",\"error\":\"工具输入不符合要求，请修正参数后继续。\",\"error_type\":\"ToolException\",\"name\":\"generate_bar_chart\",\"recovery\":\"correct_input\",\"outcome\":\"not_started\"}"}]
```

解析器必须安全支持：若 `output` 为数组，自动寻找首个 `type === "text"` 的 text 字符串进行 JSON 解析；若解析成功且符合结构化错误形状，提取其摘要。不要拼接图片块做 JSON 解析，普通 MCP 文本/图片/artifact 保留。

### B. 历史字符串与官方错误结果

```json
{
  "type": "tool",
  "tool_call_id": "call-demo-read-1",
  "name": "read_file",
  "status": "error",
  "content": "Error: file not found"
}
```

对于非 JSON 纯文本错误（如终端输出、Python 原始报错、历史字符串）：
- **折叠态摘要**：短文本直接作为摘要；若长度超过 100 字符，受控截取前 100 字符并追加 `…` 省略号，兼顾直观排版与信息可读性；
- **展开态展示**：借鉴 open-swe 模式，使用只读等宽代码块（`<pre>`）完整展示原始文本，保留换行与空格，支持用户划选复制；
- 不能要求所有错误都有 code，也不能因为 JSON 解析失败把 tool 改成 finished。MCP 错误可能带内容块和 artifact，当前结果展示保留。

### C. Run 失败、中断与取消

不可恢复故障可能没有新的 ToolMessage，只有运行终态、SDK error、已有 messages/interrupts。前端继续使用现有运行错误出口，不合成一条假工具结果。

原始 tools 通道 `tool-error.message` 现在固定为 `tool.execution_failed`，它只说明当前工具调用报错；它不是业务摘要，也不能决定 Run 失败。平台致命 lifecycle/Thread.error/原生任务错误的公开说明为 `runtime.execution_failed`，Run 终态仍使用 SDK 的原 status。优先显示安全 ToolMessage 中的中文摘要；缺少结构化摘要时沿用已有通用失败提示。

| 输入事实 | 工具展示 | Run/用户操作 |
| --- | --- | --- |
| error ToolMessage + Run 仍运行 | 当前工具失败并显示摘要 | 保留正在处理，等待后续模型输出 |
| error ToolMessage + 最终回答 | 保留失败工具 | 正常呈现回答与完成态 |
| GraphInterrupt/审批 requests | 等待审批/补充信息 | 原 resume 流程，不显示程序失败 |
| 用户取消 | 已有结果保留，无结果调用按原 incomplete 规则 | 不自动重发或恢复审批 |
| workspace/未知致命错误 | 依 SDK/消息事实，允许未完成工具 | 原 Run 失败提示；保留对话和文件入口 |
| SSE 断连 | 保留投影 | 原重连/Run 查询，不伪造工具失败 |
| 生成/发布 unknown | 保留任务凭据与原提醒 | 对账；不增加直接重试按钮 |

## 逐文件改动建议

1. `src/modules/chat/transcript.ts`：
   - 导出纯函数 `parseToolErrorSummary(output: unknown, streamError?: string): ToolErrorInfo`：
     ```typescript
     export interface ToolErrorInfo {
       summary: string;
       recoveryHint?: string;
       rawJson?: string;
       isStructured: boolean;
     }
     ```
   - 负责识别直接 JSON 字符串、MCP 文本块数组中的 JSON、非 JSON 纯文本（超 100 字符受控截断加 `…`）、stream 兜底（`tool.execution_failed`）以及恢复建议 Tag 映射；
   - 保持现有顶层 `status="error"` 优先规则，不为了摘要污染底层 ToolItem 的原始状态。
2. `src/modules/chat/components/ToolResult.vue`：
   - 引入 `parseToolErrorSummary`，计算出统一的 `errorInfo`；
   - **折叠态修复**：只要 `tool.status === 'error'`，无论 `tool.error` 是否存在均渲染错误摘要条（红色警告图标 + `errorInfo.summary` + 可选 `errorInfo.recoveryHint` 微胶囊 Tag 徽章）；彻底修复 `v-if="tool.status === 'error' && tool.error..."` 在 `tool.error` 为空时不渲染的 Bug；
   - **展开态优化**：若为结构化错误，优雅展示格式化 JSON 代码块，避免把原生单行 JSON 粗暴丢进 `MessageContent` 导致排版混乱；
   - 与现有 `unknown` 黄色对账告警框良好协同，不重复堆砌冲突提示；不增加自动重试按钮。
3. `src/modules/chat/components/SubtaskDetail.vue`：
   - 复用修复后的 `ToolResult`，保持 scoped ID 和独立 namespace 投影，验证子智能体工具失败后子图正常推理与展示。
4. 测试与验收策略：
   - 优先筑牢核心单元测试门禁：全面补齐 `transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts`；
   - 静态门禁必须 100% 通过（lint、typecheck、build）。

## 请求边界

没有新 endpoint 或必需前端参数。继续走 Platform API，携带既有项目上下文，禁止直连 Runtime 或把错误策略放入 context/configurable。

- 已有 Run 创建/恢复、state/history、标准 Run SSE、Protocol 事件通道继续使用现有 service/SDK。
- 工具失败后不调用 `runs.create` 复刻上一轮，不重用新幂等键重发原用户输入。
- 审批使用真实 interrupt ID 和既有 decisions，不能因错误自动 approve。
- 403 等 HTTP 错误走原作用域权限规则；工具 payload 里的 code/status 不触发登出或项目撤权。
- 不新增每工具 toast；已有失败工具卡和必要的 Run 错误反馈已经覆盖用户路径。

## 展示与可访问性

遵循 frontend-development-playbook、control-plane-page-standard 和 frontend-visual-baseline-standard。保持当前 Chat 壳层、密度与 BaseIcon；错误长文本可以换行，详情区域可滚动，错误不抢焦点、不强制滚底。浅/深主题结构一致。

- 恢复建议 `recovery` 渲染为微胶囊 Tag 徽章（`bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300`，字号 `text-[10px]`）；
- 复用现有按钮和图标，不增加“重试工具”按钮。错误文字通过 Vue 文本/既有安全 MessageContent 渲染，不能用 v-html 执行返回内容。

## 同事验收清单

| ID | 场景 | 必须满足 |
| --- | --- | --- |
| F01 | structured error 后模型继续 | 工具显示失败/安全摘要及 Tag 徽章，Run 仍可运行，最终答复可见 |
| F02 | assembled=finished，ToolMessage=error | 顶层消息优先，实时/历史均失败，折叠条稳定渲染错误摘要，不闪成成功 |
| F03 | 历史纯文本、非 JSON、MCP 文本块数组、未知字段 | MCP 数组正确解包，非 JSON 短文本直显，超 100 字符受控截断，展开态可读代码块 |
| F04 | 子图错误后子模型继续 | 子任务详情内工具卡正确显示错误摘要，父级不出现重复工具卡或错误 scope |
| F05 | 审批/澄清/取消 | 中断不当异常；取消不触发自动重试 |
| F06 | workspace 致命错误与生成/发布 unknown | 折叠态简明提示与 Tag，展开态保留原有黄色对账告警框，不诱导重复提交 |
| F07 | 切 Thread、刷新历史、断流重连、账号/项目切换 | 错误状态一致且作用域隔离，迟到消息不污染其他 Thread |
| F08 | 390x844、1024x768、1440x900，浅/深主题 | 长错误不遮挡正文/输入框；展开、键盘与焦点可用 |

在 `apps/platform-web` 目录执行验证门禁：

```bash
pnpm test:run src/modules/chat/transcript.test.ts src/modules/chat/components/ToolResult.spec.ts src/modules/chat/components/SubtaskDetail.spec.ts
pnpm lint
pnpm typecheck
pnpm build
```

实际跨服务浏览器验收需验证完整 Run/SSE/历史，条件见 verification.md。

## 联调交付物

Runtime/后端交付：已批准的字段/错误映射、可恢复/致命/HITL/unknown 的实际消息样本、实际 Run 终态、同一测试 Thread 的 live/state/history 及 scoped 子图样本、已执行用例与缺失项。

前端同事交付：改动文件/版本、F01-F08 结果、三尺寸截图、Vitest/lint/typecheck/build 输出、真实链路录屏或消息/事件证据、未完成项与具体原因。

交付回执回填 tasks.md:T08。前端可以先用合成数据开发，但本专项不会据此标记完整 Final 通过。
