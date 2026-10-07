# 工具调用容错整体方案

## 目标与边界

同一工具调用出现预期的输入/业务/外部服务失败时，模型收到安全错误结果，可以修正输入、选择替代方法或说明限制。遇到中断、取消、权限/契约失败、工作区基础设施故障或未知程序异常时，保留对应的暂停/取消/失败语义。

2026-10-06 用户已评审批准，2026-10-07 非前端实现/验证完成，仅剩前端交付与浏览器联合 Final。采用现有 `agent.py` 显式组合根、官方 AgentMiddleware、原生 ToolMessage/Command、既有工具和 Backend，不新增 Agent 框架、配置中心或 Run 状态机。实际改动见 [实施记录](implementation/02-selective-error-handling.md) 与 [隔离验证](implementation/03-isolated-verification.md)。

验收以“主/子 Agent 能正确消费错误，致命错误仍能停止，整条链路不泄露敏感内容”为准，不以“新文件出现”或“异常数量变少”为准。

## 三层分工

| 问题 | Runtime Service | Platform API | Platform Web |
| --- | --- | --- | --- |
| 哪些错误可恢复 | 必须：工具/Backend 知道真实执行阶段，做明确分类 | 不猜测工具错误 | 不根据异常类名或字符串重试 |
| 安全错误内容 | 必须：产生消息前使用稳定 code 与固定文案 | 验证现有字段过滤；不能依靠网关处理所有字符串秘密 | 按文本渲染，错误内容不获得额外 HTML 权限 |
| 继续 Agent 推理 | 官方 ToolErrorMiddleware 与 tool-native handler | 透传消息/事件，保留 Run 事实 | 继续展示运行中与最终回答 |
| workspace 不可用 | 真实目录/进程边界判定，停止并保留数据 | 原有握手/流内失败出口 | 原有运行失败展示；不自动新建 Thread/重发 Run |
| 中断、取消、审批 | 原有 LangGraph/Deep Agents 控制流 | 原有 resume/cancel 权限与幂等 | 原有审批与 Run 生命周期 |
| 错误观测 | 复用 callback/log，区分抛出的异常与 error ToolMessage | 原有 request/trace 关联 | 工具失败与连接错误分离 |

Runtime 承担分类与执行边界。API 验证期间发现 GraphHarbor 致命 lifecycle 与 Thread.error 仍有原异常文本，已在既有 `sdk_client.py:redact_runtime_private_fields()` 增加固定公开说明；不改变 Run 状态。前端需要小范围接入与验收，由同事完成。没有新 REST endpoint、Delegation operation、数据库表或客户端错误策略配置。

## 完整调用链

```text
Platform Web: SDK 提交/消费、纯视图映射
  -> Platform API: 项目/Thread 授权、受管参数、幂等、SSE 网关
  -> GraphHarbor: Run、checkpoint、事件与终态事实
  -> services/<agent>/agent.py: 显式组装主/子图
  -> RuntimeConfigMiddleware: 可见/可执行 allowlist 复核
  -> 已有预算、scope、skills 和审批边界
  -> 官方 ToolErrorMiddleware(on_error=on_tool_error)
  -> tool-native handle_tool_error / MCP adapter / FilesystemMiddleware
  -> 实际工具或 Backend
  -> ToolMessage / Command 或向外传播的异常
  -> 模型继续推理 / graph 暂停、取消或失败
  -> 既有 SSE + 历史读取 -> Web 展示
```

tool-native handler 先处理的异常不会进入外层 `on_error`，因此第一方可恢复错误要共用格式化函数。官方文件系统/MCP 已经返回的结果不再次包装，成功结果和 `Command` 原样通过。

## 错误分类

错误策略是 `(工具名称, 异常类型, 已批准的错误码, 执行阶段)` 的组合，不是 `isinstance(exc, Exception)` 的单一判断。

