---
status: active
last_verified: 2026-09-27
confidence: high
source_project: docs/projects/20260926-trace-context-propagation/verification.md
---

# 链路追踪传播规范

> **适用服务：** platform-api（生成方）、runtime-service（透传方）、platform-web（透传方）
> **验证证据：** API pytest 307 passed / 16 skipped；真实 R1-R6 链路通过；PG 查询性能中位 0.577ms

## 编号生成规则

| 字段 | 生成方式 | 说明 |
|---|---|---|
| `request_id` | `uuid.uuid4().hex`，32 位小写十六进制 | 每个进入 platform-api 的 HTTP 请求生成一次 |
| `trace_id` | 等于 `request_id`（本期） | 不解释为 OTel trace ID |
| `platform_trace_id` | JWT / 下游 metadata 字段名 | 取当前 `context.request.trace_id` |
| `submission_id` | 已有 `run_requests.id` | 同一幂等提交复用；同 `submission_id` 不同 `request_id` = 同一提交的不同 HTTP 尝试 |

**隔离保证：**
- 编号不进入幂等摘要、`context_hash`、授权判定或命令正文
- `ContextVar` 的 set/reset 置于完整 try/finally（覆盖正常返回、普通异常、取消）
- 忽略外部 `x-request-id` / `x-trace-id` 输入，不回显、不记录外部原值

## 审计查询扩展参数

| 参数 | 格式 | 限制 |
|---|---|---|
| `request_id` | 32 位小写十六进制精确匹配 | 单独查无时间窗口限制 |
| `submission_id` | UUID | 需强制 created_from/created_to，窗口 ≤ 7 天 |
| `thread_id` | — | 需强制时间窗口 |
| `run_id` | — | 匹配 metadata 的 run_id / target_run_id / parent_run_id（OR） |

## SSE 连接追踪事件

**提交关系事件（`runtime.submission`）：**

| 事件 | 触发时机 |
|---|---|
| `runtime.submission.attempt` | reserve 成功后、上游调用前 |
| `runtime.submission.result.outcome` | `accepted` / `deduplicated` / `rejected` / `unknown` |
| `runtime.cancel.result.outcome` | `accepted` / `rejected` / `unknown` |

> ACK 不代表 Run 已取消或已终止

**SSE 连接事件（`runtime.stream`）：**

| 规则 | 说明 |
|---|---|
| `opened` | 成功发送 http.response.start 后才记，握手失败不记 |
| `closed` | 对已 opened 的连接最多一条 |
| `close_reason` 枚举 | `eof` / `client_disconnect` / `upstream_error` / `frame_rejected` / `closed` / `unknown` |
| 覆盖保护 | `frame_rejected` 一经确定，finally 的通用原因不得覆盖 |

## 审计 metadata 白名单字段

```
platform_trace_id, submission_id, thread_id, run_id, parent_run_id,
target_run_id, interrupt_key, operation, outcome, stream_kind,
close_reason, reused_submission, correlation_version=1（整数）
```

## 已发 200 后的审计状态

已发送 200 后出现异常或断连：审计 `status_code` 保留实际 200，不改记 499/500；传输结果另记 `result` / `close_reason`。
