# open-swe 源码对照与同事方案辨析

## 取证范围

2026-10-06 只读核对用户指定的外部 open-swe 工作目录。下文 `O/` 表示该目录，`R/` 表示 `apps/runtime-service/`，`W/` 表示 `apps/platform-web/`，`A/` 表示 `apps/platform-api/`；不把参考源码作为构建依赖。

- 本项目读取时 HEAD：`424ff90e4f9a5c06c32c17f84a2cdaed73b65ef6`，初始工作树干净。
- open-swe HEAD：`ad417d64`。参考工作树包含大量本地改动和未解决合并冲突，HEAD 不能代表本次所读源码；未修改、启动或测试该项目。
- `O/agent/middleware/tool_error_handler.py` SHA256：`dbbb1a9aa84733e9f76be8ad70a5246e4a179157dcb50ee6d1c4f16a8bfce5e7`。
- `O/agent/server.py` SHA256：`2e18fb2817e10bb722eb60cf6e43b193b4089bce5c8de0bc32f2439d368903cd`。
- 本项目 `uv.lock`：`langchain==1.3.17`、`langgraph==1.2.11`、`langgraph-prebuilt==1.1.0`、`deepagents==0.7.8`、`langchain-mcp-adapters==0.3.2`。
- 只读测试所用已有虚拟环境的上述版本与锁文件一致。没有为了参考 open-swe 升级依赖。
- open-swe 的锁文件文本含 `langchain==1.3.18`、`deepagents==0.7.13`，且锁文件处于冲突状态；不能作为可安装或已验证环境的证据。

## open-swe 实际怎么做

### 1. 运行时负责错误转译

`O/agent/middleware/tool_error_handler.py` 的 `ToolErrorMiddleware.awrap_tool_call()` 包住下游 handler，实际分三条路径：

| 路径 | 判断依据 | 输出/后果 |
| --- | --- | --- |
| 瞬时 Sandbox 拒绝 | `is_transient_sandbox_error()`，识别 SDK `SandboxRetryableConnectionError` | `ToolMessage(status="error")`，`recovery="sandbox_transient"`；SDK 语义保证命令未开始 |
| 其余普通异常 | 广泛捕获 `Exception`，且不是 Sandbox 不可达 | JSON `status/error/error_type/name`，让模型看到失败 |
| Sandbox 不可达 | `SandboxConnectionError` 排除 server reload，或 Sandbox 本身的 `ResourceNotFoundError` | 通知用户后 re-raise；停止这一轮运行 |

普通 JSON 的 `error` 是 `str(exc)`；瞬时错误的 `previous_error` 也带原异常。日志还输出 `request=%r`。这是参考代码的实际行为，不是适合直接迁入多租户平台的安全契约。

`O/agent/middleware/trace.py` 的 `OpenSWEMiddleware` 使用 `TracePolicy(process_inputs=omit_payload)` 控制 Middleware trace 输入，但不能据此声称普通日志或错误消息已经脱敏。

### 2. 重试是另一个机制

- `O/agent/server.py` 主 Agent 显式装配 `ToolErrorMiddleware`，其内层有仅对 `task` 生效的 `ToolRetryMiddleware(max_retries=2, ...)`。
- `O/agent/middleware/task_retry.py` 根据部分 HTTP 状态/异常名判断子任务重试，`task_on_failure()` 区分能返回模型的模型请求错误与需继续抛出的错误。
- `O/agent/sandboxes/retry.py` 的 `retry_transient_sandbox_errors()` 最多 4 次尝试，带退避和抖动，前提是 SDK 证明 execute frame 没有发出。
- ToolError 返回消息本身不会重新执行 handler。LLM 后续发起新 tool call 是另一件事，仍需调用预算。

这些策略有远端 Sandbox SDK、coding task 和供应商异常的特定前提。本平台不能因为异常名叫 `ConnectionError` 就认定“没有执行、可以重试”。

### 3. 主/子 Agent 并非自动共享策略

`O/agent/server.py` 的 `_subagent_middleware()` 显式配置独立子图的 guards 与模型可靠性组件，并没有装配主 Agent 的 `ToolErrorMiddleware`。父层 `task` 容错处理的是子任务整体抛出的异常，不能证明子 Agent 内部工具失败后仍能自行继续推理。

