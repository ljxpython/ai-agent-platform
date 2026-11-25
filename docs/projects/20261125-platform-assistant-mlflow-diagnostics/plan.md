# 实施计划：平台助手 MLflow 诊断、Checkpoint 分页匹配与日志链路修复

## 1. 目标与非目标

### 目标
1. **Runtime 诊断查询适配 MLflow**：`runtime-service` 在 `TRACING_PROVIDER` 为 `mlflow` 或 `both` 且配置有效 `MLFLOW_TRACKING_URI` 时，能够通过 MLflow Tracking API 查询指定 Run 的 Trace 与 SpanEvent，并投影为既有的 `RuntimeDiagnostics` v1 结构。
2. **Runtime 诊断事件补齐写入 MLflow**：`record_diagnostic_event()` 在开启 MLflow 时不再仅导出 3 个循环观测事件，而是覆盖全部结构化诊断事件（含启动阶段、准备、重试、模型失败、Workspace 执行、循环转换与图执行结束），并安全脱敏（复用 `safe_fields`）。
3. **Platform API Checkpoint 精确按 Run 查找**：修正 `read_checkpoint` 因底层 GraphHarbor `/threads/{thread_id}/history` 忽略 `metadata` 参数导致的误报 `run_mismatch`，改为有界游标分页查找匹配 `run_id` 的最新 Checkpoint。
4. **Runtime 结构化诊断日志可见性与关联完善**：确保 `log_diagnostic` 在 Worker 环境下稳定输出 JSON `INFO` 日志；为 `log_context_metric` 补充受控标量标识（`project_id`、`thread_id`、`platform_trace_id`、`request_id`），使受权用户可通过 `read_run_logs` 检索。

### 非目标
- 不修改外部已部署的 `graphharbor` / `langgraph-runtime-pg` 第三方发行包源码。
- 不修改 `RuntimeDiagnostics` 或 `TraceLogsResponse` 的既有边界契约与权限过滤阈值，不放宽日志的跨项目/跨线程 ACL 校验。
- 未经用户明确指令，不执行 Git 提交、推送或远程生产主机变更部署。

---

## 2. 详细技术方案

### 2.1 MLflow 诊断事件写入与生命周期对齐（Runtime Service）

**现状问题：**
- `apps/runtime-service/src/runtime_service/observability/langfuse.py` 中的 `record_diagnostic_event()` 仅对 `runtime.loop.observation*` 向当前 active MLflow span 追加 `SpanEvent`；其余 8 类事件在 Langfuse 未配置时直接丢弃。
- `StartupDiagnostics`（`startup.py`）在图调用开始前完成并触发 `runtime.startup.*`，此时 MLflow Trace 与 Root Span 尚未建立。
- `with_langfuse_tracing()` 将 `MLflowFailSoftCallback` 排在 `_RuntimeDiagnosticsCallback` 之前，导致图结束执行 `on_chain_end`/`on_chain_error` 时 Root Span 可能已经先被 `MlflowFailSoftCallback` 关闭，后续 `_RuntimeDiagnosticsCallback._finish` 发出的 `runtime.graph.completed` 无法再挂载到已关闭的 Span。

**设计方案：**
1. **有界事件缓冲与 Root Span 索引（位于 `mlflow_tracer.py`）**：
   - 维护进程内线程安全、带最大条目上限（防异常泄露）的两个轻量索引（以 `execution_run_id` 为键）：
     - `_PENDING_EVENTS_BY_RUN`：暂存图启动前产生的 `runtime.startup.*` 等事件（脱敏后标量字典）。
     - `_ACTIVE_ROOT_SPANS_BY_RUN`：记录已开启且尚未关闭的 Root `LiveSpan`。
   - 提供 `record_mlflow_diagnostic_event(event, safe_payload)`：
     - 若当前线程/协程存在 `mlflow.get_current_active_span()`，优先挂载 `SpanEvent(name=event, attributes={"schema_version": 1, **safe_payload})`；
     - 否则查找 `_ACTIVE_ROOT_SPANS_BY_RUN.get(run_id)`，向未关闭的 Root Span 挂载；
     - 若 Root Span 尚未开启，则放入 `_PENDING_EVENTS_BY_RUN[run_id]`（单 Run 最多保留 64 条、总键数设上限淘汰最早条目）。
