# open-swe vs 当前 Runtime：Agent 工业级能力差距分析

> **阅读说明**：本文档从「非业务、非前端」的 Agent 基础能力角度，逐项对比 open-swe 和当前项目（runtime-service）的实现差距。每项按「优先级 / 当前状态 / 参考位置 / 如何补」四格表述，看完即可动手。

---

## 目录

1. [模型调用稳定性 — Model Reliability](#1-模型调用稳定性)
2. [工具调用容错 — Tool Error Handling](#2-工具调用容错)
3. [上下文窗口与历史压缩 — Context Management](#3-上下文窗口管理)
4. [运行生命周期超时治理 — Run Lifecycle Timeout](#4-运行生命周期超时治理)
5. [消息队列运行中注入 — In-flight Message Injection](#5-消息队列运行中注入)
6. [运行完成通知与失败回调 — Run Completion Webhook](#6-运行完成通知与失败回调)
7. [可观测性与追踪 — Observability & Tracing](#7-可观测性与追踪)
8. [Sandbox 容错与电路熔断 — Sandbox Resilience](#8-sandbox-容错与电路熔断)
9. [错误分类体系 — Error Classification](#9-错误分类体系)
10. [消息修复与幂等性 — Message Repair & Idempotency](#10-消息修复与幂等性)
11. [工具输入自动修正 — Tool Input Sanitization](#11-工具输入自动修正)
12. [工具动态加载 — Dynamic Tool Loading](#12-工具动态加载)
13. [运行启动阶段追踪 — Startup Phase Tracing](#13-运行启动阶段追踪)
14. [任务预算与步骤限制告警 — Step Limit Notification](#14-任务预算与步骤限制告警)
15. [运行配置幂等防护 — Prepare Run Idempotency](#15-运行配置幂等防护)
16. [工具安全守卫 — Tool Safety Guards](#16-工具安全守卫)
17. [模型智能选路 — Model Selection Routing](#17-模型智能选路)
18. [Token/Cost 跟踪 — Usage Tracking](#18-tokenscost-跟踪)
19. [工具结果稳定排序 — Stable Tool Order](#19-工具结果稳定排序)
20. [运行取消与中断 — Run Cancellation](#20-运行取消与中断)
21. [任务级重试策略 — Task-Level Retry](#21-任务级重试策略)
22. [结构化消息信封 — Message Envelopes](#22-结构化消息信封)
23. [Plan Mode 工具权限状态机 — Plan Mode](#23-plan-mode-工具权限状态机)
24. [后台非阻塞任务调度 — Background Task Scheduling](#24-后台非阻塞任务调度)
25. [URL 安全与 SSRF 防护 — URL Safety & SSRF Guard](#25-url-安全与-ssrf-防护)
26. [【当前项目已超越】Docker 深度沙箱隔离](#26-当前项目已超越docker-深度沙箱隔离)
27. [【当前项目已超越】LangGraph BubbleUp 补丁](#27-当前项目已超越langgraph-bubbleup-补丁)

---

## 1. 模型调用稳定性

### 优先级：🔴 高（生产级必须）

### 当前状态

`ModelCallTimeoutMiddleware` **已有**，超时超出取消。
但**缺失**：

- 主/备模型自动 fallback（provider A 挂了换 provider B）
- provider 特定错误分类（429/529/overloaded）驱动的 retry 策略
- Transient error 检测列表（APIConnectionError / APITimeoutError / ReadTimeout 等）
- backoff jitter 抖动退避

**现有文件**：[`middlewares/model_call_timeout.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/middlewares/model_call_timeout.py)

### open-swe 实现

**文件**：[`agent/middleware/model_fallback.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/model_fallback.py)

```python
# 核心逻辑：主/备轮询，backoff jitter
DEFAULT_BACKOFF_SCHEDULE: tuple[float, ...] = (0.0, 5.0, 15.0, 30.0, 45.0)

for attempt in range(total_attempts):
    use_fallback = attempt % 2 == 1  # 奇数次用备模型
    try:
        return await handler(attempt_request)
    except Exception as exc:
        if not _should_fallback(exc):
            raise
        delay = self._backoff_schedule[attempt]
        delay += random.uniform(0, delay * 0.25)  # ±25% jitter
        await asyncio.sleep(delay)

# 全部失败后：返回用户可见的 outage message，而不是崩溃
if self._surface_outage_message:
    return AIMessage(content=MODEL_OUTAGE_MESSAGE)
```

可 fallback 的错误类型：

```python
_TRANSIENT_EXCEPTIONS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    TimeoutError,
)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 529})
```

### 如何补

**在 `src/runtime_service/middlewares/` 下新增 `model_fallback.py`：**

1. 参考 open-swe 的 `ModelFallbackMiddleware` 实现
2. 接受 `fallback_model`（可选）+ `backoff_schedule` 参数
3. 若配置了 `AGENT_FALLBACK_MODEL_ID` env，在 `runtime/modeling.py` 里初始化第二个 model 实例
4. 在 agent factory 里将 `ModelFallbackMiddleware` 插到 `ModelCallTimeoutMiddleware` **之后**（让 timeout 先变成异常，再由 fallback 捕获）
5. 全部失败时返回 `AIMessage(content="...")` 而不是 raise，避免运行变 error 状态

---

## 2. 工具调用容错

### 优先级：🔴 高

### 当前状态

**没有** `ToolErrorMiddleware`。工具如果 raise，直接让整个 agent run crash。目前工具代码内部各自 try/except，但没有统一兜底。

### open-swe 实现

**文件**：[`agent/middleware/tool_error_handler.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/tool_error_handler.py)

```python
class ToolErrorMiddleware(OpenSWEMiddleware):
    async def awrap_tool_call(self, request, handler):
        try:
            return await handler(request)
        except Exception as e:
            if is_transient_sandbox_error(e):
                # 瞬时错误：返回结构化 ToolMessage，让 LLM 自动重试
                return _transient_sandbox_tool_message(e, request)
            if not _is_sandbox_unreachable(e):
                # 普通错误：返回结构化 ToolMessage，不崩溃
                return _generic_error_tool_message(e, request)
            # Sandbox 彻底挂了：发通知用户，然后 re-raise
            await post_sandbox_unreachable_notification(config, ...)
            raise  # 只有不可恢复才 crash
```

错误 ToolMessage 格式：

```python
{
    "status": "error",
    "error": "...",
    "error_type": "ExceptionClassName",
    "name": "tool_name"
}
```

### 如何补

**在 `middlewares/` 下新增 `tool_error_handler.py`：**

1. 实现 `ToolErrorMiddleware(AgentMiddleware)` 重写 `awrap_tool_call`
2. 所有异常转为 `ToolMessage(status="error", content=json.dumps(...))`
3. 加到 agent 全局 middleware 链，位置在工具执行相关 middleware 的最外层
4. workspace 不可达时（已有 `.runtime/` 文件系统的场景）走 re-raise 路径

---

## 3. 上下文窗口管理

### 优先级：🔴 高（长任务必然撞到）

### 当前状态

**无**。当前没有任何对话历史压缩机制。长会话最终会命中 `context_length_exceeded`，目前靠 model 报错来"发现"问题，没有主动管理。

虽然项目已有 `断流恢复解耦与历史快照按需懒加载`（`docs/projects/20261002-chat-history-lazy-loading`），但那是**前端侧懒加载**，不是 agent 侧的消息压缩。

### open-swe 实现

**文件**：[`agent/middleware/conversation_offloading.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/conversation_offloading.py)

基于 `deepagents.middleware.summarization.SummarizationMiddleware`，核心行为：

```python
class ConversationOffloadingMiddleware(SummarizationMiddleware):
    def _should_summarize(self, messages, total_tokens) -> bool:
        # 超过 token 阈值时自动触发摘要
        return _manual.get() or super()._should_summarize(messages, total_tokens)

    async def _acreate_summary(self, messages_to_summarize):
        # 用一个 hidden model 生成摘要（不流式，不影响用户体验）
        self._status("started")
        return await super()._acreate_summary(messages_to_summarize)
```

特点：

- 摘要 model 打 `nostream` + `langsmith:hidden` tag，不输出到用户流
- 支持手动触发（`manual=True`）和自动触发
- 摘要文件写入 sandbox 文件系统持久化，下次启动可还原
- 向 state 写入 `conversation_offloading` 事件，前端可监听进度

### 如何补

**在 `middlewares/` 下新增 `conversation_offloading.py`：**

1. 依赖 `deepagents.middleware.summarization.SummarizationMiddleware`（已在 deepagents 包内）
2. 实现封装：摘要 model 用 `nostream` tag，不影响用户流
3. 配置 `AGENT_CONTEXT_OFFLOAD_THRESHOLD_TOKENS`（e.g. 80000）作为触发阈值
4. 接收 `offload_conversation: bool` 在 RunConfig 里，支持按 run 控制是否压缩
5. 压缩后向 state 写 event，前端 SSE 监听并提示用户「历史已压缩」

---

## 4. 运行生命周期超时治理

### 优先级：🟡 中（长任务场景需要）

### 当前状态

`ModelCallTimeoutMiddleware` 管的是**单次模型调用**超时（默认 600s）。**没有**：

- 整体 run 的 wall-clock 超时
- 快到超时时告诉 LLM「请收尾」的优雅关机

### open-swe 实现

**文件**：[`agent/middleware/timeout_wrapup.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/timeout_wrapup.py)

```python
_DEFAULT_TIMEOUT_SECONDS = 45 * 60  # 45 分钟

class TimeoutWrapupMiddleware(OpenSWEMiddleware):
    def _should_wrapup(self) -> bool:
        # monotonic clock，避免时区/NTP 干扰
        return (time.monotonic() - self._start) >= self._timeout_seconds

    async def awrap_model_call(self, request, handler):
        # 即将超时：把 wrapup 指令注入 system prompt
        if self._should_wrapup():
            request = request.override(
                system_message=SystemMessage(content=f"{original}\n\n{WRAPUP_INSTRUCTION}")
            )
        return await handler(request)
```

`timeout-wrapup.md` 里的 prompt 是类似「你的时间快到了，请立即保存进度并生成最终报告」的指令。

### 如何补

**在 `middlewares/` 下新增 `timeout_wrapup.py`：**

1. 记录 run 开始时间（`abefore_agent` 钩子里赋值）
2. 每次 `awrap_model_call` 检查是否超过阈值
3. 超过则在 system prompt 末尾注入收尾指令（一个 `prompts/timeout-wrapup.md` 文件）
4. 环境变量 `AGENT_RUN_TIMEOUT_SECONDS`（默认 2700 = 45min）控制
5. 与平台层 LangGraph 的 run timeout 配合（platform 层强杀，这里优雅退出）

---

## 5. 消息队列运行中注入

### 优先级：🟡 中（已有但功能差距较大）

### 当前状态

**有** `MessageQueueMiddleware`，已实现基本的 FIFO 注入和权限验证。

**缺失 vs open-swe**：

- 没有 `pending_autofix_event`（后台 PR babysit 事件聚合）
- 没有 dashboard handoff 特殊消息格式识别
- 没有多媒体（图片 URL）异步解析后注入
- 没有 `injected_dynamic_context_hashes` 去重（同一 context 注入多次）

**现有文件**：[`middlewares/message_queue.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/middlewares/message_queue.py)

### open-swe 实现

**文件**：[`agent/middleware/check_message_queue.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/check_message_queue.py)

核心增量特性：

```python
# 1. 聚合 autofix 事件（PR babysit）
pending_autofix = await _consume_pending_autofix_event(store, thread_id)

# 2. 识别 dashboard_handoff 特殊消息类型
if _is_dashboard_queued_message(content):
    handoff = build_input_messages(DASHBOARD_HANDOFF_BODY, ...)

# 3. 多媒体消息（图片 URL）→ 解析成 content blocks
if has_images:
    resolved_model_id = await _resolve_thread_model_id(thread_id)
    blocks = await _build_blocks_from_payload(content, model_id=resolved_model_id)

# 4. 动态 context hash 去重（避免重复注入相同 context）
injected = visible_dynamic_context_hashes(state)
```

### 如何补

优先级较低，当前已能基本工作。若有「运行中追加消息」场景不满足时，补：

1. `autofix_event` 聚合：后台 PR 监控产生事件 → 写 store → 下次 model call 前注入
2. context hash 去重：避免同一 dynamic context 在同一次 run 里重复注入两次

---

## 6. 运行完成通知与失败回调

### 优先级：🔴 高（生产可靠性）

### 当前状态

**没有** run-completion webhook 处理。当前运行失败（error/timeout）时，用户得不到任何通知，run 安静地死掉。

### open-swe 实现

**文件**：[`agent/completion.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/completion.py)

```python
# 每个 dispatch 的 run 都携带 webhook 地址
# run 结束后平台 POST 到 /webhooks/run-complete

_TERMINAL_FAILURE_STATUSES = frozenset({"error", "timeout"})

# 失败时发送用户可见的友好消息
_REASON_TEXT = {
    "provider_overloaded": "model provider was overloaded and never recovered",
    "provider_rate_limited": "model provider rate-limited it",
    "context_too_long": "conversation outgrew the model's context window",
    "sandbox_unreachable": "run lost its sandbox",
    "step_limit": "run hit its step limit",
}

# HMAC 验证避免伪造
def verify_run_complete_token(token: str | None) -> bool:
    return token is not None and hmac.compare_digest(token, secret)
```

关键：

1. 失败原因通过 `LAST_MODEL_ERROR_KEY` 从 thread metadata 读取（`ModelErrorMiddleware` 写入）
2. 同一 run_id 只发一次通知（幂等）
3. 不同渠道（Slack/GitHub/Linear）分别发送

### 如何补

**在 `runtime-service` 或 `platform-api` 添加 run completion webhook handler：**

1. LangGraph platform 配置 run webhook URL
2. 实现 `POST /internal/run-complete` endpoint，接受 `{status, thread_id, run_id, error_type}`
3. status 为 `error/timeout` 时：
   - 从 thread metadata 读取 `last_model_error`（需要先有 `ModelErrorMiddleware`）
   - 组装友好文案，通过 SSE/通知发给用户（platform-api → platform-web）
4. HMAC 共享密钥验证，防伪造（`RUN_COMPLETE_WEBHOOK_SECRET`）

---

## 7. 可观测性与追踪

### 优先级：🟡 中

### 当前状态

**有**：

- `OTelDiagnosticsCallback` + `langfuse` 集成（`observability/otel.py`, `observability/langfuse.py`）
- `_RuntimeDiagnosticsCallback`（记录 run 开始/完成/duration/tool_error）
- 结构化日志（已使用 `structlog`）

**缺失 vs open-swe**：

- 没有 `ModelErrorMiddleware`（不记录 model 报错原因到 thread metadata）
- 没有 `error_tracking_fields()`（结构化 Datadog error 格式）
- 没有 `classify_exception()`（将 provider 异常分类为 `provider_rate_limited` / `context_too_long` 等）
- 没有 startup phase 追踪（factory/准备阶段的 span 无法附到 run trace 里）
- `LangSmith` trace 回写（在 thread metadata 留 trace URL）

**现有文件**：[`observability/langfuse.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/observability/langfuse.py), [`observability/otel.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/observability/otel.py)

### open-swe 实现

**文件**：[`agent/utils/errors.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/utils/errors.py), [`agent/middleware/model_errors.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/model_errors.py)

```python
# 1. 异常分类（感知 provider 状态码 + body）
def classify_exception(exc) -> str | None:
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    if status == 429 or "rate_limit" in haystack: return "provider_rate_limited"
    if status == 529 or "overloaded" in haystack: return "provider_overloaded"
    if "context_length_exceeded" in haystack: return "context_too_long"

# 2. Datadog 标准格式
def error_tracking_fields(exc) -> dict:
    return {"error": {
        "kind": type(exc).__name__,
        "message": str(exc),
        "stack": "".join(traceback.format_exception(exc))
    }}

# 3. ModelErrorMiddleware：记录错误分类到 thread metadata
class ModelErrorMiddleware(OpenSWEMiddleware):
    async def awrap_model_call(self, request, handler):
        try:
            return await handler(request)
        except Exception as exc:
            code = classify_exception(exc)
            logger.exception("Model call failed", extra={
                **error_tracking_fields(exc),
                "model_call_failure": {"model": model, "code": code}
            })
            # 关键：把分类写进 thread metadata，供 completion webhook 读
            await get_client().threads.update(thread_id, metadata={
                LAST_MODEL_ERROR_KEY: {"run_id": run_id, "code": code}
            })
            raise
```

### 如何补

**在 `runtime/errors.py` 或新建 `observability/error_classifier.py`：**

1. 添加 `classify_exception(exc)` 函数，映射 status code + body 关键词 → 分类字符串
2. 添加 `error_tracking_fields(exc)` 生成 Datadog 标准格式
3. 新建 `middlewares/model_errors.py`：实现 `ModelErrorMiddleware`
   - 捕获 model call 异常 → 分类 → `logger.exception(...)` → 写 thread metadata → re-raise
4. 在 agent factory 里把 `ModelErrorMiddleware` 放在 `ModelFallbackMiddleware` **内侧**（先记录，再 fallback）

---

## 8. Sandbox 容错与电路熔断

### 优先级：🟡 中（有 workspace 运行时才相关）

### 当前状态

当前项目的 workspace 是本地文件系统（`.runtime/` 目录），没有云端 sandbox。但如果将来接入 E2B/Daytona/Modal，需要此能力。

现有工具调用没有 sandbox 层的 transient retry。

### open-swe 实现

**文件**：[`agent/sandboxes/retry.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/sandboxes/retry.py), [`agent/middleware/sandbox_circuit_breaker.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/sandbox_circuit_breaker.py)

```python
# 指数退避，最多 4 次重试（仅 gateway 5xx，命令未开始执行）
MAX_TRANSIENT_ATTEMPTS = 4
_BASE_BACKOFF = 0.5
_MAX_BACKOFF = 8.0

async def retry_transient_sandbox_errors(operation, *, description, max_attempts=4):
    while True:
        attempt += 1
        try:
            return await operation()
        except Exception as exc:
            if attempt >= max_attempts or not is_transient_sandbox_error(exc):
                raise
            delay = _compute_backoff(attempt)  # exponential + ±20% jitter
            await asyncio.sleep(delay)

# 熔断：sandbox 彻底不可达时，通知用户并终止 run
async def post_sandbox_unreachable_notification(config, sandbox_id=None):
    # 向 Slack/GitHub/Linear 发通知
    # "sandbox stopped responding, please retrigger"
```

### 如何补

**对当前项目的 workspace/execution.py 添加 transient retry 包装：**

1. 识别「本地进程执行」失败的瞬时错误（如临时文件锁、权限瞬时不可用）
2. 对 workspace 执行操作加 `retry_transient_errors` 装饰器（`asyncio.sleep` + `max_attempts`）
3. 彻底失败时：通过 SSE 发送用户提示（不是 crash，是优雅报告）

---

## 9. 错误分类体系

### 优先级：🟡 中

### 当前状态

`runtime/errors.py` 有 `RuntimeErrorBase` / `RuntimeResolutionError` / `RuntimeAuthError`，这些是**运行时配置类**错误，不是 provider/tool 层错误分类。

**没有**跨层错误分类（provider 429 → `rate_limited`；tool crash → `tool_error`；sandbox → `sandbox_unreachable`）。

### open-swe 实现

统一错误码体系（`agent/utils/errors.py`）：

```python
_ERROR_TYPE_CODES = {
    "RateLimitError": "provider_rate_limited",
    "OverloadedError": "provider_overloaded",
    "APIConnectionError": "provider_unavailable",
    "APITimeoutError": "provider_timeout",
    "ModelCallTimeoutError": "provider_timeout",
    "GraphRecursionError": "step_limit",
    "SandboxConnectionError": "sandbox_unreachable",
}
```

这套码一路传到：

- thread metadata（供 completion webhook 读）
- 结构化日志（供 Datadog/Grafana 聚合）
- 用户通知（翻译为人类可读文案）

### 如何补

**在 `runtime/errors.py` 扩展：**

```python
PROVIDER_ERROR_CODES = {
    429: "provider_rate_limited",
    529: "provider_overloaded",
    503: "provider_unavailable",
    504: "provider_timeout",
}

def classify_model_error(exc: Exception) -> str | None:
    status = getattr(exc, "status_code", None)
    return PROVIDER_ERROR_CODES.get(status) or _classify_by_body(exc)
```

然后在 `ModelErrorMiddleware` 里调用，并写入 thread metadata。

---

## 10. 消息修复与幂等性

### 优先级：🟡 中

### 当前状态

当前没有「孤儿工具调用」修复机制。如果 agent run 中断（网络断开、进程重启），部分 tool call 可能产生了 AIMessage（含 tool_calls）但没有对应的 ToolMessage，下次恢复时 LLM 会收到格式错误的历史，导致报错或幻觉。

### open-swe 实现

**文件**：[`agent/middleware/repair_orphaned_tool_calls.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/repair_orphaned_tool_calls.py)

```python
class RepairOrphanedToolCallsMiddleware(OpenSWEMiddleware):
    async def awrap_model_call(self, request, handler):
        repaired = _repair_messages(request.messages)
        if repaired is not None:
            request.messages[:] = repaired  # 就地修复，不改消息 ID
        return await handler(request)

def _repair_messages(messages):
    satisfied = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    inserted = 0
    for message in messages:
        for call_id, name in _iter_tool_calls(message):
            if call_id not in satisfied:
                repaired.append(_synthetic_tool_message(call_id, name))
                inserted += 1
    if not inserted:
        return None  # 不需要修复
```

当前项目里已有 `DearFlow Agent` 的畸形 ToolCall 自动缝合（`2026-10` 改动里提到），但是封装在业务层。**建议提取为通用 middleware。**

### 如何补

**在 `middlewares/` 下新增 `repair_orphaned_tool_calls.py`：**

1. 检查每次 model call 前的 messages 历史
2. 找 AIMessage 中有 tool_call 但缺少对应 ToolMessage 的情况
3. 插入合成的 `ToolMessage(status="error", content="[interrupted]", tool_call_id=...)`
4. 加到 middleware 链，位置在 model call 最内侧（第一个 awrap_model_call）

---

## 11. 工具输入自动修正

### 优先级：🟢 低

### 当前状态

无自动修正。LLM 偶尔生成 `'1, 80'` 这种字符串给整数参数，直接导致 Pydantic 校验失败 → 报错 → 浪费一次 LLM 调用。

### open-swe 实现

**文件**：[`agent/middleware/sanitize_tool_inputs.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/sanitize_tool_inputs.py)

```python
def _coerce_int(value: object) -> int | None:
    if isinstance(value, str):
        match = re.match(r"\s*(\d+)", value)  # 提取前导数字
        if match:
            return int(match.group(1))
```

对 `read_file` 工具的 `offset` / `limit` 字段自动修正。

### 如何补

如果当前有 workspace 文件读取类工具（read_file / read_lines 等），加此 middleware。**不紧急，但值得加**（避免无谓 LLM retry）。

---

## 12. 工具动态加载

### 优先级：🟢 低（有集成扩展场景时才需要）

### 当前状态

工具在 agent factory 时静态加载，运行中不能动态启用/禁用工具集。

### open-swe 实现

**文件**：[`agent/middleware/dynamic_tools.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/dynamic_tools.py)

```python
class DynamicIntegrationToolsMiddleware(OpenSWEMiddleware):
    # LLM 可以调 load_integration_tools 工具来启用某个集成
    # 之后每次 model call 前，把已加载的集成工具注入 tools 列表
    async def awrap_model_call(self, request, handler):
        loaded = self._loaded_names(request.state)
        tools = [tool for name in loaded if (tool := self._tool(name)) is not None]
        return await handler(request.override(tools=[*request.tools, *tools]))
```

### 如何补

当前项目 MCP 工具已有动态加载机制，**这个场景基本覆盖了**。若未来需要 agent 运行中动态启用 Integration（如 Notion/Linear），参考此模式。

---

## 13. 运行启动阶段追踪

### 优先级：🟢 低（完整 tracing 需要时）

### 当前状态

Factory 初始化（`prepare_run`、sandbox 准备等）发生在 LangGraph trace span 建立**之前**，这段时间在 trace 里是黑盒。

### open-swe 实现

**文件**：[`agent/utils/startup_trace.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/utils/startup_trace.py)

```python
# 1. Factory 阶段用 aphase() context manager 记录时间
async with aphase(thread_id, "sandbox_warmup", sandbox_id=sandbox_id):
    await initialize_sandbox(...)

# 2. 第一次 model call 前，把缓存的 phases 回写到 trace
def flush_phases(thread_id: str | None) -> None:
    parent = _parent_run_tree()  # 获取当前 run 的 LangSmith root span
    for phase in ordered:
        child = parent.create_child(name=phase.name, ...)  # 补录为子 span
        child.post()
        child.end(outputs={"elapsed_ms": phase.elapsed_ms})
        child.patch()
```

### 如何补

若需要完整追踪初始化耗时（模型加载、DB 连接、MCP 初始化等），在 `observability/` 里实现类似的 phase buffer + flush 机制。**不紧急。**

---

## 14. 任务预算与步骤限制告警

### 优先级：🟡 中

### 当前状态

LangGraph 的 `recursion_limit` 会在超步时抛 `GraphRecursionError`，但当前没有：

- 到达步骤限制时的用户通知
- 超步前的「快要到限制了」告警

### open-swe 实现

**文件**：[`agent/middleware/notify_step_limit.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/notify_step_limit.py)

```python
@after_agent
async def notify_step_limit_reached(state, runtime):
    last_msg = state["messages"][-1]
    # 检测 ModelCallLimitMiddleware 写入的标记文本
    if "Model call limits exceeded" in content:
        await post_slack_thread_reply(channel_id, thread_ts, warning(
            "Open SWE reached its maximum step limit and had to stop. "
            "You can retry with a more focused request, or ask to continue."
        ))
```

还有 `TimeoutWrapupMiddleware`（见 #4）：接近 run timeout 时注入 prompt 告知 LLM 收尾，比硬中断更优雅。

### 如何补

**在 `middlewares/` 新增 `notify_step_limit.py`：**

1. `aafter_agent` 钩子检查最后一条消息是否含步骤限制标记
2. 如果是，通过 SSE stream writer 推送用户提示
3. 配合 `TimeoutWrapupMiddleware`（#4）做整体时间管理

---

## 15. 运行配置幂等防护

### 优先级：🟡 中

### 当前状态

每次 agent run 都会执行 `prepare` 阶段（加载模型参数、渲染 system prompt 等），但如果一次 run 中途 crash 重试，`prepare` 会重新执行，可能产生副作用（重复申请 token、重复初始化 sandbox 等）。

### open-swe 实现

**文件**：[`agent/middleware/prepare_run.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/prepare_run.py)

```python
class BasePrepareRunMiddleware(OpenSWEMiddleware):
    async def abefore_agent(self, state, runtime):
        fingerprint = self._prepare_fingerprint(state, runtime)
        # 指纹：上一条消息 hash + middleware 类名 + 配置 hash
        if (
            state.get("run_prepared")
            and state.get("run_prepared_for") == fingerprint
        ):
            return None  # 幂等：跳过

        updates = await self._prepare(state, runtime)
        return {"run_prepared": True, "run_prepared_for": fingerprint, **updates}
```

LangGraph 会把 `run_prepared_for` checkpoint，同一 invocation 的重试自动跳过；新 invocation 的指纹不同，正常重新 prepare。

### 如何补

**在 agent factory 的 `prepare_run` 逻辑里加幂等检查：**

1. 在 state 里存 `run_prepared: bool` + `run_prepared_for: str`（fingerprint）
2. fingerprint 由 `hash(last_message_id + config_hash)` 计算
3. `abefore_agent` 检查是否已 prepared：已 prepared 且 fingerprint 一致 → 直接跳过
4. 所有 prepare 副作用操作（申请 token、读取配置等）移到 `_prepare()` 方法内

---

## 16. 工具安全守卫

### 优先级：🟡 中（有生产安全需要时）

### 当前状态

当前 `runtime/tool_access.py` 有工具权限 ACL，控制哪些工具可被哪个 agent 用。但没有：

- 工具调用参数级别的内容守卫（如 PR 创建必须走官方 tool）
- Shell 命令执行里的危险操作检测

### open-swe 实现

**文件**：[`agent/middleware/pr_creation_guard.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/pr_creation_guard.py), [`agent/middleware/workflow_push_guard.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/workflow_push_guard.py)

```python
# pr_creation_guard：阻止通过 shell/curl 绕过官方 open_pull_request 工具
_GITHUB_PULLS_URL = re.compile(r"https://api\.github\.com/repos/[^/\s]+/[^/\s]+/pulls/?")
_BLOCK_ERROR = "New pull requests must be opened with the open_pull_request tool..."

# workflow_push_guard：推送 .github/workflows 前要求人工审批
class WorkflowPushGuardMiddleware:
    async def awrap_tool_call(self, request, handler):
        if _is_workflow_push(request):
            if not await workflow_push_approved(thread_id):
                return ToolMessage(content="Workflow push requires approval", status="error")
```

### 如何补

**如果有类似场景**（如防止 agent 直接修改数据库、强制通过指定 API 操作某类资源），参考 `pr_creation_guard.py` 模式：

1. `awrap_tool_call` 拦截 shell 工具调用
2. 正则检测危险命令或 URL
3. 返回 `ToolMessage(status="error", content="[blocked]")` 而不是执行

---

## 17. 模型智能选路

### 优先级：🟢 低

### 当前状态

当前 `runtime/modeling.py` 根据 RunConfig 固定选模型，没有基于任务复杂度的动态选路。

### open-swe 实现

**文件**：[`agent/middleware/model_selection.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/model_selection.py)

```python
Route = Literal["fast", "balanced", "performance"]

class ModelSelectionMiddleware(OpenSWEMiddleware):
    # 用一个小型 classifier 模型分析任务复杂度
    # → 选 fast/balanced/performance 三档模型
    # 结果缓存在 state["model_route"] 中，本次 run 不重复分类
```

### 如何补

当前平台已有 BYOK + 项目模型选择，动态选路不紧急。若未来做多档模型计费，可参考此模式。

---

## 18. Token/Cost 跟踪

### 优先级：🟡 中

### 当前状态

`observability/langfuse.py` 里有 `_RuntimeDiagnosticsCallback.on_llm_end` 记录 `total_tokens`，但：

- 没有跨 invocation 聚合（session 级别累加）
- 没有 input/output token 拆分
- 没有 cache token 扣除（cache_read 不应计费）
- 没有 invocation 级别 cost 计算和持久化

### open-swe 实现

**文件**：[`agent/middleware/record_run_usage.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/record_run_usage.py), [`agent/utils/run_usage.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/utils/run_usage.py)

```python
# run_usage.py：精确 token 计算
def _tokens(usage: Any) -> _TokenCounts | None:
    total_tokens = input_tokens + output_tokens
    # 关键：减去 cache_read，避免重复计费
    cache_read = input_details.get("cache_read") or 0
    return _TokenCounts(total_tokens=max(total_tokens - cache_read, 0))

# RecordRunUsageMiddleware：每次 model call 后打 invocation_id，run 结束时聚合
class RecordRunUsageMiddleware:
    async def aafter_agent(self, state, runtime):
        await finalize_agent_invocation_usage(
            invocation_id=cfg.invocation_id,
            thread_id=cfg.thread_id,
            state=dict(state),  # 从 messages 聚合所有 token 消耗
        )
```

### 如何补

**在 `middlewares/` 新增 `record_run_usage.py`：**

1. `awrap_model_call` 后给 AIMessage 打 `invocation_id` tag
2. `aafter_agent` 时：遍历本次 run 的所有 AIMessage，按 invocation_id 聚合
3. 计算：input_tokens + output_tokens - cache_read_tokens = 实际计费 tokens
4. 持久化到 DB（`platform-api` 的计费记录表）或 Langfuse

---

## 总结优先级排序

| 能力                       | 优先级 | 预估工作量 | 当前缺口       |
| -------------------------- | ------ | ---------- | -------------- |
| 1. 模型 fallback + backoff | 🔴 高   | 1-2天      | 无             |
| 2. 工具调用统一兜底        | 🔴 高   | 0.5天      | 无             |
| 6. run 完成失败通知        | 🔴 高   | 2-3天      | 无             |
| 3. 上下文压缩              | 🔴 高   | 1-2天      | 无             |
| 9. 错误分类体系            | 🟡 中   | 0.5天      | 部分有         |
| 7. ModelErrorMiddleware    | 🟡 中   | 0.5天      | 无             |
| 4. 运行超时收尾            | 🟡 中   | 0.5天      | 无             |
| 10. 孤儿工具调用修复       | 🟡 中   | 0.5天      | 无（业务层有） |
| 14. 步骤限制告警           | 🟡 中   | 0.5天      | 无             |
| 15. prepare 幂等防护       | 🟡 中   | 1天        | 无             |
| 18. Token/Cost 精确跟踪    | 🟡 中   | 1天        | 部分有         |
| 5. 消息注入增强            | 🟡 中   | 1天        | 部分有         |
| 8. Sandbox 电路熔断        | 🟡 中   | 看场景     | 无             |
| 11. 工具输入自动修正       | 🟢 低   | 0.5天      | 无             |
| 13. 启动阶段追踪           | 🟢 低   | 1天        | 无             |
| 12. 动态工具加载           | 🟢 低   | —          | MCP已覆盖      |
| 16. 工具安全守卫           | 🟡 中   | 看场景     | ACL已有        |
| 17. 模型智能选路           | 🟢 低   | —          | BYOK已有选模型 |

---

## 建议实施顺序（最小可行防线）

**Phase 1（1周，生产必备）：**

- `ToolErrorMiddleware`（防止工具报错炸掉整个 run）
- `ModelFallbackMiddleware`（provider 挂了切备用）
- `ModelErrorMiddleware` + `classify_exception`（记录失败原因）
- Run completion webhook handler（用户知道 run 失败了）

**Phase 2（1周，长任务稳定性）：**

- `ConversationOffloadingMiddleware`（防 context 溢出）
- `TimeoutWrapupMiddleware`（整体 run 优雅超时）
- `RepairOrphanedToolCallsMiddleware`（恢复后历史完整）
- 步骤限制 notify（达到 recursion_limit 用户知道）

**Phase 3（按需）：**

- prepare 幂等防护
- Token/Cost 精确聚合
- Startup phase tracing
- 工具安全守卫（pr_creation_guard 类）

---

## 19. 工具结果稳定排序

### 优先级：🟡 中（有并行工具调用 + 使用 Anthropic Prompt Caching 时必须）

### 当前状态

当前项目没有对并行工具调用结果做排序处理。LangGraph 异步调度下，多个并行 tool call 的 ToolMessage 按**完成时间**先后写入 state，顺序是不确定的。

**影响**：Anthropic/OpenAI 的 Prompt Cache 依赖**前缀字节完全匹配**，乱序直接导致缓存全失效，Token 费用飙升。

### open-swe 实现

**文件**：[`agent/middleware/stable_tool_order.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/stable_tool_order.py)

```python
class StableToolResultOrderMiddleware(OpenSWEMiddleware):
    """在模型调用前，将相邻 ToolMessage block 按父 AIMessage.tool_calls 的初始下发顺序重排。"""

    async def awrap_model_call(self, request, handler):
        sorted_messages = _sort_tool_results(request.messages)
        if sorted_messages is not None:
            request = request.override(messages=sorted_messages)
        return await handler(request)

# 找到每个 tool_call_id 在 AIMessage.tool_calls 中的原始位置
# 然后对其后紧跟的 ToolMessage block 按该顺序重排
sorted_block = sorted(block,
    key=lambda result, positions=positions: positions.get(
        getattr(result, "tool_call_id", None) or "", len(positions)
    ))
```

### 如何补

**在 `middlewares/` 下新增 `stable_tool_order.py`：**

1. `awrap_model_call` 中遍历 messages，找到每个 ToolMessage block（AIMessage 之后连续的 ToolMessage 序列）
2. 按该 AIMessage 的 `tool_calls` 字段中 `id` 出现的顺序，对 block 内 ToolMessage 重排
3. 有变更则 `request.override(messages=sorted)`，无变更直接透传
4. 接入时机：插在 middleware 链最内侧，model call 前最后一个

**收益**：Anthropic Prompt Cache 命中率提升到理论最大值，在并行工具调用场景（如多文件读取）可显著降低 Token 成本。

---

## 20. 运行取消与中断

### 优先级：🟡 中

### 当前状态

当前项目依赖 LangGraph platform 层的 `run.cancel()` 强制终止，但：

- 没有**用户主动触发停止**的业务流程（用户无法在 run 进行中通知 agent「停，我改变主意了」）
- 取消后没有**总结当前状态**给用户的能力（run 就静默死掉了）
- `workspace/execution.py` 里 Docker 容器取消有 `asyncio.shield` 保护清理逻辑（**这个已有**）

### open-swe 实现

**文件**：[`agent/slack/stop.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/slack/stop.py)

```python
# 用户触发停止（Slack 表情 / 指令）→ 优雅中断，而非强杀
run_ids = await _active_run_ids(client, thread_id)
if run_ids:
    await client.runs.cancel_many(
        thread_id=thread_id,
        run_ids=run_ids,
        action="interrupt",  # 优雅中断：等当前工具调用结束
    )
# 清理队列中的待处理任务（避免取消后继续注入）
await _clear_deferred_work(client, thread_id)
# 写入状态标记
await client.threads.update(thread_id, metadata={
    "latest_run_status": "interrupted",
    "stop_requested_at_ms": int(datetime.now(UTC).timestamp() * 1000),
})
# 调度一个「状态摘要小 run」告诉用户当前进度
await dispatch_agent_run(thread_id, _stop_summary_prompt(state), ...)
```

### 如何补

**在 `platform-api` 新增 cancel endpoint：**

1. `POST /threads/{thread_id}/cancel` endpoint，接受用户取消请求
2. 调用 LangGraph `runs.cancel_many(action="interrupt")`（优雅，非强杀）
3. 清理 `message_queue` 中该 thread 的待处理消息
4. 写 thread metadata 标记 `stop_requested_at_ms`
5. （可选）dispatch 一个「摘要小 run」让 LLM 生成「已停止，当前进度是...」通知用户

---

## 21. 任务级重试策略

### 优先级：🟡 中

### 当前状态

当前项目没有 LangGraph dispatch 层面的 retry policy。如果一个 run 因 provider 限流（429）失败，整个 run 就挂了，没有自动重试。

### open-swe 实现

**文件**：[`agent/middleware/task_retry.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/task_retry.py)

```python
# 定义哪些 run-level 异常可以被平台层自动重试
_RETRY_HTTP_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})
_TRANSIENT_ERROR_NAMES = frozenset({
    "APIConnectionError", "APITimeoutError", "ConnectTimeout",
    "ModelCallTimeoutError", "ReadTimeout", "TimeoutException", "TransportError",
})

def task_retry_on(exc: Exception) -> bool:
    """返回 True 代表此异常可以重试整个 run。"""
    status = _status_code(exc)
    if isinstance(status, int) and (status in _RETRY_HTTP_STATUS_CODES or status >= 500):
        return True
    return exc.__class__.__name__ in _TRANSIENT_ERROR_NAMES

def task_on_failure(exc: Exception) -> str:
    """不可重试时，把错误序列化为 JSON 返给上层 LLM，而非崩溃。"""
    code = classify_exception(exc)
    return json.dumps({"error": code or "unknown_error", "message": str(exc)})
```

还有**自主唤醒防死循环**（`schedule_thread_wakeup.py`）：

```python
_MAX_WAKEUPS_BETWEEN_USER_MESSAGES = 10  # 两次用户消息之间最多 10 次自主唤醒
# 超过则熔断，防止 Agent 陷入无限自唤醒循环
```

### 如何补

**在 LangGraph dispatch 配置中：**

1. 所有 dispatch 的 run 上配置 `retry_policy`：将 `task_retry_on` 作为判断函数传入
2. 在 graph 入口将不可重试错误序列化为 ToolMessage JSON 而非 raise（对应 `task_on_failure`）
3. 如有定时唤醒工具，加计数器限制（`_MAX_WAKEUPS_BETWEEN_USER_MESSAGES`），防止 Agent 无限自唤醒

---

## 22. 结构化消息信封

### 优先级：🟢 低（有多 surface / 多 sender 场景时才需要）

### 当前状态

当前 `message_queue.py` 直接把 payload 包成 `HumanMessage(content=row["payload"])`，没有结构化标记发送者身份、消息来源 surface 或去重 hash。

### open-swe 实现

**文件**：[`agent/input_messages.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/input_messages.py)

```xml
<!-- 结构化 XML 信封，而非裸字符串 -->
<input-message sender="user_slack_id" surface="slack" kind="human">
  <content>请帮我重构这个函数</content>
</input-message>

<!-- 动态 context 注入，带 hash 去重，避免同一 context 在一次 run 里重复注入 -->
<dynamic-context kind="repo_info" id="repo_abc" hash="sha256:abc123">
  owner: acme, repo: api-server
</dynamic-context>
```

核心特性：

- `trust="untrusted"` 标记用户输入中的非受信字段（如 PR 标题，防 prompt injection）
- `visible_dynamic_context_hashes()` 感知历史压缩截断点，被压缩丢失的 context 自动重新注入
- sender_id 校验防止 XML 注入

### 如何补

**当前不紧急**。若未来接入多渠道（Web/API/定时任务/第三方平台），需要此机制区分消息来源并做去重。实现路径：

1. 在 `messaging/` 下定义 `MessageEnvelope` Pydantic 模型（sender, surface, kind, content, hash）
2. `MessageQueueMiddleware` 读消息时解析信封而非裸 payload
3. 注入 `dynamic-context` 时计算 SHA-256 hash，避免同一 context 在一次 run 里重复注入

---

## 23. Plan Mode 工具权限状态机

### 优先级：🟡 中（有「先规划后执行」场景时必须）

### 当前状态

当前项目的 HITL 审批通过 `interrupt_on` 控制具体工具是否需要审批，但没有「整体规划模式」概念：即先让 Agent 只做调研/规划，人类审批计划后再放开写代码的权限。

### open-swe 实现

**文件**：[`agent/middleware/plan_mode.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/middleware/plan_mode.py)

```python
class PlanModeMiddleware(OpenSWEMiddleware):
    """当 state['plan_mode'] == True 时，动态裁剪掉所有破坏性工具。"""

    def _filter(self, request: ModelRequest) -> ModelRequest:
        if not self._active(request):  # plan_mode 未激活
            return request
        # 剥离：PR 创建、代码提交、子 Agent 委托、环境变更等破坏性工具
        filtered = [t for t in request.tools if _tool_name(t) not in self._excluded]
        return request.override(tools=filtered)
```

状态转移：

```
enter_plan_mode() ──→ plan_mode=True ──→ [只读调研 + 写草案到 /workspace/plans/]
                                                ↓
                                     approve_plan()（人类审批）
                                                ↓
                        plan_mode=False ──→ [完整工具权限恢复，开始执行]
```

### 如何补

**在现有 HITL 审批机制基础上扩展：**

1. 在 `AgentState` 加 `plan_mode: bool` 字段
2. 新建 `enter_plan_mode` 工具（LLM 自主调用以进入规划模式）
3. 新建 `approve_plan` 工具（平台审批通过后调用，重置 `plan_mode=False`）
4. 在 middleware 链加 `PlanModeMiddleware`，`awrap_model_call` 时按 state 动态过滤工具列表
5. Plan 模式下允许写 `/workspace/plans/` 但禁止写代码文件和其他破坏性操作

---

## 24. 后台非阻塞任务调度

### 优先级：🟢 低（有长耗时 shell 命令场景时需要）

### 当前状态

当前所有工具调用都是同步等待的，无法启动一个长耗时命令（如编译、运行测试套件、等待预览部署）后继续让 LLM 做其他任务，只能傻等着。

### open-swe 实现

**文件**：[`agent/tools/background_execute.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/tools/background_execute.py), [`agent/background_tasks.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/background_tasks.py)

```python
# 1. 工具：在沙箱里用独立进程组启动命令（非阻塞，立即返回 task_id）
process = await asyncio.create_subprocess_shell(
    command,
    start_new_session=True,  # 独立进程组，父进程退出不影响它
)
# 原子写入状态（tmp → 正式文件）
state.json.tmp → state.json

# 2. Cron 监控：每分钟检查一次，全程不唤醒 LLM
async def monitor_background_tasks(thread_id):
    tasks = await _list_tasks(backend)
    for task in terminal_tasks:
        if not await _claim(backend, task_id):  # 原子领用，mkdir 防重复
            continue
        await dispatch_agent_run(thread_id, _notification(task))  # 完成才唤醒

# 3. 日志 Head-Tail 环形截断，最大 1MB
MAX_LOG_BYTES = 1 * 1024 * 1024
```

### 如何补

**当前项目如有长耗时 workspace 命令需求（如跑测试、构建预览），参考此模式：**

1. `background_execute` 工具：在 workspace 启动独立进程，立即返回 `task_id`
2. 状态文件原子写入：`task_status.json.tmp → task_status.json`
3. 注册 LangGraph scheduler cron（每分钟）检测任务完成状态，完成后 dispatch 新 run 通知 Agent
4. 原子领用机制（`mkdir notify.claim`）防止多副本重复通知

---

## 25. URL 安全与 SSRF 防护

### 优先级：🟡 中（当前已有基础版，可补强）

### 当前状态

当前 `services/dearflow_agent/tools/search.py` 里已有 `public_url()` 函数：

- ✅ scheme 白名单（仅 http/https）
- ✅ 私有 IP 过滤（`not address.is_global`）
- ✅ localhost 域名过滤
- ❌ 无 DNS Pinning（可被 DNS Rebinding 绕过）
- ❌ 无跨域重定向时的 header 脱敏

### open-swe 额外实现

**文件**：[`agent/utils/url_safety.py`](file:///Users/lijiaxin/PyCharmMiscProject/research/open-swe/agent/utils/url_safety.py)

```python
# DNS Pinning：解析所有 DNS 结果，任一为私有 IP 则拒绝（防 DNS Rebinding）
for addr_info in socket.getaddrinfo(hostname, port):
    ip = ipaddress.ip_address(addr_info[4][0])
    # IPv4-mapped IPv6（::ffff:10.0.0.1）也要提取内层 IPv4 判断
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_global:
        return False, f"URL resolves to blocked address: {ip}"

# 跨域重定向时剥离 Authorization / Cookie header
```

### 如何补

**在现有 `public_url()` 基础上补充：**

1. `socket.getaddrinfo()` 解析所有 DNS 结果，任一为私有 IP 则拒绝
2. 处理 IPv4-mapped IPv6 地址（`::ffff:10.0.0.1`）
3. 跨域 HTTP 重定向时自动剥离 `Authorization` / `Cookie` header

---

## 26. 【当前项目已超越】Docker 深度沙箱隔离

### 状态：✅ 当前项目实现远超 open-swe

当前项目的 [`workspace/execution.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/workspace/execution.py) 实现了 **11 维度**的 Docker 安全参数：

| 参数                               | 防御目标                                      |
| ---------------------------------- | --------------------------------------------- |
| `--network=none`                   | 完全断网，切断数据外发和反弹 Shell            |
| `--read-only`                      | 容器根文件系统只读                            |
| `--cap-drop=ALL`                   | 丢弃所有 Linux Capabilities                   |
| `--security-opt=no-new-privileges` | 禁用 SUID/SGID 提权                           |
| `--user uid:gid`                   | 以宿主机普通用户运行，非 root                 |
| `--pids-limit=64`                  | 进程配额上限 64，免疫 Fork Bomb               |
| `--memory=256m`                    | 内存上限，防 OOM 拖垮宿主机                   |
| `--cpus=1`                         | CPU 配额限制                                  |
| `--ulimit fsize=8MB`               | 单文件写入大小硬限制                          |
| `--tmpfs /tmp:size=16m`            | 独立内存临时盘，不落磁盘                      |
| 精细挂载隔离                       | `/workspace/work` 读写，其余只读，skills 只读 |

还有 `backend.py` **文件系统路径守卫**：所有写操作强制限制在 `/workspace/work/`，拦截 `..` 路径穿越。

open-swe 的 sandbox 是云端虚拟机（langsmith/e2b/daytona），**没有**这套本地 Docker 细粒度隔离参数。

**结论：无需改动，当前已是最佳实践，应作为其他 Agent 沙箱设计的参考基准。**

---

## 27. 【当前项目已超越】LangGraph BubbleUp 补丁

### 状态：✅ 当前项目独有，open-swe 没有

当前项目的 [`patches.py`](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/patches.py) 包含了一个关键的 LangGraph 底层修复：

```python
def _patch_stream_tool_call_handler() -> None:
    """
    修复 LangGraph ToolNode 将 GraphBubbleUp（即 GraphInterrupt）
    误判为 tool-error 并向前端推送错误事件的 LangGraph bug。

    GraphBubbleUp 是控制流中断信号（如 HITL 审批 interrupt），
    不是工具执行失败，不应该触发 tool-error 事件。
    """
    orig_error = StreamToolCallHandler._error

    def _patched_error(self, error, *, run_id):
        if isinstance(error, GraphBubbleUp):
            # 这是 interrupt，不是错误：直接重置 writer，不推送 tool-error 事件
            info = self._run_to_call.pop(run_id, None)
            if info is not None:
                _, _, token = info
                self._reset_writer(token)
            return
        return orig_error(self, error, run_id=run_id)

    StreamToolCallHandler._error = _patched_error
    StreamToolCallHandler._bubble_up_patched = True
```

这个补丁解决了 HITL `interrupt()` 场景下前端会收到虚假 `tool-error` 事件的问题。open-swe 没有使用 LangGraph HITL interrupt，所以没遇到这个 bug，也没有此修复。

**结论：保留，持续关注 LangGraph 上游是否 fix 此 bug 后可安全移除。**

---

## 完整能力矩阵（subagent 深度报告版）

| #    | 能力                      | open-swe                | 当前项目                      | 优先级 | 预估工作量 |
| ---- | ------------------------- | ----------------------- | ----------------------------- | ------ | ---------- |
| 1    | 模型 fallback + backoff   | ✅ 完整                  | ❌ 无（仅 timeout）            | 🔴 高   | 1-2天      |
| 2    | 工具调用统一兜底          | ✅ 完整                  | ⚠️ 工具级各自做                | 🔴 高   | 0.5天      |
| 3    | 上下文压缩卸载            | ✅ 完整                  | ❌ 无                          | 🔴 高   | 1-2天      |
| 4    | 运行超时优雅收尾          | ✅ 完整                  | ❌ 无                          | 🟡 中   | 0.5天      |
| 5    | 消息队列注入              | ✅ 完整                  | ✅ 已有（含权限验证）          | —      | —          |
| 6    | run 完成失败通知          | ✅ 完整                  | ❌ 无                          | 🔴 高   | 2-3天      |
| 7    | 可观测性（Langfuse+OTel） | ✅ 完整                  | ✅ 已有（Fail-Soft）           | —      | —          |
| 7+   | ModelErrorMiddleware      | ✅ 完整                  | ❌ 无                          | 🟡 中   | 0.5天      |
| 8    | Sandbox 电路熔断通知      | ✅ 完整                  | ⚠️ 仅本地Docker                | 🟡 中   | 看场景     |
| 9    | 错误分类体系              | ✅ 完整                  | ⚠️ 仅配置层错误                | 🟡 中   | 0.5天      |
| 10   | 孤儿工具调用修复          | ✅ 完整                  | ✅ 已在RuntimeConfigMiddleware | —      | —          |
| 11   | 工具输入自动修正          | ✅ 完整                  | ❌ 无                          | 🟢 低   | 0.5天      |
| 12   | 动态工具加载              | ✅ 完整                  | ✅ MCP已覆盖                   | —      | —          |
| 13   | 启动阶段追踪重放          | ✅ 完整                  | ❌ 无                          | 🟢 低   | 1天        |
| 14   | 步骤限制告警通知          | ✅ 完整                  | ⚠️ 有限制无用户通知            | 🟡 中   | 0.5天      |
| 15   | prepare 幂等防护          | ✅ 完整                  | ❌ 无                          | 🟡 中   | 1天        |
| 16   | 工具安全守卫（shell级）   | ✅ 完整                  | ✅ 有ACL（工具级）             | 🟡 中   | 看场景     |
| 17   | 模型动态选路              | ✅ 完整                  | ⚠️ 静态选择                    | 🟢 低   | —          |
| 18   | Token/Cost 精确跟踪       | ✅ 完整（含cache扣除）   | ⚠️ 仅基础计数                  | 🟡 中   | 1天        |
| 19   | 工具结果稳定排序          | ✅ 完整                  | ❌ 无                          | 🟡 中   | 0.5天      |
| 20   | 运行取消优雅中断          | ✅ 完整                  | ⚠️ 依赖平台强杀                | 🟡 中   | 1天        |
| 21   | 任务级 retry policy       | ✅ 完整                  | ❌ 无                          | 🟡 中   | 0.5天      |
| 22   | 结构化消息信封            | ✅ 完整                  | ❌ 无                          | 🟢 低   | 1天        |
| 23   | Plan Mode 状态机          | ✅ 完整                  | ❌ 无（有HITL但不同）          | 🟡 中   | 1-2天      |
| 24   | 后台非阻塞任务调度        | ✅ 完整                  | ❌ 无                          | 🟢 低   | 2-3天      |
| 25   | URL安全/SSRF防护          | ✅ DNS Pinning+Rebinding | ✅ 已有基础版                  | 🟡 中   | 0.5天      |
| 26   | Docker深度沙箱隔离        | ⚠️ 云VM，无此参数        | **✅ 超越open-swe**            | —      | —          |
| 27   | LangGraph BubbleUp补丁    | ❌ 无                    | **✅ 独有**                    | —      | —          |

---

## 建议实施顺序（最终版）

**Phase 1（约 1 周，生产必备防线）：**

- `ToolErrorMiddleware` — 工具报错不崩整个 run，转为 ToolMessage(error) 让 LLM 自愈
- `ModelFallbackMiddleware` — provider 挂了切备用模型，带 jitter backoff
- `ModelErrorMiddleware` + `classify_exception` — 记录失败根因到 thread metadata
- Run completion webhook handler — 让用户知道 run 失败了及原因
- 任务级 `retry_policy` 配置 — dispatch 层 429/5xx 自动重试

**Phase 2（约 1 周，长任务稳定性）：**

- `ConversationOffloadingMiddleware` — 防 context 溢出，自动压缩历史
- `TimeoutWrapupMiddleware` — 整体 run 到时限后 LLM 优雅收尾而非强杀
- 步骤限制 notify — 达到 recursion_limit 通知用户，而非静默结束
- `StableToolOrderMiddleware` — Prompt Cache 命中率提升（有并行工具调用时）
- 运行取消优雅中断 — 用户能主动停止并收到进度总结

**Phase 3（按需，精细化治理）：**

- prepare 幂等防护
- Token/Cost 精确聚合（cache_read 扣除、invocation 级别持久化）
- Plan Mode 状态机（有「先规划后执行」业务场景时）
- URL 安全 DNS Pinning 补全
- Startup phase tracing（完整链路可观测性）
- 任务级 retry_policy（当前瞬时失败靠 ModelFallback 兜底已够用）

**YAGNI — 现阶段不建议搞：**

- 结构化消息信封（当前单渠道，改造收益低于成本）
- 后台非阻塞任务调度（当前无长耗时 shell 场景）
- 模型动态选路（BYOK 已满足选模型需求）
- 自主唤醒防死循环（当前无定时唤醒工具）
