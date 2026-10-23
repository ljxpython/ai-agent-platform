# W3C TraceContext 标准透传与全服务结构化日志打标

## 改动时间
2026-10-22

## 相关任务
- Task 1.1: W3C TraceContext 标准透传实现
- Task 1.2: API 与 Runtime 结构化日志打标对齐

## 改动文件
- `apps/platform-api/src/platform_api/core/context/models.py`
- `apps/platform-api/src/platform_api/core/context/runtime.py`
- `apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py`
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`
- `apps/platform-api/src/platform_api/core/observability/logging.py`
- `apps/platform-api/tests/test_trace_propagation.py`
- `apps/runtime-service/src/runtime_service/observability/context.py`
- `apps/runtime-service/src/runtime_service/observability/logging.py`
- `apps/runtime-service/src/runtime_service/observability/diagnostics.py`
- `apps/runtime-service/src/runtime_service/webapp.py`
- `apps/runtime-service/tests/test_trace_propagation.py`

## 具体改动

### 1. W3C traceparent 标准请求头解析与生成
- **位置：** `platform_api/core/context/runtime.py` 与 `runtime_service/observability/context.py`
- **契约规格：** `traceparent: 00-{trace_id}-{span_id}-01`。
- **网关生成：** Platform API 请求进入时，若未携带外部 `traceparent`，则自动根据 32 位 Hex `trace_id` 与生成的 16 位 Hex `span_id` 组装标准 `traceparent`；若存在合法 `traceparent`，则自动继承 `trace_id` 并分配本地新 `span_id`。
- **向下透传：** 在 `LangGraphRuntimeClient._headers()` 中自动提取当前上下文的 `traceparent`、`x-request-id`、`x-trace-id` 并注入 HTTP 发送头。
- **引擎继承：** Runtime Service 挂载 `traceparent_middleware`，自动解析上游父 Span 并建立当前的 `RuntimeTraceContext`，在响应头中完整回显。

### 2. 统一日志打标与 LogRecord 注入
- **位置：**
  - `platform_api/core/observability/logging.py` (`PlatformTraceLogFilter`)
  - `runtime_service/observability/logging.py` (`RuntimeTraceLogFilter`, `format_log_line`)
- **改动理由：** 为所有流向标准日志输出的行打上 `service`、`trace_id`、`span_id` 标记，确保日志流进入 Loki 或文件后能够被单 `trace_id` 联合查询完整捕获。

### 3. Langfuse 根 TraceID 强绑定
- **位置：** `runtime_service/observability/diagnostics.py` (`trace_id_for`)
- **改动理由：** 优先继承上游的 `platform_trace_id` 或 HTTP 上下文 `trace_id`，杜绝过去基于 Hash 生成独立 TraceID 导致的网关与大模型链路 Trace 割裂问题。

## 验证结果
1. `apps/platform-api/tests/test_trace_propagation.py`：**4 passed (100% 绿灯)**。
2. `apps/runtime-service/tests/test_trace_propagation.py`：**5 passed (100% 绿灯)**。
3. 跨服务 Header 传递、父子 Span 分配与响应头回显均符合规范。