2. **回调顺序与生命周期协同（位于 `mlflow_tracer.py` 与 `langfuse.py`）**：
   - 在 `MLflowFailSoftCallback.on_chain_start(parent_run_id=None)` 调用完 `self._tracer.on_chain_start(...)` 后：
     - 获取新建的 Root Span（优先 `mlflow.get_current_active_span()`，其次从 `self._tracer._get_span_by_run_id(run_id)` 获取以兼容 `run_inline=False`）；
     - 立即注册进 `_ACTIVE_ROOT_SPANS_BY_RUN[exec_run_id]` 并将 `_PENDING_EVENTS_BY_RUN` 中暂存的 `startup` 事件全部追加到该 Root Span。
   - 在 `with_langfuse_tracing()` 中，`_RuntimeDiagnosticsCallback` 仅在 `on_chain_end`/`on_chain_error` 早于 `MLflowFailSoftCallback` 关闭 Span（或将 `_RuntimeDiagnosticsCallback` 注册于 `MLflowFailSoftCallback` 之前，因 `_RuntimeDiagnosticsCallback.on_chain_start` 不依赖 MLflow span，而 `_finish` 触发 `runtime.graph.completed` 时 Root Span 恰好仍开启，可直接成功追加 `SpanEvent`）。
   - `MLflowFailSoftCallback.on_chain_end` 与 `on_chain_error`（当该 `run_id` 为 root chain 时）在清理前释放 `_ACTIVE_ROOT_SPANS_BY_RUN` 与剩余缓冲，确保无内存驻留。

**安全与失败降级：**
- 所有写入 MLflow 的事件字段必须先经 `diagnostics.safe_fields(fields)` 白名单脱敏，保证不携带任何正文、路径或密钥。
- 整个流程保持 fail-soft，异常仅计数日志，绝不中断 Agent 主运行。

---

### 2.2 MLflow 诊断查询适配（Runtime Service）

**现状问题：**
- `apps/runtime-service/src/runtime_service/observability/query.py` 中的 `diagnostics_client_lifespan()` 与 `query_run_diagnostics()` 仅判断 `LANGFUSE_ENABLED=true`。

**设计方案：**
1. **双引擎状态感知（`diagnostics_client_lifespan` & `query_run_diagnostics`）**：
   - 保留原有 Langfuse `AsyncLangfuseAPI` 生命周期管理。
   - 当 `get_tracing_provider()` 返回 `"mlflow"` 时，直接走 MLflow 查询分支；当为 `"both"` 时，优先查询可用后端（若 Langfuse 已配置先查 Langfuse，否则或 Langfuse `not_recorded` 时再查 MLflow；两者均未配置则返回 `not_configured`）。
   - MLflow 查询需检查 `MLFLOW_TRACKING_URI` 是否非空；若为空返回 `empty_diagnostics("not_configured")`。注意调用前确保调用一次 `initialize_mlflow()` 使 SDK 使用配置的 URI（同时遵循 `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` / `MLFLOW_TRACKING_TOKEN`）。
2. **定位目标实验与 Trace（同步 `MlflowClient` 包装在 `asyncio.to_thread` + 2s 超时内）**：
   - 根据 `project_id` 定位实验 `f"project-{project_id}"`，若不存在或无结果则兜底检查全局 `MLFLOW_EXPERIMENT_NAME`（默认 `"ai-agent-platform-traces"`）对应实验。
   - 优先使用 `filter_string` 按 `metadata.`mlflow.trace.session` = '{thread_id}'`（且对参数进行安全正则校验防注入）搜索最近 50 条 Trace，并在 Python 侧对每条 Trace 的 `trace_metadata`（`tenant_id`, `project_id`, `graph_id`, `thread_id`, `run_id`）及 `tags` 进行严格匹配。若特定 MLflow 后端过滤语法不兼容则自动回退到不带 `filter_string` 拉取最近 50 条后按元数据严格核对。
   - 若匹配到的 Trace 对象不包含完整 `spans`，再按 `trace_id` 调 `client.get_trace(trace_id)` 拉取 Spans（单条 Trace）。
3. **事件提取与历史 Trace 兼容投影**：
   - 遍历匹配的 Trace 内全部 `span.events`，提取 `event.name in _EVENTS` 且 `attributes.get("schema_version") == 1` 的事件，构造与既有 `_project(observations, expected, truncated=...)` 完全一致的数据结构（包含唯一 `observation_id`、`trace_id`、`name` 与 `metadata`）。
   - 若某个历史旧 Trace 已被 MLflow 记录，但 Spans 中尚未包含 `_EVENTS` 中的 `SpanEvent`（如本次改造前的存量 Trace）：
     - 仍填充 `trace`（`provider="mlflow"`, `trace_id=trace.info.trace_id`, `url=None`）与 `correlation`（由 `trace_metadata` / `tags` 中的 `request_id` 与 `platform_trace_id` 经 `_identifier` 校验得到）；
     - 若 `graph_executions` 为空，依据 `trace.info.state`（`OK -> success`, `ERROR -> failed`, 其余忽略或兜底）与 `trace.info.execution_duration`（或根 Span 起止时间差）合成 1 条合法的 `graph_executions`；
     - 由于缺少 `startup` 等结构化明细，`_project` 规则会自然输出 `availability = "partial"`（有条件展示而非虚报完整）与 `unavailable_reason = None`。当新运行完整写齐 `runtime.startup.*` 与 `runtime.graph.completed` 后，自动变为 `availability = "available"`。

