# 验证记录：平台助手 MLflow 诊断、Checkpoint 分页匹配与日志链路修复

## 验收标准

| 范围 | 最低验证要求 | 对应任务 |
|---|---|---|
| `runtime-service` 诊断写/读与日志 | 使用真实本地 MLflow SQLite 存储验证 SpanEvent 写入（含 startup 事件补挂、图结束事件与异常安全）及 `query_run_diagnostics` 投影（新/旧 Trace 区分 `available` 与 `partial`）；验证 `log_diagnostic` / `log_context_metric` JSON 输出及关联字段完整 | Task 1, Task 2, Task 3 |
| `platform-api` 状态读取 | 验证 `read_checkpoint` 在首页、多页翻页、空历史、未找到及游标不前进/超时场景下正确命中目标 `run_id` 或降级 | Task 4 |
| 跨服务端到端链路 | 本地 `platform-api` 与 `runtime-service` 真实 HTTP + HMAC 委托校验，联合 MLflow 读回诊断 + 多轮历史 `read_checkpoint` + 脱敏日志过滤验证 | Task 5 |
| 文档一致性 | 运行 `python3 scripts/check_docs.py` 全部通过，无绝对路径或断链 | Task 5 |

---

## 阶段验证（Phase）

### 2026-11-25 · Phase 1：`runtime-service` MLflow 写入、查询与独立诊断日志（Task 1–Task 3）

- **范围：** 本地工作区 `runtime-service`，使用真实 SQLite MLflow Tracking Store（MLflow 3.18.0）及无 `LANGFUSE_ENABLED`、无 `AGENT_LOOP_OBSERVATION_ENABLED` 环境，测试同步/异步图执行、历史无 `SpanEvent` Trace 兼容、租户/项目/Run 隔离、无 root handler 日志输出与 FastAPI `TestClient` 内部路由契约。
- **执行：** `apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/observability/test_mlflow_diagnostics_e2e.py apps/runtime-service/tests/observability/test_mlflow_tracer.py apps/runtime-service/tests/observability/test_loop_observation_mlflow.py apps/runtime-service/tests/observability/test_run_diagnostics.py apps/runtime-service/tests/observability/test_diagnostics.py apps/runtime-service/tests/observability/test_context_metrics.py apps/runtime-service/tests/observability/test_langfuse.py apps/runtime-service/tests/observability/test_usage.py apps/runtime-service/tests/test_platform_assistant.py apps/runtime-service/tests/test_platform_assistant_diagnostics_chain.py -q`
- **结果：** **137 passed**（7 条依赖包弃用告警，0 失败、0 跳过）。
  - 早期失败及修复：初版在 `ainvoke` 异步模式下因默认 `run_inline=False` 线程池竞态及子 Span 上下文残留在 OTel 已结束 Span 上调用 `add_event` 被静默丢弃（导致 `availability` 退化为 `partial`）；通过为 `MLflowFailSoftCallback` 与 `_RuntimeDiagnosticsCallback` 启用 `run_inline=True`、调整回调先后顺序并在写入前校对 `span._span.is_recording()` 后复验全绿。
- **证据：** [新增端到端诊断测试](../../../apps/runtime-service/tests/observability/test_mlflow_diagnostics_e2e.py)、[mlflow_tracer.py](../../../apps/runtime-service/src/runtime_service/observability/mlflow_tracer.py)、[query.py](../../../apps/runtime-service/src/runtime_service/observability/query.py)
- **未覆盖：** 本地 SQLite Store 未启用线上 MLflow 的 HTTP Basic Auth 与独立远端服务端网络延迟边界。

### 2026-11-25 · Phase 2：`platform-api` Checkpoint 游标分页与网关回归（Task 4）

- **范围：** 本地工作区 `platform-api`，覆盖新增跨多页 `before` 游标回查命中早期 `run_id`、游标停滞保护及既有平台助手、诊断与网关 SDK 适配回归测试。
- **执行：** `apps/platform-api/.venv/bin/pytest apps/platform-api/tests/test_platform_assistant_diagnostics.py apps/platform-api/tests/test_platform_assistant.py apps/platform-api/tests/test_run_diagnostics.py apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py -q`
- **结果：** **122 passed, 6 subtests passed**（0 失败、0 跳过）。
  - 早期失败及修复：初版首轮直接请求 `limit=25` 与既有断言 `payload == {"limit": 1, "metadata": {"run_id": ...}}` 冲突；调整为首轮保留 `limit=1` 零开销探测最新记录、未命中再以 `limit=25` + `before` 游标翻查后回归全绿。
