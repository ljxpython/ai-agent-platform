# 任务清单：平台助手 MLflow 诊断、Checkpoint 分页匹配与日志链路修复

> 本文档为本项目的唯一权威任务进度源；各任务遵循 [开发规范](../../../AGENTS.md) 与 [实施计划](plan.md)。

---

### Task 1：Runtime 诊断事件补齐写入 MLflow 与启动事件补挂

在当前仅导出 `runtime.loop.observation*` 3 类事件的基础上，补齐全部平台结构化诊断事件（含 `runtime.startup.*`、`runtime.graph.completed`、`runtime.model_call.failed`、`runtime.prepare.completed`、`runtime.retry.completed`、`runtime.workspace.execution_completed`、`runtime.loop.transition`、`runtime.tool.failed` 等）的 MLflow SpanEvent 写入，解决启动事件先于 Root Span 产生、图结束时 Root Span 先关闭导致的丢失问题。

**状态：** 已完成（done）。
**完成标准：** 开启 `TRACING_PROVIDER=mlflow`（且未启用 Langfuse）运行一次带启动阶段、模型/工具调用或错误/重试的图后，MLflow Trace 中的 SpanEvents 完整包含脱敏后的 `schema_version=1` 诊断事件，且不泄露敏感输入/输出或引发回调崩溃。
**涉及位置：**
- `apps/runtime-service/src/runtime_service/observability/mlflow_tracer.py`
- `apps/runtime-service/src/runtime_service/observability/langfuse.py`

- [x] 在 `mlflow_tracer.py` 实现线程安全、有界的按 `run_id` 索引的待补挂事件队列（上限 512 Run、单 Run 最多 64 条）与活跃 Root Span 注册表（先校验 `_is_span_recording`，避免向已结束子 Span 写入被 OpenTelemetry 丢弃；在 Root Chain 启动时刷新暂存事件、结束时清理引用）；同步写入精简压缩版 `runtime.diag.events` Trace Tag（剥离已在 Trace 元数据存在的 8 个公共字段、严格限长 `<= 3800` 字节避开 MLflow 后端 4096 字节截断上限），并在 Root Chain 结束时通过守护线程短时 join（最多 1.5s）调用 `mlflow.flush_trace_async_logging` 保证即时可读。
- [x] 在 `langfuse.py` 扩展 `record_diagnostic_event()`，开启 MLflow 时将 `_MLFLOW_DIAGNOSTIC_EVENTS`（覆盖全部 `_EVENTS`、工具/节点/计划事件及循环观测）写入活跃或 Root Span；将 `_RuntimeDiagnosticsCallback` 调至 `MLflowFailSoftCallback` 之前且统一启用 `run_inline = True`，消除异步 `ainvoke` 回调线程池并发关闭 Root Span 的竞态。
- [x] 新增并运行 `runtime-service` 真实 SQLite MLflow DB 单元测试，验证同步/异步执行下全部核心事件均落盘、紧凑 Tag 体积达标且无敏感字段泄露。

**开发与验证进度：** 已实施、通过全部 `observability` 单测（186 passed）并部署至 `sshmy1` 通过真实 `dearflow_agent` 运行验证。
**下一步：** 已完成。

---

### Task 2：Runtime 诊断查询接口接入 MLflow

让 `query_run_diagnostics` 在 `TRACING_PROVIDER` 为 `mlflow` 或 `both` 时，能够使用既有 `MLFLOW_TRACKING_URI` 及认证环境变量从 MLflow 搜索目标 Run 对应的 Trace 并投影为 `RuntimeDiagnostics` v1 结果，同时对无 `SpanEvent` 的历史旧 Trace 提供 `partial` 降级信息。

