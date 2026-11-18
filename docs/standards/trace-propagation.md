---
status: active
last_verified: 2026-11-17
confidence: high
source_project: docs/projects/20261022-trace-to-logs-distributed-observability/verification.md
---

# 链路追踪传播规范

> **适用服务：** platform-api（生成方）、runtime-service（透传方）、platform-web（透传方）
> **验证证据：** API pytest 307 passed / 16 skipped；真实 R1-R6 链路通过；PG 查询性能中位 0.577ms；W3C traceparent 跨服务透传与日志打标单测 9 项 100% 通过（2026-10-22）

## 编号生成规则

| 字段 | 生成方式 | 说明 |
|---|---|---|
| `request_id` | `uuid.uuid4().hex`，32 位小写十六进制 | 每个进入 platform-api 的 HTTP 请求生成一次 |
| `trace_id` | 等于 `request_id`（本期） | 32 位 Hex，与 W3C traceparent 的 trace_id 强对齐 |
| `span_id` | 16 位小写十六进制随机 Hex | W3C Span 标识，API 与下游 Runtime 各自派生子 Span |
| `traceparent` | `00-{trace_id}-{span_id}-01` | 工业级 W3C TraceContext 标准透传头 |
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

## 平台助手与日志读取范围（2026-11-16）

平台助手分别记录助手Thread/Run与被诊断目标Thread/Run，不把目标Trace当当前用户授权。旧/api/v1/observability/traces/{trace_id}/logs已要求登录和项目范围；仅返回结构化project_id及Trace匹配的有界安全字段，新增partial/coverage，不再透传任意原始日志正文。没有Run时需明确项目日志调查授权，时间窗口最多24小时。

运行诊断若未配置追踪后端，返回disabled/not_configured；不猜platform_trace_id。模型Trace与平台Trace仍按原类型区分。关闭助手不恢复旧日志匿名访问。新增接口、旧页面迁移及本地验证见[助手交接](../projects/20261116-platform-assistant/frontend-handoff.md)和[验证](../projects/20261116-platform-assistant/verification.md)。本次只补读取范围，不新增追踪头或SSE事件；未验证生产Loki。

普通日志查询还逐条校验结构化thread_id的当前Thread ACL；按Run读取同时限定目标Thread/Run。客户端传播的Trace或自己的同Trace审计记录不是独立授权，缺资源关联仅供明确获准的项目日志调查者查看。

2026-11-17补充：首次读取与助手历史复核均按目标Thread的真实项目及当前成员/Thread ACL授权。证据scope.project_id表示助手会话项目，scope.target_project_id表示排查目标项目；跨项目本身不构成归属冲突。observed_at表示本次资料读取时间，data.run_time表示获准Run快照中的created_at/updated_at，不能拿读取时间冒充故障时间。

按Run默认查created_at前5分钟至updated_at后5分钟的日志，返回query_start/query_end。时间未知、无时区、逆序、扩展后超24小时或只提供一端时要求补充时间；显式窗口仍最多24小时。保留partial/coverage及原数量和字节边界，日志为空不证明无故障。合成时间/日志、当前权限和模型分层验证见[实施证据](../projects/20261116-platform-assistant/implementation/03-guide-and-diagnostics-optimization.md)，未代替真实Loki或生产采集验收。

2026-11-17真实排障复盘追加批准：Run已通过当前目标项目/Thread ACL且后端核实Run归属后，日志可按已验证平台Trace、诊断来源的execution_request_id、Run编号依次选择关联。该回退只改变候选搜索键；每条返回仍须有精确项目/Thread/Run、所选关联字段及时间范围，不接受模型指定请求编号，不扩大项目检索，不放宽旧Trace入口。correlation_type返回实际方式。诊断顶层request_id属于本次查询，不能作为旧执行关联；availability_scope明确当前查询端，不能推断历史采集。验证入口为[本轮任务](../projects/20261116-platform-assistant/tasks.md#t21把目标运行的持久失败状态提供给助手)，实际结果见verification的R01–R05。