| 类型 | 例子 | 模型结果/Run 行为 | 本期自动重试 |
| --- | --- | --- | --- |
| 参数 schema 错误 | 缺参数、类型错误 | 复用 ToolNode 已有错误 ToolMessage；不强制 JSON 化 | 无 |
| 第一方可修正输入 | invalid_research_query、invalid_arxiv_date_range、invalid_page_range | 安全结构化 ToolMessage，recovery=correct_input，outcome=not_started | 无；模型可修改后调用 |
| 已知业务失败 | 页面无正文、不支持的文档、供应商不可用 | error ToolMessage，固定说明；按实际失败点使用 choose_alternative/failed | 无 |
| 受控只读 MCP transport 失败 | 已授权 read-only 绑定的明确 transport/session 连接故障 | 可归入 tool.upstream_unavailable；不暴露地址；conversion/未知错误继续抛出 | 无；readOnlyHint 不是写工具重试凭据 |
| MCP `isError=True` | 外部工具返回协议错误结果 | adapter 原生 status/error 内容块；保留配对和 artifact | 无 |
| 原生 Backend 失败结果 | read_file 文件不存在、edit 无匹配、execute 非零退出 | 原生 error ToolMessage/artifact 保留；不强制结构化 | 无 |
| Runtime 授权/契约失败 | RuntimeAuthError、RuntimeResolutionError、scope/hash/快照异常 | fail-closed，模型不继续工具循环 | 无 |
| `task` 内部未知或致命异常 | 子图权限失败、程序缺陷 | 父工具包装不得将它降为普通业务错误 | 无 |
| 工作区基础设施故障 | 可信根目录无权限、空间耗尽、实际 Docker 启动失败 | 明确错误向外传播；停止当前 Run，不替换工作区 | 无 |
| 非幂等结果未知 | execute 超时、提交供应商后断线、发布/生成任务 unknown | 保留现有 unknown/退出结果；错误说明不得声称“未执行” | 无；不得提示盲重发 |
| `GraphBubbleUp` / interrupt / parent Command | HITL、子图中断 | 原有暂停/恢复/父图路由 | 无 |
| cancellation / Run deadline | 用户停止、外层 deadline | 立即传播并完成现有资源清理 | 无 |
| 未知程序异常 | RuntimeError、TypeError、AssertionError；未归类的 ValueError/ToolException | 保留内部诊断与失败，公开出口遵循既有安全契约 | 无 |

`RuntimeErrorBase` 继承 `ValueError`，必须在分类函数中优先排除整个族。仅凭 `ToolException` 也不足以放行：当前 memory/media/skills 工具中有 scope/storage 等错误，需根据工具与稳定 code 明确划分。现有批准的“工具操作拒绝”可以保留为 error 结果，但不得扩大为基础身份/Runtime 授权失败可恢复。

### 执行阶段与重试

- `not_started` 只用于参数校验或明确在动作之前拒绝；不能从 timeout/connection error 推断。
- `failed` 表示已确认这次操作失败，不承诺工作区没有其他变化。
- `unknown` 表示结果可能存在副作用；本期保留 media/deploy 的既有任务 ID 与结果结构。
- 不新增生产 ToolRetryMiddleware，不新增线程级错误次数状态。复用现有 Model/Tool/Task 调用预算；连续失败达到预算仍按既有终止行为收敛。
- 后续要自动重试时另列幂等工具、异常、次数、总 deadline，并证明工具内部/Provider 重试不会叠乘；本次不默认开启。

## 已批准的结构化内容

仅第一方已归类的错误使用下面内容。外层 LangChain ToolMessage 的 `status/name/tool_call_id` 才是消息协议；JSON 内 `status` 不是替代品。

```json
{
  "status": "error",
  "code": "tool.invalid_input",
  "error": "工具输入不符合要求，请修正参数后继续。",
  "error_type": "ToolException",
  "name": "search_web",
  "recovery": "correct_input",
  "outcome": "not_started"
}
```

| 字段 | 约束 |
| --- | --- |
| `status` | 固定 error；外层 ToolMessage 同时为 error |
| `code` | tool.invalid_input / tool.upstream_unavailable / tool.operation_failed / tool.outcome_unknown；从批准映射产生 |
| `error` | 固定有界文案；不使用 `str(exc)`、request repr、原响应或堆栈 |
| `error_type` | 已知错误类型名称；不是前端重试/授权依据 |
| `name` | 真实已注册的工具名称；外层官方 Middleware 自动填充，native handler 用受信构造参数传入 |
| `recovery` | correct_input / choose_alternative / do_not_repeat；均为建议，不是自动执行命令 |
| `outcome` | not_started / failed / unknown；依赖真实执行阶段 |