本项目应在生产 researcher 子图内部配置工具错误策略，而不是只在父层把 `task` 异常压成普通工具结果。

### 4. 用户通知有明显业务属性

`O/agent/middleware/sandbox_circuit_breaker.py` 实际提供通知辅助函数，按 Slack、Linear、GitHub 来源发消息。不能只看文件名就认定它实现了通用的熔断状态机。

可借鉴原则：有状态工作区不可达时停止，不能偷偷换一个空 Sandbox，造成“恢复成功但文件丢失”。不迁入 `RunConfig.repo`、PR/Issue、Slack channel/thread、Linear issue、GitHub token 或对应通知函数。

### 5. 前端消费现有 SDK 状态

`O/ui/src/features/agents/lib/streamMessagesToUi.ts` 的 `toolStatus()`、`toolOutputText()` 消费 assembled tool call 和 ToolMessage，不承担工具执行/重试。没有发现该专项需要新增前端错误处理 API。

参考函数优先使用 assembled 的 finished/error，再回退 ToolMessage。本平台 `buildTranscript()` 已优先检查结果消息的顶层 `status`，这一点应保留。

## 当前平台差在哪里

| 能力 | 当前事实与代码 | 差距/本次处理 |
| --- | --- | --- |
| 官方统一异常处理原语 | `R/src/runtime_service/services/reference_agent/agent.py:get_agent()` 已配置官方 `ToolErrorMiddleware` | 原语已存在，不能另造同名组件 |
| 最小有界工具重试 | 同文件仅对 `read_reference` 重试 `ConnectionError`，最多再试 1 次 | 已实现示例；不据此宣称生产各工具都具备重试 |
| 选择性错误返回 | `_tool_error()` 只处理 `read_reference` 的 `ValueError/ConnectionError`，不公开原异常文本 | 已有基线，但格式是字符串；要显式排除 `RuntimeErrorBase`，它继承 `ValueError` |
| DearFlow 主 Agent 接线 | `R/src/runtime_service/services/dearflow_agent/agent.py:middleware()` 有权限检查、Model/Tool limit、模型 timeout | 未装配官方工具错误组件；需补已知错误策略，不处理所有异常 |
| researcher 接线 | 同一组合根传入 middleware；`subagents/researcher.py:researcher()` 声明只读角色 | 不能依赖父 `task` 包装；需子图内验证 |
| Showcase 模板接线 | `R/src/runtime_service/services/demo/showcase_demo/agent.py:middleware()` 与 DearFlow 相似 | 为新增 Agent 提供一致范式；主/子图一起补 |
| 第一方工具局部容错 | DearFlow 的 search/github/arxiv/media/memory/skills 等设置 `handle_tool_error=True` | 已能返回部分错误；内容与分类分散，外层 Middleware 看不到被消化的异常 |
| MCP 执行错误 | adapter 0.3.2 默认将 `isError=True` 转为错误 ToolMessage，保留内容块 | 已有，不能再包装丢失图片/结构块；transport/session/conversion 异常是另一类 |
| 文件系统工具 | Deep Agents 0.7.8 对 read/write/edit/execute 多条失败分支直接返回 `ToolMessage(status="error")` | 已有，正常非零退出/文件不存在不应一律变 Run 崩溃或“工作区死亡” |
| 工作区 | `R/src/runtime_service/workspace/scoped.py` 指向作用域化本地目录；execution.py 通过 Docker/本地 Backend 执行 | 无远程 Sandbox session/id，不能套用 open-swe SDK 异常 |
| 中断与流事件 | `R/src/runtime_service/patches.py` 维护既有 LangGraph interrupt 行为；普通 tool-error 仍可能携带原异常 | 保留控制流，修复已复现的错误文本流出口；回归 HITL 与取消 |
| 前端工具状态 | `W/src/modules/chat/transcript.ts:buildTranscript()` 区分 error/finished/incomplete；ToolResult/SubtaskDetail 已消费 | 无需新状态机；补结构化摘要、历史与实时对齐 |
| 平台网关 | `A/src/platform_api/modules/runtime_gateway/presentation/http.py` 处理授权、SSE、私有字段过滤 | 无需工具执行逻辑；补数据保真/脱敏回归 |
| 工具失败观测 | `R/src/runtime_service/observability/langfuse.py` 已有 `on_tool_error` 与 `tool_error` 计数 | 异常计数不等于所有已返回 error 结果；核对 `on_tool_end` 路径再按需补齐 |