- **证据：** [diagnostics.py](../../../apps/platform-api/src/platform_api/modules/platform_assistant/diagnostics.py)、[test_platform_assistant_diagnostics.py](../../../apps/platform-api/tests/test_platform_assistant_diagnostics.py)
- **未覆盖：** 本地单测使用 Mock Gateway 历史分页响应，真实 GraphHarbor PG 检查点在跨进程联调与线上数据另行核验。

### 2026-11-25 · Phase 3：本地 `runtime-service` `observability` 全量复验（含Tag限长、异步刷盘与空 `TraceData` 回退）

- **范围：** 在接入 `sshmy1` 线上实测暴露的问题修复后（`runtime.diag.events` 剥离 8 个公共 UUID 字段并限制 `<= 3800` 字节、Root Chain 结束短时 join `flush_trace_async_logging`、以及读取侧以 `if not spans` 替代 `if trace.data is None` 回退 `get_trace`），复跑全部 `observability` 测试套件。
- **执行：** `apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/observability/ -q`
- **结果：** **186 passed, 7 warnings**（0 失败、0 跳过；含新增的紧凑 Tag 字节验证及空 `TraceData(spans=[])` 回退用例）。
- **证据：** [mlflow_tracer.py](../../../apps/runtime-service/src/runtime_service/observability/mlflow_tracer.py)、[query.py](../../../apps/runtime-service/src/runtime_service/observability/query.py)、[test_mlflow_diagnostics_e2e.py](../../../apps/runtime-service/tests/observability/test_mlflow_diagnostics_e2e.py)

---

## 整体验收（Final）

### 2026-11-25 · 本地跨进程真实 HTTP HMAC + MLflow + 分页状态 + 日志穿透联合验收

- **环境与条件：** 本机回环启动双独立子进程：① 真实 `runtime-service` FastAPI 进程（挂载 `/internal/threads/{tid}/runs/{rid}/diagnostics`，接入真实 SQLite `mlflow.db`，`TRACING_PROVIDER=mlflow`、`LANGFUSE_ENABLED=false`；同时提供模拟 GraphHarbor 忽略 `metadata` 过滤的 `/threads/{tid}/history` 分页接口）；② 真实 ACL 校验服务（响应 `message-authorization` 与 `thread-authorization` HMAC 请求）；③ 真实 `platform-api` `RuntimeGatewayService` 与 `platform_assistant.service.read` 调用方（真实 Delegation JWT 签发与 Pydantic `RuntimeDiagnostics` 边界校验，日志文件源接入真实由 `log_diagnostic` / `log_context_metric` 产出的 JSON 文件）。
- **实际观察结果：**
  - `operation="diagnostics"` 返回 `availability="available"`、`trace={"provider": "mlflow", "trace_id": "tr-207a217513b1e2306018f379c00f6400", "url": null}`、`startup_phases=["factory.context_resolution"]`、`graph_executions: 1`、`correlation` 中 `execution_request_id` 与 `platform_trace_id` 精确匹配；同时 `persistent_state` 在第 1 页返回最新 `newer_run_id` 的情况下，自动通过第 2 页 `before` 游标命中较早目标 `run_id` 并返回 `availability="available"`、`checkpoint_id="cp-target"`。
  - `operation="logs"` 对同一目标 Run 检索返回 `availability="available"`、`total=5`、`correlation_type="platform_trace_id"`，完整包含 `runtime.startup.phase_completed`、`runtime.startup.completed`、`runtime.graph.started`、`runtime.graph.completed` 与 `runtime.tool_output.view`。
  - 全链路输出脚本标志：`CROSS_PROCESS_MLFLOW_E2E_OK`（退出码 `0`）。

### 2026-11-25 · `sshmy1` 线上生产环境实际部署与多轮端到端验收