第一方 JSON 最大 2 KiB，已获本次评审批准；受信工具名最多 128 字节，固定内容经测试在上限内。这个值是消息内容上限，不是延迟 SLO。未知 code 不拼接原文，未归类异常继续抛出。成功内容、MCP 多模态块、Filesystem 原生结果与已有 media/deploy `unknown` 结构不强制套这个格式。Provider 未配置/媒体容量已满使用 operation_failed + not_started；提交结果未知使用 outcome_unknown + do_not_repeat，媒体已有 task_id/unknown 回执继续保留。

工具名称与业务错误码用于本平台工具定位；不引入 repo、PR、sandbox_id、Slack、Linear 等 open-swe 业务属性。

## 代码补充位置

### 1. 最小错误函数

- **已新增：** `apps/runtime-service/src/runtime_service/tools/errors.py`。
- **函数：** `tool_error_content(exc, tool_name)`，只识别明确的预期错误并返回安全 JSON，未识别返回 `None`；`on_tool_error(exc, request)` 给官方 Middleware 使用；`handle_expected_tool_error(exc, *, tool_name)` 与 `tool_error_handler(tool_name)` 给第一方工具使用，未识别时 re-raise；`is_transport_error()` 只识别已知 transport，ExceptionGroup 全部叶子已知才允许恢复。
- 不新增 `ToolErrorMiddleware` 类、错误 Registry、MiddlewareBuilder 或 DefaultStack。有限常量映射用于当前真实工具，不做插件配置。
- `DocumentError.code`、`ImageWorkspaceError.code` 可复用；无 code 的第一方 ToolException 只接受审定的精确安全值，不用宽泛前缀/异常字符串正则判断工作区死亡。
- Callback 对 RuntimeErrorBase、GraphBubbleUp、未知异常和 task 致命错误返回 None；官方组件负责 sync/async 和标准 ToolMessage 构造。

### 2. 三个组合根及子 Agent

| 文件 | 函数/位置 | 计划 |
| --- | --- | --- |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` | `get_agent()` 内 `middleware()` | 主图与 researcher 共享显式安全策略原子组件；在 guards 内侧添加官方 ToolErrorMiddleware；工具异常覆盖不包含 task 致命错误 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/researcher.py` | `researcher()` 的 middleware 字段 | 现有声明结构保留，验证内部工具错误后仍有子模型推理；不需要为此重构角色 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` | `get_agent()` 内 `middleware()` | 模板增加同一原子能力，主/子图同步 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/subagents.py` | `build_subagents()` | 使用传入的 middleware；仅在现有传参不足时做最小调整 |
| `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py` | `_tool_error()` 与官方组件声明 | 复用新函数；保留 read_reference 现有重试、工具过滤与未知错误传播 |

代码不得注册一个进程级“所有 graph 全局链”。`failure_demo` 的故意失败案例保留；其他 demo 若复用同一工具 formatter，自然获得内容归一化，不批量迁移其组合根。

### 3. 第一方 native 错误出口

| 文件 | 现有入口 | 计划 |
| --- | --- | --- |
| `services/dearflow_agent/tools/search.py` | `build_research_tools()`、`tavily()`、`jina_extract()`、`_evidence()` | 将 handle_tool_error=True 改为受信工具名绑定的小函数；Provider/输入错误归类，证据根故障不假装普通网页失败 |
| `services/dearflow_agent/tools/research_http.py` | `get_public()` | 保留受控 URL/timeout；区分可公开稳定 code，不能把 403 与 429 当自动重试许可 |
| `services/dearflow_agent/tools/github.py`、`arxiv_search.py`、`web_guidelines.py` | 对应 builder/工具的 handle_tool_error | 共用 formatter，保持成功证据与只读行为 |
| `services/dearflow_agent/tools/media.py`、`deployment.py` | builders/handle_tool_error | 仅统一预期校验失败；已提交任务的 unknown、任务 ID 与取消清理保留 |
| `services/dearflow_agent/tools/memory.py`、`skills.py` | `build_memory_tools()`、`build_skill_tools()` | 错误码审阅在先，scope/授权/存储错误不得被宽泛 ToolException 规则吞掉 |
| `apps/runtime-service/src/runtime_service/tools/documents.py`、`images.py`、`artifacts.py`、`chart.py` | 对应真实工具 builder/native handler | 只修改已确认需要归一化的失败出口，保留现有数据/多模态成功结果 |
| `services/demo/showcase_demo/tools.py` | `fetch_documentation.handle_tool_error` | 示例同范式，无新增异常循环 |

