# 参考实现、当前差距与方案取舍

## 证据口径

本仓代码引用均为仓库根目录相对路径，基线为 `bf47991b7592b19cbda1051c6a674623450318ae`。参考仓库是用户指定的 `research/open-swe`，其 HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`，工作副本有未提交变更。下文 open-swe 路径均相对参考仓库根目录。

本次只读核对参考文件，没有修改或运行 open-swe 的测试。关键文件快照 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `agent/sandboxes/retry.py` | `f002d88e5275f26581301b57416ffe61780692cdfd9484ab7a4390bea9fb50d1` |
| `agent/middleware/sandbox_circuit_breaker.py` | `926e7c502c425f07057ea501c373355d0e8d614e7af0eb29e16508dbcd0ae4a1` |
| `agent/middleware/tool_error_handler.py` | `dbbb1a9aa84733e9f76be8ad70a5246e4a179157dcb50ee6d1c4f16a8bfce5e7` |
| `agent/sandboxes/providers/langsmith.py` | `857140a111ed0e59b576eb90ed3e1f5346959348e24cdfaaf57e99e248f40c86` |

## open-swe 如何做

### 1. 重试判定落在 Sandbox/SDK 边界

`agent/sandboxes/retry.py:is_transient_sandbox_error()` 只匹配 SDK 的 `SandboxRetryableConnectionError`。该文件明确依赖 SDK 语义：WebSocket upgrade 被 500/502/503/504 拒绝时，execute frame 尚未发送。安全依据是未发送命令，不是 HTTP 状态数字本身。

`retry_transient_sandbox_errors()` 调用 operation，遇到上述类型才等待并再试：

| 参数 | 真实含义 |
| --- | --- |
| `MAX_TRANSIENT_ATTEMPTS=4` | 最多 4 次总尝试，含首次，最多额外重试 3 次 |
| 基础退避 0.5 秒 | 连续失败等待约 0.5、1、2 秒 |
| jitter ±20% | 这 3 次计划等待累计 2.8-4.2 秒 |
| delay cap 8 秒 | 当前默认 4 次总尝试不会触及该上限 |

`agent/sandboxes/providers/langsmith.py:TimeoutLangSmithSandbox.aexecute()` 将该循环包在 `_aexecute_once()` 外，未在前端或外部通知层重试。

### 2. 有限执行时间与清理

`_aexecute_once()` 使用 sandbox handle、客户端 deadline、server-side command timeout。客户端等待超时会调用 `_asafe_kill()`，返回 exit 124；普通非零结果仍为 ExecuteResponse。

但该参考也有需要避开的路径：拿到 handle 后，`handle.result` 的中途连接错误会调用 `_abase_execute(command)`。这时第一次命令可能已开始。`tests/sandbox/test_langsmith_sandbox_timeout.py:test_aexecute_midstream_ws_drop_falls_back_to_base()` 只断言 fallback 调用，没有证明副作用只发生一次。本项目不照搬这一 fallback；结果丢失时停止并保留未知结果。

### 3. 工具错误中间件与不可达通知

`agent/middleware/tool_error_handler.py:ToolErrorMiddleware.awrap_tool_call()` 区分普通工具错误、transient 耗尽和 sandbox unreachable。不可达时发送通知后重新抛出异常；server reload 不等同 sandbox 故障，普通文件不存在也不等同整个 sandbox 不可达。

transient 耗尽后，参考返回带 `recovery=sandbox_transient` 的 error ToolMessage，允许模型再次调用。它不能保证整次 Run 的重试次数有界。本期选择在预算耗尽后形成失败终态，避免在 backend、middleware、LLM 和 Worker 四层叠加重试。

参考 `_to_error_payload()` 会公开 `str(exc)`，日志也存在 request 表示；本平台已有安全错误出口，不能沿用这一做法。

`agent/middleware/sandbox_circuit_breaker.py:post_sandbox_unreachable_notification()` 按 Slack、Linear、GitHub 渠道发送通知。`sandbox_unreachable_message()` 说明“不知道是否会恢复”，避免把空 sandbox 当成恢复后的原工作区。

这个文件没有 closed/open/half-open、计数窗口、恢复探测等熔断状态机。应借鉴其“准确说明、保护原数据、终止当前 Run”的原则，不能据文件名规划一套全局熔断器。`agent/server.py:_prepare()` 也覆盖启动准备阶段的不可达，不只处理工具调用期。

## 当前项目已有能力

| 能力 | 当前事实与关键位置 | 本期动作 |
| --- | --- | --- |
| Workspace 与执行隔离 | `apps/runtime-service/src/runtime_service/workspace/execution.py:runtime_backend()/docker_workspace_args()/execute_in_workspace()`；Docker 无网络、只读根、cap-drop、资源限制，持久目录绑定 | 复用共享入口；同事“只有本地目录、将来才有 Sandbox”的前提不完整 |
| 本地开发执行 | Showcase `LocalWorkspaceBackend`、Dear `DearWorkspaceBackend.aexecute()` 使用官方 LocalShellBackend | 保持开发模式；不是生产隔离，也不是 Docker 的失败 fallback |
| 命令有界 | 1-60 秒 timeout、128 KiB 输出截断、取消/等待超时清理 | 保留并补失败路径验证，不重写正常执行 |
| 稳定 Workspace 异常 | `runtime/errors.py:RuntimeWorkspaceError` 继承 RuntimeError，仅携带稳定 code | 复用，不把原生 OSError 直接抛给 Worker |
| 选择性工具错误处理 | `tools/errors.py:tool_error_content()/on_tool_error()`；Showcase/Dear 组合根显式使用官方 ToolErrorMiddleware | Workspace、权限、控制流和未知缺陷继续传播，不新增全量异常兜底 |
| 启动与 Run 诊断 | `observability/startup.py:StartupDiagnostics`、`observability/langfuse.py:_RuntimeDiagnosticsCallback` | 增加安全 Workspace 原因，复用可信身份和回调 |
| 诊断查询 | Runtime `observability/query.py`、API `application/diagnostics.py` 与 `get_thread_run_diagnostics()` | 在既有 GET、diagnostics-read/ACL、版本 1 DTO 中增加可选字段 |
| SSE 与资源错误槽位 | API `sdk_client.py:project_execution_error()/redact_runtime_private_fields()`、`presentation/http.py:_redact_sse_frame()` | 基线先收敛；扩精确白名单，不公开任意异常消息 |
| 前端诊断展示 | `diagnostics/types.ts`、`view-model.ts`、`RunDiagnostics.vue`、`useRunDiagnostics.ts` | 同事补 Workspace 记录和安全 Run 提示，不另建页面/状态机 |

表内省略路径前缀的 Runtime 文件均位于 `apps/runtime-service/src/runtime_service/`；API 文件均位于 `apps/platform-api/src/platform_api/`；前端诊断文件位于 `apps/platform-web/src/modules/chat/`。

## 当前差距与风险

1. 共享执行没有 transient retry，但整个 `asyncio.create_subprocess_exec()` 的异常并不天然证明命令尚未执行。启动含子进程创建与异步管道接线，不能用“函数没返回 process”充当副作用证明。
2. 现有启动 OSError 被包装为 `runtime.workspace.execution_unavailable`；读输出、等待、清理阶段还需核对顶层原生 OS/连接异常是否逃逸。
3. Docker CLI 已启动但 daemon 不可用会返回 exit 125；本次真实用例复现了这一点。用户命令也能 exit 125，不能把所有 125 转成“未启动”并重试。
4. 既有 Workspace 致命异常可以停止 Run，但 API 将已知机器码抹为通用错误。缺少安全且具体的 Workspace 原因和重试记录。
5. 诊断查询当前仅投影模型失败、graph 完成、startup 完成、startup phase 四类事件；工具失败只记录有限类型，没有 Workspace 的 attempts/等待信息。
6. 已安装 GraphHarbor `0.13.0.post41` 的 `langgraph_runtime_pg/production_worker.py:_is_infrastructure_error()` 按顶层异常类型匹配 TimeoutError、ConnectionError、OSError、DBAPIError，并可能重调度整个 Run。backend 不重试不等于系统不重放，必须验证 RuntimeWorkspaceError 顶层传播。
7. worktree 的 API 基线有安全与契约问题：`tasks.error` 原文透出；测试期待 `runtime.execution_failed`，HEAD 投影对象为 `runtime_execution_failed`、字符串为固定英文说明。见 [真实记录](verification.md#规划阶段实际记录)。规划不自行裁决已批准契约与代码的冲突，实施先经过人工评审。

## 对同事方案逐条评价

| 建议 | 判断 | 调整后方案 |
| --- | --- | --- |
| 临时文件锁、权限瞬时不可用都识别为 transient | 不采纳这个错误集合 | 锁不一定来自执行器；权限可能是安全拒绝；写入可能已部分完成。EACCES/EPERM、ENOSPC、一般文件锁等保持单次失败 |
| 给 workspace 执行加统一 retry 装饰器 | 不采纳整函数/整工具包装 | 先证明窄启动边界；只有可信“未执行”信号允许最多 4 次总尝试。已启动、等待、超时、结果未知和清理绝不重跑命令 |
| 耗尽后 SSE 用户提示，不 crash | 采纳准确报告和安全提示 | Runtime 抛稳定异常，原生 Run 失败；API 投影现有 error/lifecycle/task 槽位，Web 展示一次。不能生成假 AIMessage 或 ToolMessage 假恢复 |
| 云 Sandbox 接入后需要这类能力 | 原则成立，provider 实现后再落地 | 复用后续 SDK 类型化证据；现在不建空 provider 接口或新增云依赖 |

## 框架能力与本地范式

已按项目要求查询 LangChain docs/reference MCP，核对官方 `ToolRetryMiddleware`、`ToolErrorMiddleware`、Deep Agents `SandboxBackendProtocol` 和 `adispatch_custom_event`。

- 官方 ToolRetryMiddleware 重跑整个 tool handler，适合当前 Reference 的只读 `read_reference`，不适合任意副作用 `execute`。不新增 tenacity，也不把通用 retry 默认值用于 Workspace。
- retry 必须了解执行阶段，适合所属 backend/共享 execution；鉴权和 Workspace 初始化仍由现有 WorkspaceMiddleware 负责。
- 安全观测可使用官方 custom callback 事件，由既有诊断回调合并可信 scope；这不是新增 GraphHarbor SSE custom 通道。
- 服务 `agent.py` 保持唯一组合根；backend 无 Slack/repo/team 字段；prompts 不读配置、不通知用户；共享工具代码不导入 Dear/Showcase 业务。

## 前端、API、Runtime 是否需要做

| 层 | 是否需要 | 本期承担的工作 |
| --- | --- | --- |
| platform-web | 需要小范围适配，交同事 | 精确安全错误提示；既有 RunDiagnostics 的 Workspace 摘要；历史/切线程/撤权/取消回归 |
| platform-api | 需要 | 收敛现有安全出口差异；精确投影 Workspace 错误；验证扩展诊断 DTO 和 ACL，保持 Run 状态/流结构 |
| runtime-service | 需要，核心实现 | 判定与执行边界、可靠启动证据、清理、结果未知停止、可信诊断、共享 backend 覆盖 |
| GraphHarbor | 本期不改源码 | 保持原生状态机与生命周期；用契约和隔离 Worker 测试证明 Workspace 错误不会整 Run 重试 |
