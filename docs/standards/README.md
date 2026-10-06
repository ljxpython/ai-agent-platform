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
| 错误响应 Envelope | [error-envelope.md](error-envelope.md) | active | 2026-09-27 | 🟢 high | [20260926-error-response-contract](../projects/20260926-error-response-contract/README.md) |
| 链路追踪传播 | [trace-propagation.md](trace-propagation.md) | active | 2026-09-27 | 🟢 high | [20260926-trace-context-propagation](../projects/20260926-trace-context-propagation/README.md) |
| Delegation JWT Schema | [delegation-jwt.md](delegation-jwt.md) | draft | 2026-10-05 | 🟡 medium | [20260926-delegation-jwt-contract](../projects/20260926-delegation-jwt-contract/README.md) |
| SSE 事件格式契约 | [sse-event.md](sse-event.md) | draft | 2026-09-27 | 🟡 medium | [20260926-sse-event-contract](../projects/20260926-sse-event-contract/README.md) |

## 未完成项

- **delegation-jwt（draft）**：26 项 operation 和 claim 规则已验，包含 `suggestions-generate` 的内部路由隔离；cron 实时授权隔离链路通过；消息内部原生 Run 回查源码已修复，现役链路尚未验证，待 [message-run-read-delegation](../projects/20260927-message-run-read-delegation/README.md) 专项部署后补验
- **sse-event（draft）**：帧安全、SDK 重试、会话池、410 降级规则已验（S1–S10）；8 条并发容量（S11）因 HTTP/1.1 入口限制阻塞，待 HTTP/2 入口就绪后补验

## 更新规则

- 标准发生变化时，对应文件的 `last_verified` 和 `status` 必须同步更新
- 专项从 partial/blocked → done 后，将对应文件 `status` 改为 `active`
- 不在此目录下存放草案或未批准的设计意图