表中 `services/...` 相对于 `apps/runtime-service/src/runtime_service/`。必须先完成 T01 的逐出口清单；某个入口已有安全结构化结果就记录保留，不机械修改所有文件。

### 4. MCP 与工作区

- **MCP：** `services/dearflow_agent/tools/mcp.py:load_mcp_tools()` 保持发现/绑定/冲突/只读检查在构图阶段，失败仍终止。调用阶段明确的只读连接失败可由官方 Middleware 返回安全结果。`isError=True` 的 adapter 结果保留；若内容存在泄露，优先在这一受控加载边界使用 adapter 支持的处理能力，未证明不足前不添加新包装层。
- **工作区：** `workspace/execution.py:execute_in_workspace()`、`services/dearflow_agent/workspace/backend.py:DearWorkspaceBackend.prepare()/aexecute()`、Showcase backend 是真实故障边界。现有准备异常本就发生在工具 wrap 之外，不能声称新增 ToolError 会处理它。
- 实测确认 Deep Agents 的 execute 会吞 `ValueError`，因此已在 `runtime/errors.py` 增加最小 `RuntimeWorkspaceError(RuntimeError)`，使用 `runtime.workspace.unavailable` / `runtime.workspace.execution_unavailable` 等稳定 code。它不继承基于 ValueError 的 RuntimeErrorBase，以免基础故障被误转参数错误。执行创建、可信根目录和资源 OSError 向外传播；单文件不存在仍沿用原工具错误。
- 未找到 docker 可执行文件的启动异常与命令退出码可以区分；单凭 exit_code=125/124、文件不存在或英文 stderr 不能判定整个 workspace 死亡。禁止每次工具调用额外探测 Docker、用新工作区替换原目录或回退宿主 shell。
- 扩大回归确认同一 IO 类也用于 HTTP 读取。`webapp.py:workspace_exception_handler()` 保留读取未创建作用域的原 404/code（image/file/artifact/workspace），其他可信根故障使用安全 500；不创建目录。此映射仅在 HTTP 出口生效，Agent 工具仍传播 RuntimeWorkspaceError 并停止。
- `ImageWorkspace._directory()` 默认只允许创建根内子目录，已有可信根消失时写入失败；工作区 prepare、文件/图片上传和终端初始化显式使用 create_root。研究证据、生成结果和成果发布不能在执行中悄悄重建空根。

### 5. 观测

复用 `apps/runtime-service/src/runtime_service/observability/langfuse.py` 的 callback 和安全 metadata。核对已转换的 error ToolMessage 是否经过 `on_tool_end`；需要时在既有 callback 补安全计数/事件，保留 `tool_error` 的原异常含义，不重复计一次结果。

字段限定为 tool_name、稳定 code、异常类型、处理类别、已有 scope/request/trace 标识。原 arguments、路径、连接 URL、token 和正文不进入新诊断；日志/Exporter 失败不影响容错结果。内部完整异常仅走现有受控排障路径，不扩散到公开流。

### 6. 独立流事件出口

离线探针发现 LangGraph `StreamToolCallHandler._error()` 的 `tool-error.message` 会带 `str(error)`，即使外层 ToolError 已返回安全结果。实施必须单独修复这个出口。优先确认官方配置/等价修复；锁定版本没有时，修改已有 `apps/runtime-service/src/runtime_service/patches.py:_patch_stream_tool_call_handler()`，保留 event、tool_call_id、namespace 和中断清理，把 message 换成固定安全文案，如 `tool.execution_failed`；异常类型仅进入受控安全诊断，不增加事件字段。用真实 stream 契约测试验证，不新增其他 monkey patch，也不默认升级依赖。