**状态：** 已完成（done）。
**完成标准：** 不配置 Langfuse、仅配置 MLflow 时，`/internal/threads/{thread_id}/runs/{run_id}/diagnostics` 能定位 `project-{project_id}` 或默认实验下的对应 Trace；新 Run 诊断返回 `availability="available"` 与完整字段，无 `SpanEvent` 的存量旧 Trace 返回 `availability="partial"` 与基础 `trace` / `correlation` / `graph_executions` 信息，错误场景正确区分 `not_configured`、`not_recorded` 与 `backend_unavailable`。
**涉及位置：**
- `apps/runtime-service/src/runtime_service/observability/query.py`

- [x] 重构 `diagnostics_client_lifespan()` 与 `query_run_diagnostics()` 分支，支持按 `get_tracing_provider()` 路由至 Langfuse / MLflow / 双启回退，并在 8 秒超时保护内通过 `asyncio.to_thread` 执行同步 `MlflowClient` 查询。
- [x] 实现 MLflow 实验定位（优先 `project-{project_id}`，兜底默认实验 `MLFLOW_EXPERIMENT_NAME`）、`metadata.\`mlflow.trace.session\`` 安全过滤+`order_by=["timestamp DESC"]` 与 `include_spans=False` 轻量搜索，优先直接解码 `runtime.diag.events` 标签实现零 `get_trace` 极速投影；若标签缺失或解析失败且 `not spans`（兼容空 `TraceData(spans=[])`），按单条 `get_trace` 回退提取 `SpanEvent`，并执行多维度范围匹配校验（`tenant_id`/`project_id`/`graph_id`/`thread_id`/`run_id`）。
- [x] 实现无 `SpanEvent` 存量 Trace 的基础 `trace`、`correlation` 与 `graph_executions` 兜底映射，确保 `availability` 诚实标注为 `partial`。
- [x] 编写单元测试覆盖端到端写入 -> MLflow SQLite 存储 -> `query_run_diagnostics` 标签快路径、空 `TraceData(spans=[])` 回退及 `/internal/threads/{thread_id}/runs/{run_id}/diagnostics` HTTP 接口契约。

