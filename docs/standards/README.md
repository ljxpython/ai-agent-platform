# 跨服务规范健康表

> AI 处理跨服务改动时，先读本页确认置信度，再按任务读具体标准文件。

## 置信度说明

| 置信度 | 条件 | AI 行为 |
|---|---|---|
| 🟢 high | last_verified < 60 天 | 可直接参考 |
| 🟡 medium | 60–180 天，或状态为 draft/blocked | 参考，需核对代码是否已超前 |
| 🔴 low | > 180 天 | 视为过期，以代码为准，不作约束 |

## 规范状态总览

| 规范 | 文件 | 状态 | last_verified | 置信度 | 源专项 |
|---|---|---|---|---|---|
| Worktree 开发与资源隔离 | [worktree-development.md](worktree-development.md) | active | 2026-10-10 | high | [Worktree 本地栈专项](../projects/20261010-worktree-local-stack/README.md) |
| 错误响应 Envelope | [error-envelope.md](error-envelope.md) | active | 2026-10-09 | 🟢 high | [20260926-error-response-contract](../projects/20260926-error-response-contract/README.md) · [执行预算安全码](../projects/20261007-agent-execution-budget/verification.md) · [Stop 错误映射](../projects/20261007-agent-run-cancellation/verification.md) · [Workspace 执行保护](../projects/20261007-agent-workspace-resilience/README.md) · [后台任务错误](../projects/20261009-agent-generic-production-capabilities/verification.md) |
| 链路追踪传播 | [trace-propagation.md](trace-propagation.md) | active | 2026-09-27 | 🟢 high | [20260926-trace-context-propagation](../projects/20260926-trace-context-propagation/README.md) |
| Delegation JWT Schema | [delegation-jwt.md](delegation-jwt.md) | draft | 2026-10-09 | 🟡 medium | [Delegation 专项](../projects/20260926-delegation-jwt-contract/README.md) · [diagnostics-read](../projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md) · [usage-read](../projects/20261007-agent-usage-cost-governance/03-platform-cost-contract.md) · [Stop 精确委托](../projects/20261007-agent-run-cancellation/verification.md) · [后台三 operation](../projects/20261009-agent-generic-production-capabilities/verification.md) |
| SSE 事件格式契约 | [sse-event.md](sse-event.md) | draft | 2026-10-09 | 🟡 medium | [SSE 专项](../projects/20260926-sse-event-contract/README.md) · [执行错误投影](../projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md) · [执行预算 custom](../projects/20261007-agent-execution-budget/frontend-handoff.md) · [Workspace 错误与 tasks 脱敏](../projects/20261007-agent-workspace-resilience/README.md) · [后台完成 Run 接续](../projects/20261009-agent-generic-production-capabilities/frontend-handoff.md) |

## 未完成项

- **delegation-jwt（draft）**：34 项 operation；`diagnostics-read`、`usage-read`、会话 Stop 自定义 scope/固定回执例外及后台三 operation 已增补隔离证据。后台 lost-ACK 只读回查 B01 仍阻塞正式启用；`suggestions-generate` 与 cron 保持独立证据。消息内部原生 Run 回查源码已修复，现役链路尚未验证，待 [message-run-read-delegation](../projects/20260927-message-run-read-delegation/README.md) 专项部署后补验
- **sse-event（draft）**：帧安全、SDK 重试、会话池、410 降级规则已验（S1–S10）；8 条并发容量（S11）因 HTTP/1.1 入口限制阻塞，待 HTTP/2 入口就绪后补验

## 更新规则

2026-10-07 补充已批准的 Context v5、受控维护与整理 custom 契约，证据见 [上下文专项](../projects/20261006-agent-context-window-governance/verification.md)。此补充不代表上面原专项的剩余门禁通过。

- 标准发生变化时，对应文件的 `last_verified` 和 `status` 必须同步更新
- 专项从 partial/blocked → done 后，将对应文件 `status` 改为 `active`
- 不在此目录下存放草案或未批准的设计意图