### 7. 后端与前端

API 在 `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`、`test_runtime_gateway_runtime_contract.py`、`test_runtime_gateway_sdk_adapters.py` 增加消息/事件验证；HTTP 与 application 编排保持现有逻辑。唯一业务补充是既有 adapter 的 `redact_runtime_private_fields()`：致命 lifecycle、Thread/Run 或原生任务结果的 error 固定为 `runtime.execution_failed`，字典 error 保持字典及有界类型名，字符串 error 保持字符串。工具消息和成功结果保持原样；content/artifact/metadata/values/result 内的业务结果不会触发运行异常改写。

网关按 JSON 键递归过滤，对 JSON 字符串里的 `error` 文本不会自动脱敏。因此第一方工具安全内容必须在 Runtime 产生，API 测试不能只断言 token 键消失。GraphHarbor 的内部致命记录仍可含原异常，平台公开出口通过上述 adapter 处理；不声称底座全部原始出口都已安全。受控只读 MCP 的原生 isError 内容块按批准范围保留，不能把来源于外部工具的自由文本当作统一固定摘要。

Web 代码范围及消息样例见 [frontend-handoff.md](frontend-handoff.md)。继续消费 SDK/Transcript，不新增 store、轮询、重试工具 API 或 SSE 事件类型。

## Middleware 顺序

目标工具执行语义为：

```text
授权/契约/预算 guards -> ToolError -> [已有幂等 Retry] -> 工具执行
```

Reference 的 Error 在 Retry 外层，Retry 使用 `on_failure="error"` 向外抛出耗尽异常。本期 DearFlow/Showcase 不新增 Retry。

Deep Agents 还会注入内建 Filesystem/SubAgent/HITL 组件，不能只看数组就宣称实际顺序。实施时用真实 graph 的事件标记和调用计数确认：拒绝发生在 handler 执行之前；中断穿过所有 wrap；子图的内部 ToolError 生效；成功 Command 不变。`patches.py` 仅处理已复现的流文本问题，不负责工具错误分类。

## 契约与发布影响

- 公开 HTTP 路由、JWT claims、Run 枚举、SSE method/namespace 和原生 ToolMessage schema 不变；第一方部分错误的 content 从字符串改成结构化 JSON。
- 历史已有字符串消息继续展示，不迁移 checkpoint，不重写既有历史。
- 仅本专项方案写入项目目录，待批准和验证后再同步长期标准。检查 [HTTP 错误出口](../../standards/error-envelope.md)、[SSE 标准](../../standards/sse-event.md) 是否需更新；没有实际契约变化不修改置信度或毕业其他专项草案。
- Runtime 与前端可以分别上线；必须验证旧字符串/新 JSON 的消费。本次不自动发布、提交代码或更改依赖。
- 回退以撤回本次 error 接线/formatter 使用为主，保留原目录、任务记录和历史；不删除工作区或回滚数据库。实施前保存代码/镜像基线，隔离环境演练后填写证据。

## 实施顺序与风险

1. 人工评审错误矩阵与范围，随后做最小故障复现，建立逐工具出口清单。
2. 实现共享函数和第一方 native handler，再显式接线主/子 Agent。
3. 完成 MCP、workspace、unknown、取消、审批与观测边界验证；只修复确实失败的出口。
4. 后端验证透传与安全；同事按交接完成前端摘要/消费。
5. 最后执行跨进程、真实模型、浏览器、安全和回退门禁，更新任务状态。

主要风险：宽泛 ValueError/ToolException 吞安全错误；native handler 提前吞错误；父 task 掩盖子图故障；重试造成重复副作用；JSON 字符串泄露；阶段测试冒充生产验收。分别由显式分类、共用 formatter、独立子图测试、不新增自动重试、源头安全内容和分层验证解决。

评审前不把任何“待验证的工作区故障”当作已复现 bug，实施结束前不把 11 项 Reference 基线当作 DearFlow 生产容错已完成。