**开发与验证进度：** 已实施、通过全部 `observability` 单测并部署 `sshmy1` 验证通过；详见 [验证记录](verification.md#阶段验证phase)。
**下一步：** 已完成。

---

### Task 3：Runtime Worker 结构化诊断日志独立输出与关联字段补齐

修复 Worker 仅使用 `structlog` 时标准 `INFO` 诊断日志被吞、以及上下文指标日志缺乏 `project_id`/`thread_id`/`platform_trace_id` 导致无法通过平台助手 ACL 检索的问题。

**状态：** 已完成（done）。
**完成标准：** `log_diagnostic` 独立输出标准 `INFO` 单行 JSON 日志；`log_context_metric` 与 `runtime.model_request.profile` 自动携带当前运行元数据中的合法 `project_id`、`thread_id`、`platform_trace_id` 与 `request_id`，不包含消息正文或密钥；产出日志能够满足 `platform-api` `logs.py` 的白名单与范围校验。
**涉及位置：**
- `apps/runtime-service/src/runtime_service/observability/diagnostics.py`
- `apps/runtime-service/src/runtime_service/observability/logging.py`
- `apps/runtime-service/src/runtime_service/observability/usage.py`

- [x] 为 `log_diagnostic` 所用 logger 设置 `INFO` 级别，并在 root logger 无有效 `INFO` 处理器（如 `graphharbor worker`）时按需挂载独立 `StreamHandler`，兼顾生产 stdout 输出与单测 `caplog`。
- [x] 在 `log_context_metric` 与 `usage.py` 中从运行元数据安全注入非空且过合法正则的 `project_id`、`thread_id`、`platform_trace_id`、`request_id`。
- [x] 补齐单元测试，验证模拟无 root handler 环境下可捕获完整 JSON 诊断及画像日志字段，且通过 `platform-api` 日志权限与字段过滤。

**开发与验证进度：** 已实施、通过测试并部署至 `sshmy1`，线上真实 Loki（`127.0.0.1:3100`）已检索到 Worker 发出的全量 `runtime.*` `INFO` 结构化日志；详见 [验证记录](verification.md#阶段验证phase)。
**下一步：** 已完成。

---

### Task 4：Platform API 修复 Checkpoint 按 Run 分页匹配

解决底层 GraphHarbor 线程历史接口忽略 `metadata={"run_id": ...}` 参数导致多轮会话查询早期 Run 时返回最新一轮 Checkpoint 并触发 `run_mismatch` 的问题，并修正 `require_scope()` 对默认租户传出数据库 UUID 而非 `__default` 导致的诊断作用域不匹配。

**状态：** 已完成（done）。
**完成标准：** 当目标 Thread 在目标 Run 之后已有更多新 Run 时，`read_checkpoint` 仍能通过 `before` 游标有界分页精确定位目标 `run_id` 对应的最新 Checkpoint 并返回 `availability="available"`；默认租户（`slug == "__default"`）向 Runtime 统一传出 `tenant_id="__default"`；当扫描完可用历史或触及安全上限仍未命中时返回确定失败/空原因而不误拿错误 Run 摘要；保留既有 `checkpoint_summary` 单条失配契约。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/platform_assistant/diagnostics.py`
- `apps/platform-api/src/platform_api/modules/platform_assistant/service.py`

- [x] 在 `read_checkpoint` 中保留首页 `limit=1` 快速探测最新记录（零额外开销），若非目标 `run_id` 则按每页 25 条、最多 8 页携带 `before` 游标向前分页扫描，设置游标停滞防死循环保护并维持 8 秒总超时控制。
- [x] 在 `require_scope()` 对 `TenantRecord.slug == "__default"` 返回 `"__default"`，与普通聊天运行写入的默认租户标识对齐。
- [x] 完善空历史返回 `not_recorded` 与全量扫描未命中返回 `run_mismatch` 的边界语义，保留既有 `checkpoint_summary` 行为兼容。
- [x] 编写并运行 `platform-api` 单元测试，覆盖跨多页 `before` 翻页命中较早 `run_id` 与游标停滞中止场景，回归测试 123 项（含 6 子测试）全部通过。

**开发与验证进度：** 已实施、通过回归并部署至 `sshmy1` 验证通过；详见 [验证记录](verification.md#阶段验证phase)。
**下一步：** 已完成。

---

### Task 5：跨服务链路联调、线上部署实测与项目整体验收（Final）

在本地真实进程链路与 `sshmy1` 生产主机（真实 MLflow `http://127.0.0.1:5000`、真实 Loki `http://127.0.0.1:3100`、真实 PostgreSQL/GraphHarbor）下验证端到端行为，完成两条已批准经验沉淀与全套文档校准。

**状态：** 已完成（done）。
**完成标准：**
- [x] 各自服务相关单元测试全量通过（`runtime-service` observability 186 passed、`platform-api` 123 passed / 6 subtests passed）。
- [x] 本地跨进程 HTTP + JWT HMAC + ACL 回调端到端链路校验通过（`CROSS_PROCESS_MLFLOW_E2E_OK`）。
- [x] `sshmy1` 线上部署生效（`agent-runtime-api`、`agent-runtime-worker`、`agent-platform-api` 均 `active running`、`NRestarts=0`），覆盖存量旧 Run（`c951dfba` 返回 `partial` + `persistent_state`）、第 2 轮新 Run（`140192a3` 即时查询 `1.575s` 返回 `available` + 3576B 紧凑 tag + Loki 14 条结构化日志）与第 2 轮之后回查第 1 轮旧 Run（`441c090c` 通过 `before` 分页 + `SpanEvents` 回退返回 `available` 及第 1 轮 `checkpoint_id`）。
- [x] 两条已批准经验写入 `docs/lessons/runtime-service.md`、`docs/lessons/cross-service.md` 与 `docs/lessons/index.md`；项目与全局文档更新完成，且 `python3 scripts/check_docs.py` 校验通过。

**开发与验证进度：** 已全部完成并通过线上实测与文档校验。
**下一步：** 交付最终总结。
