# 03 - 跨服务链路追踪规范

## 目标

设计并落地跨服务的分布式链路追踪标准，让一次用户请求从 platform-web 到 platform-api 到 runtime-service 到 interaction-data-service 全链路可追踪，并与 runtime-service 现有的 Langfuse 可观测体系打通。

## 当前问题

- `x-request-id` / `x-trace-id` 在 platform-api 文档中提到，但无格式规范、无传播规则
- runtime-service 有 Langfuse 追踪，但其 `trace_id` 与平台的 `x-request-id` 完全无关联
- IDS 写入时通过业务字段（`provenance`）传递 `thread_id/run_id`，无标准追踪头

## 方案设计

### 追踪头方案：W3C traceparent（主）+ x-request-id（辅）

**选型理由：**
- W3C TraceContext 是行业标准，OpenTelemetry 兼容
- Langfuse 支持从 traceparent 提取 trace_id，可直接关联
- x-request-id 保留作为简短的日志关联 ID（取 trace-id 的后 16 位）

**traceparent 格式：**
```
traceparent: 00-{trace-id-32hex}-{parent-id-16hex}-{flags-2hex}
```
示例：
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

**x-request-id 格式：**
- 取 trace-id 的后 16 位十六进制，便于日志快速关联
- 示例：`a3ce929d0e0e4736`

### 传播链

```
platform-web（发起请求）
    ↓  traceparent（如果没有，在 platform-api 生成）
platform-api（入口，生成或透传 traceparent）
    ↓  traceparent 透传 + x-request-id
runtime-service（LangGraph Agent Server）
    ↓  Langfuse 注入 trace_id（从 traceparent 提取）
    ↓  traceparent 透传
interaction-data-service（写入时携带 traceparent）
```

### 各服务职责

**platform-api（入口服务，负责生成）：**
- 若请求携带有效 traceparent → 透传，取其 trace-id 作为 x-request-id 后缀
- 若请求不携带 traceparent → 生成新的 traceparent，trace-id 用于本次请求全链路
- 所有下游 HTTP 调用透传 traceparent 和 x-request-id
- 错误响应的 `meta.trace_id` 中包含 trace-id

**runtime-service：**
- 从入站请求读取 traceparent
- 初始化 Langfuse 时注入 trace_id（从 traceparent 提取前 32 位）
- 调用 IDS 时透传 traceparent

**interaction-data-service：**
- 从入站请求读取 traceparent（可选，用于日志关联）
- 错误响应包含 trace_id（如果存在）

**platform-web：**
- 每次请求自动附加 traceparent（如果有）
- 从错误响应的 `meta.trace_id` 提取，用于用户反馈/支持

### Langfuse 打通方案

```python
# runtime-service 的 agent.py 中
from langfuse import Langfuse

def get_agent(config: RunnableConfig):
    traceparent = config.get("configurable", {}).get("traceparent")
    if traceparent:
        # 从 traceparent 提取 trace_id（版本00-之后的32位）
        trace_id = traceparent.split("-")[1]
        langfuse = Langfuse(trace_id=trace_id)
    # ...
```

这样 Langfuse 的 trace 与平台链路 trace 使用同一个 trace_id，可在 Langfuse UI 中直接通过 platform-api 日志里的 trace_id 找到对应的 Agent 执行记录。

## 任务拆分

### Task 3.1: 制定链路追踪规范文档
- **改动内容：** 创建 `docs/standards/trace-propagation.md`，包含追踪头格式、各服务职责、Langfuse 打通说明
- **代码位置：** `docs/standards/trace-propagation.md`（新建）
- **预期结果：** 有权威规范文档
- **验证项：** 文档覆盖所有服务的实现要求
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 3.2: platform-api 实现 traceparent 生成与透传
- **改动内容：** 在 FastAPI 中间件中实现：入口生成/透传 traceparent，注入 `request.state`，下游 HTTP 调用时透传
- **代码位置：** `apps/platform-api/src/platform_api/core/middleware/`（新建或扩展现有中间件）
- **预期结果：** 所有入站请求都有 traceparent，所有下游调用都携带 traceparent
- **验证项：** 单元测试中间件；手动验证 runtime-service 收到的请求包含正确的 traceparent
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 3.3: runtime-service 透传 traceparent 并注入 Langfuse
- **改动内容：** 从 Delegation JWT 或 HTTP header 读取 traceparent，注入 Langfuse trace_id，调用 IDS 时透传
- **代码位置：** `apps/runtime-service/src/runtime_service/` → 相关的 Agent 初始化或中间件代码
- **预期结果：** Langfuse trace 与平台 trace 使用同一 trace_id
- **验证项：** 执行一次完整 Agent run，在 Langfuse UI 中能通过 platform-api 日志的 trace_id 找到对应执行记录
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 3.4: interaction-data-service 接收并记录 traceparent
- **改动内容：** 接收入站 traceparent，写入日志，在错误响应的 meta 中包含 trace_id
- **代码位置：** `apps/interaction-data-service/app/` → 中间件或请求处理层
- **预期结果：** IDS 日志可通过 trace_id 与上游关联
- **验证项：** 写入请求的日志中包含 trace_id
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 3.5: platform-web 在 service 层透传 traceparent
- **改动内容：** 在 `src/services/` 的 HTTP 客户端中，自动将 traceparent 附加到请求头（如果存在）
- **代码位置：** `apps/platform-web/src/services/`（HTTP 请求基础层）
- **预期结果：** 前端发起的请求携带 traceparent，服务端可关联
- **验证项：** 浏览器 Network 面板中确认请求携带 traceparent header
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

## 验证要求与记录

### Final 验证
- [ ] 完整链路测试：一次 Chat 请求从 web → api → runtime → IDS，全链路 trace_id 一致
- [ ] Langfuse UI 可通过 trace_id 关联到对应 Agent 执行
- [ ] 错误响应中 meta.trace_id 字段存在且正确
- [ ] platform-api 日志和 runtime-service 日志使用同一 trace_id

### 验证记录
<!-- 实施后填写 -->

## 状态

规划中