锁定的 ToolNode 默认只转换 `ToolInvocationError` 等参数绑定/校验错误，其余异常通常继续抛出。`BaseTool.handle_tool_error`、MCP adapter、官方 FilesystemMiddleware 和外层 Middleware 是不同的错误出口，不能只审阅一个类就判断整条链路。

### 新发现：流事件仍可能携带原异常

对锁定版本做了离线探针：工具抛出 `ValueError("CANARY_TEST_DETAIL")`，官方 `ToolErrorMiddleware` 返回安全字符串，模型继续回答；但 `astream(..., stream_mode=["tools", "updates"], version="v3")` 仍收到：

```text
('tools', {'event': 'tool-error', 'tool_call_id': 'probe-call', 'message': 'CANARY_TEST_DETAIL'})
```

`langgraph.pregel._tools.StreamToolCallHandler._error()` 当前直接使用 `str(error)`。现有 `R/src/runtime_service/patches.py` 只对 `GraphBubbleUp` 做特殊处理。ToolMessage 已脱敏不能作为全链路安全结论。

T06 必须修复这个出口：先确认官方配置/等价修复；锁定版本没有时，在已有 `patches.py` 做稳定 code/type 清洗，保留事件配对与控制流。Runtime 原始流、平台流和浏览器均需验收。底座升级需另审，不为了容错默认升级依赖。离线证据尚未证明现役平台流或浏览器行为。

## 同事方案逐项评估

| 建议 | 结论 | 原因与替代 |
| --- | --- | --- |
| 优先补工具容错 | 采纳 | 生产 Agent 接线和错误分类确有缺口 |
| 当前没有 ToolErrorMiddleware | 修正事实 | Reference 已接入，第一方工具和 MCP 也已有局部容错 |
| 新建 `middlewares/tool_error_handler.py` 实现同名类 | 不采纳 | 官方 1.3.17 已支持 sync/async、工具过滤、GraphBubbleUp 放行和 error ToolMessage；只补小型函数 |
| 所有异常转 ToolMessage | 不采纳 | 会隐藏权限失败、程序缺陷、中断以及未知副作用；只接受明确可恢复错误 |
| JSON 输出 status/error/error_type/name | 部分采纳 | 保留这四个安全字段，增加稳定 code 和有限 recovery/outcome；error 从固定文案产生，不直接序列化异常 |
| 放全局 Middleware 最外层 | 修正位置 | 权限/契约/预算 guards 保持在错误处理外；只在工具执行容错层最外，若有 Retry 则 Error(Retry(tool)) |
| `.runtime/` workspace 不可达时 re-raise | 采纳原则，重做判定 | 目录级故障与 Docker 启动故障需确切证据；单文件不存在、命令退出非零、超时均不证明工作区不可达 |
| 让 LLM 自动重试 | 修正表述 | 只是反馈给模型；不承诺重试或成功，不自动重复 task、execute、发布或计费动作 |

## 本次借鉴及不迁入的内容

借鉴：错误结果对模型可见、显式 Middleware 顺序、主/子图独立验证、按实际执行阶段判断重试安全性、保留工作区和未知副作用。

不迁入：OpenSWEMiddleware 基类、远端 Sandbox SDK、sandbox_id/previous_error、RunConfig、Slack/Linear/GitHub 通知、PR/计划模式、coding task 重试 predicate、动态工具框架和额外管理页面。

## 官方核对依据

2026-10-06 已查询 `langchain-docs` 与 `langchain-reference` MCP，并以本地锁定版本源码交叉核对。

- [Tool error Middleware API](https://reference.langchain.com/python/langchain/agents/middleware/tool_error/ToolErrorMiddleware)：`on_error` 返回内容时生成 error ToolMessage；返回 `None` 时继续传播；控制流信号不传给回调。
- [工具错误处理](https://docs.langchain.com/oss/python/langchain/tools#error-handling)
- [自定义 Middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [v1 迁移中的错误边界](https://docs.langchain.com/oss/python/migrate/langchain-v1#handling-tool-errors)

线上文档版本可能变化；实现必须继续以 `uv.lock`、已安装源码和真实 graph 契约测试为准。