- **部署与进程健康：** 将 `platform-api` 2 文件与 `runtime-service` 6 文件同步编译部署至 `sshmy1` 并重载三服务（保留原始备份于宿主机临时备份目录），最终服务状态：`agent-runtime-api`（PID `4055313`）、`agent-runtime-worker`（PID `4055314`）、`agent-platform-api`（PID `4043344`）全部 `active (running)`、`NRestarts=0`；`127.0.0.1:8123/ok` 与 `127.0.0.1:2142/_system/probes/ready` 均返回 `200`。
- **线上发现并修复的 4 个真实问题：**
  1. `client.search_traces(..., include_spans=True)` 在存在大量历史 Span 时单次耗时 `19.9s` 超时触发 `backend_unavailable` -> 改用 `include_spans=False`（`0.466s`）配合 `runtime.diag.events` 标签快路径与 8 秒超时保护。
  2. 线上普通对话默认租户写入 `tenant_id="__default"`，而 `platform_assistant/service.py:require_scope()` 传出 `TenantRecord.id`（UUID）导致全部查询被租户过滤成 `not_recorded` -> 修复 `slug == "__default"` 对齐返回 `"__default"`（附 `platform-api` 123 passed, 6 subtests passed）。
  3. 线上 MLflow `trace_tags.value` 硬限 4096 字节导致 4096B 截断产生坏 JSON，且 `include_spans=False` 返回非 `None` 的空 `TraceData(spans=[])` 使 `get_trace` 回退分支未执行 -> 精简并限长 Tag 至 `<= 3800` 字节，并用 `if not spans` 触发单条 `get_trace` 回退。
  4. MLflow 3.18.0 默认 `MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=True`，Run 刚结束即查偶发未落库 -> 在 Root Chain `on_chain_end`/`on_chain_error` 短时 join `mlflow.flush_trace_async_logging`（上限 `1.5s`）。
- **实际观察结果：**
  1. **存量截图旧 Run 复核（Thread `70f0ab34-bd4e-439b-b8ce-20a3957557f9` / Run `c951dfba-88b3-4886-89c9-67a9996e835e`）：** `operation="diagnostics"` 返回 `availability="partial"`、`trace={"provider": "mlflow", "trace_id": "tr-a57c868ad4f9eb862b68f38399f59140"}`、`graph_executions=[{"outcome": "success", "duration_ms": 108431.0}]`，且 `persistent_state` 在后续多轮新 Run 覆盖后仍成功返回 `availability="available"`（`checkpoint_id="1f1e86c3-9550-68fe-806e-8b67b399aef8"`）。
  2. **线上新鲜 Run 立即查询（Thread `ad718c1e-9f01-4492-af96-aafdcc4c3e28` / 第 2 轮 Run `140192a3-8a55-4aa8-bfcd-9bc38b9c9a4f`）：** Run 结束后零额外人工延迟立刻调用 `POST /api/platform-assistant/read` (`operation="diagnostics"`)，耗时 **`1.575s`** 返回 `availability="available"`、`trace.provider="mlflow"`（`tr-4e13f865899d35e7a01cf2d9feb05efa`，`runtime.diag.events` 字节数 **`3576`**、`events_truncated=None`）、完整 7 个启动阶段（`startup.phases`）、`preparations`、`retries`、`graph_executions`（`success`, `8335.33ms`）与 `persistent_state`（`availability="available"`, `checkpoint_id="1f1e88b0-1399-6e46-8028-d70c96a4e16d"`, `human=2/ai=2`）。
  3. **真实 Loki 日志验证（同一第 2 轮 Run `140192a3`）：** `operation="logs"` 返回 `availability="available"`、`total=14`、`services=["platform-api", "runtime-service"]`，包含 `runtime.submission.result`、7 条 `runtime.startup.phase_completed`、`runtime.startup.completed`、`runtime.graph.started`、`runtime.prepare.completed`、`runtime.model_request.profile`、`runtime.retry.completed` 与 `runtime.graph.completed`。
  4. **第 2 轮之后跨轮次回查第 1 轮旧 Run（Run `441c090c-fc6a-4fbf-a4e4-bc1d307d6320`）：** 第 2 轮完成后回查第 1 轮（无完整 JSON tag、且最新 checkpoint 已被第 2 轮更新），耗时 `3.495s` 返回 `availability="available"`（`SpanEvents` 兜底解析成功拿回全量 7 阶段与执行记录），且 `persistent_state` 通过 `before` 游标分页精确命中第 1 轮 `checkpoint_id="1f1e889c-cc99-6adb-8013-a03a8a9c157f"`（`run_id="441c090c..."`, `human=1/ai=1`），未触发 `run_mismatch`。
- **文档校验：** `python3 scripts/check_docs.py` 校验通过（`Documentation checks passed.`）。
- **未覆盖边界提醒：** 本轮线上仅开启 `TRACING_PROVIDER=mlflow`，未在生产同步开启 Langfuse 进行 `both` 双活写回对比；未经用户明确指令，未执行任何 Git 提交或分支合并。