---

### 2.3 Checkpoint 按 Run 精确查找（Platform API）

**现状问题：**
- `apps/platform-api/src/platform_api/modules/platform_assistant/diagnostics.py` 的 `read_checkpoint()` 调用 `gateway.get_thread_history(..., payload={"limit": 1, "metadata": {"run_id": run_id}})`。由于外部 `graphharbor` 的 `threads_history` 仅将 `config`（含 `thread_id`/`checkpoint_ns`）与 `before`/`limit` 传给 `aget_state_history`，忽略了 `metadata` 过滤，始终返回全 Thread 最新那条 Checkpoint，一旦该 Thread 在目标 Run 之后又有新轮对话，必触发 `run_mismatch`。

**设计方案：**
- 在 `read_checkpoint()` 内保持总超时 `asyncio.timeout(8)` 不变，将读取策略改为有界分页查找：
  - 每页请求 `limit = 25`（保留 `metadata={"run_id": run_id}` 兼容未来服务端支持过滤的情况），最多翻 `8` 页（累计检查最多 `200` 条 Checkpoint）；
  - 逐页遍历检查 `(item.get("metadata") or {}).get("run_id") == run_id`：
    - 只要找到第一条匹配记录（倒序中即该 Run 的最新 Checkpoint），立即调用现有 `checkpoint_summary(item, run_id)` 返回完整摘要；
    - 若当前页均不匹配且本页条数达到 `limit`，提取最后一条的 `checkpoint`（或 `checkpoint_id`）作为下一轮 `before` 游标继续向前查询；注意当遇到游标未前进或重复时立即停止防死循环。
  - 若仅有 1 页或扫描完所有记录（未超过上限）仍未发现目标 `run_id`：
    - 保留对单条非法/失配情况的区分逻辑：如果整段返回本来就只有空列表返回 `{"availability": "empty", "reason": "not_recorded"}`；如果历史非空但翻查完或触及上限均未命中该 `run_id`，则按是否被历史长度截断返回清楚且符合原契约的 `unavailable`（例如在不超过检查上限扫完全部历史时返回 `empty / not_recorded`，触及上限未找到则返回 `unavailable / run_mismatch` 或保留可解释语义；具体见单测验证，保证不破坏 `checkpoint_summary` 既有单元测试）。

---

### 2.4 Runtime 结构化日志输出与受控关联补充（Runtime Service）

**现状问题：**
- `apps/runtime-service/src/runtime_service/observability/diagnostics.py` 的 `log_diagnostic()` 使用未配独立 Handler 的模块 logger，在 Worker 仅配 structlog 时 `INFO` 日志被吞。
- `apps/runtime-service/src/runtime_service/observability/logging.py` 的 `log_context_metric()` 只输出 `run_id` 和 `checkpoint_ns`，缺乏 `project_id`/`thread_id`/`platform_trace_id`/`request_id`，被 `platform-api/modules/platform_assistant/logs.py` 的项目与线程强过滤拦截。

**设计方案：**
1. **独立诊断日志流（`diagnostics.py`）**：
   - 将 `log_diagnostic` 使用的 logger 显式设置 `level = logging.INFO`、`propagate = False` 并挂载一个 `StreamHandler`（仅当尚未存在 handler 时），参考 `observability/logging.py` 已验证模式，确保容器/systemd stdout 必定打印单行合法 JSON，且不重复输出。
2. **上下文指标白名单字段补齐（`logging.py` & `usage.py`）**：
   - 在 `log_context_metric()` 读取 `config.get("metadata")` 时，安全提取 `project_id`、`thread_id`、`platform_trace_id`、`request_id`（限字符串且过受控长度与字符过滤，无内容泄漏风险），并允许调用方显式覆盖；`usage.py` 发出 `runtime.model_request.profile` 时同步传入上述身份字段（从 `self.identity` 或当前 `metadata` 中取）。

---

## 3. 影响评估与回滚策略

- **影响服务**：`runtime-service` 与 `platform-api`；不涉及数据库 Schema 变更与前端改动。
- **契约与兼容性**：`RuntimeDiagnostics`、`RunDiagnostics`、`TraceLogsResponse` 的对外字段结构、脱敏白名单与 ACL 规则保持不变。
- **回滚策略**：均属纯代码逻辑扩展；`TRACING_PROVIDER` 切回 `langfuse` 或移除新增适配后，原有逻辑无侵入回退；无迁移回滚风险。
