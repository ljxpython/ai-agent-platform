# 平台助手 MLflow 运行诊断支持与历史状态、日志链路修复

## 业务背景与问题

平台成员在排查对话运行问题时，先根据 Thread 编号检索到目标轮次的 `run_id`，再让平台助手读取该轮运行诊断（`read_run_diagnostics`）、持久化状态摘要（`persistent_state`）与结构化日志（`read_run_logs`）。当前线上环境默认开启了 MLflow 链路追踪（`TRACING_PROVIDER=mlflow`）而非 Langfuse（`LANGFUSE_ENABLED=false`），实际使用时出现三类证据断层：

1. **追踪诊断被判为未配置**：即使 MLflow 已经按项目实验（`project-{project_id}`）与线程会话（`mlflow.trace.session`）保存了完整 Trace，运行时诊断查询端仅认 Langfuse 配置，直接返回 `availability: "disabled"` / `unavailable_reason: "not_configured"`，且写侧未将启动耗时、模型报错、重试、循环检测、图执行结果和 Workspace 执行摘要写入 MLflow。
2. **非最后一轮的 Checkpoint 状态误报失配**：向平台助手查询同一会话较早轮次的 `run_id` 时，状态查询返回 `persistent_state: unavailable`（`reason: run_mismatch`）。根因在于 `platform-api` 仅请求 `limit: 1` 加 `metadata: {"run_id": ...}`，而底层 GraphHarbor 的线程历史接口忽略了 `metadata` 过滤条件，只返回全线程最新一轮的 Checkpoint，导致比对 `run_id` 必然失败。
3. **Worker 结构化日志未落入平台助手可检索范围**：运行诊断日志依赖标准 `logging` 在 `INFO` 级别输出 JSON；Worker 宿主仅配置 `structlog` 时，`log_diagnostic` 产生的重要节点/图结束日志被默认 `WARNING` 阈值吞掉。同时，`log_context_metric`（模型请求画像、工具溢出视图）缺少 `project_id`、`thread_id`、`platform_trace_id` 等白名单字段，在 `platform-api` 严格按项目和线程校验日志权限时全部被过滤。

## 预期目标

- **兼容 MLflow 的读写双通诊断**：在保持现有对外 HTTP/Pydantic 契约（`RuntimeDiagnostics`、`TraceReference.provider="mlflow"`）不变的前提下，实现平台诊断事件的 MLflow SpanEvent 写入（含图启动前阶段事件缓冲补挂）与基于 MLflow Tracking API 的运行诊断查询投影；历史旧 Trace 在仅有基础 Trace 元数据时返回诚实的 `partial` 结果，新运行事件齐全时返回完整 `available`。
- **精确命中目标轮次的 Checkpoint 状态**：`platform-api` 在读取目标 Run 的持久化状态时，通过历史游标分页扫描匹配 `metadata.run_id == target_run_id` 的最近一条 Checkpoint，解决多轮对话中非最后一轮运行误报 `run_mismatch` 的问题。
- **打通 Worker 诊断与剖面日志穿透**：为 `log_diagnostic` 提供独立不污染宿主的 `INFO` 标准流处理器，并为上下文指标补充受控标量身份字段（不含任何消息正文、参数或密钥），使平台助手能够依法定项目与线程范围检索到这些结构化执行日志。

## 改动分级与文档导航

本项目横跨 `runtime-service` 与 `platform-api` 两个核心服务，影响运行诊断、持久化状态读取和日志穿透的跨服务排障链路，按仓库规范归类为**链路改动**（不新增 Delegation JWT operation、不新增 SSE 事件类型，既有外部边界契约保持向后兼容）。

| 文档 | 用途 |
|---|---|
| [实施计划](plan.md) | 架构方案、MLflow 读写策略、Checkpoint 分页与日志字段安全设计、取舍与边界 |
| [任务清单](tasks.md) | 唯一权威任务拆解（Task 1–Task 5）、状态、涉及文件与执行进展 |
| [验证记录](verification.md) | 验收矩阵、阶段验证（Phase）与整体验收（Final）证据 |

## 当前进度摘要

- **总体状态：** 已完成（done，含本地单测、跨进程联调及 `sshmy1` 线上部署与真实全链路验收）
- **已完成：** Task 1–Task 5 全部完成并部署 `sshmy1`（`agent-runtime-api`、`agent-runtime-worker`、`agent-platform-api` 均处于 `active running`、`NRestarts=0`）。线上复核截图存量旧 Run（`c951dfba`）返回 `partial` + 完整 `persistent_state`；线上多轮实测新 Run（`140192a3`）即时查询 `1.575s` 返回 `available`（含 7 个启动阶段、紧凑 `runtime.diag.events` 3576 字节标签与 Loki 14 条跨服务日志），并实测在第 2 轮之后回查第 1 轮（`441c090c`）通过 `before` 游标分页与 `SpanEvents` 回退同时拿回完整 `available` 诊断与第 1 轮持久化状态。用户批准的两条经验已沉淀至 `docs/lessons/`。
- **未覆盖与下一步：** 保留对 Langfuse 线上生产环境的回查边界（本轮生产仅开启 `TRACING_PROVIDER=mlflow`）；未执行任何未经授权的 Git 提交或分支操作。
