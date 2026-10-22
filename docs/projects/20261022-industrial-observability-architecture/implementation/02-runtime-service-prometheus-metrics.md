# Runtime Service 指标基础设施与 Prometheus /metrics 接入

## 改动时间
2026-10-22

## 相关任务
- Task 1.2: Runtime Service 指标基础设施改造
- Task 1.3: 单元测试覆盖与性能压力基准

## 改动文件
- `apps/runtime-service/pyproject.toml`
- `apps/runtime-service/src/runtime_service/observability/metrics.py` (新增)
- `apps/runtime-service/src/runtime_service/observability/__init__.py`
- `apps/runtime-service/src/runtime_service/observability/langfuse.py`
- `apps/runtime-service/src/runtime_service/webapp.py`
- `apps/runtime-service/tests/test_prometheus_metrics.py` (新增)

## 具体改动

### 1. 引入 prometheus-client 并创建 RuntimeMetricsRegistry
- **位置：** `runtime_service/observability/metrics.py`
- **指标定义：**
  - `runtime_agent_runs_total{graph_id, outcome}`: 记录 Graph 执行次数与最终结果分布（success/failed/interrupted）。
  - `runtime_agent_run_duration_seconds{graph_id}`: 直方图记录执行耗时（从 0.5s 到 300s 多梯度桶）。
  - `runtime_model_calls_total{provider, model, outcome}`: 记录大模型实际调用次数与成功/失败分布。
  - `runtime_loop_detection_tripped_total{code}`: 记录循环保护探针触发计数（tool_loop_approaching/tool_loop_reached）。
  - `runtime_sandbox_containers_active`: Gauge 记录当前活跃的 Docker 沙箱容器水位。
- **Fail-Soft：** 采集方法全量包裹异常隔离，任何异常仅记录 warning，绝不抛出异常阻断 Agent 执行。

### 2. 在 Langfuse 与诊断回调中联动指标埋点
- **位置：** `runtime_service/observability/langfuse.py`
- **改动理由：**
  - 在 `_RuntimeDiagnosticsCallback._finish()` 中直接记录 `runtime_metrics.record_agent_run()`，即使 Langfuse 未开启或上报失败，Prometheus 指标依然能准确记录。
  - 在 `_RuntimeDiagnosticsCallback.on_llm_end()` 中记录成功模型调用。
  - 在 `record_diagnostic_event()` 中，当捕获到 `runtime.model_call.failed` 和 `runtime.loop.transition` 时，自动同步打点到 `runtime_metrics`。

### 3. 在 FastAPI webapp 暴露 /metrics 路由
- **位置：** `runtime_service/webapp.py`
- **改动理由：**
  - 在全局根路径直接暴露 `GET /metrics` 端点，输出 OpenMetrics 纯文本数据流。
  - 该端点无需用户鉴权，供 Prometheus 探针定期内网抓取。

## 验证结果
执行命令：
`uv run pytest tests/test_prometheus_metrics.py tests/observability/test_langfuse.py`
结果：**33 passed (100% 绿灯)**。
基准性能测试表明：单次指标记录平均耗时低于 0.005ms（远优于 0.05ms 上限要求）。
