# SSE 事件流保活心跳与连接容错治理专项

## 项目概述
- **时间：** 2026-09-27 至 2026-09-28
- **目标：** 解决前端会话持续保活时每隔 45 秒频繁弹出“恢复连接”假性报错条的问题，通过 Platform API 网关注入心跳与前端 SDK/UI 容错机制彻底根治假死断连。
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **状态：** 已完成（done）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)
- [GraphHarbor 上游心跳修复建议](graphharbor-upstream-recommendations.md)
- [GraphHarbor 历史中断重放缺陷与修复建议](graphharbor-zombie-interrupt-replay-recommendations.md)

## 改动范围
- **影响服务：** `platform-api`（网关层）、`platform-web`（前端展示与审批状态机自愈）
- **约束声明：** 依赖库 `GraphHarbor` 保持锁定不改动；不改动底层数据库结构与事件保留策略；不破坏现有的对话渲染和交互基线。
- **改动级别：** 链路改动 / 跨服务规范治理
- **预计工作量：** 1.5 人天

## 关键决策
1. **上游缺陷网关层兜底：** 鉴于 GraphHarbor 双包已锁定（不修改二进制包），由 Platform API 网关层在代理 SSE 流时注入周期性保活心跳（`: heartbeat\n\n`），彻底解决上游心跳缺失导致前端超时断开的问题。
2. **连接状态与破坏性 UI 解耦：** 前端优化 `reconnecting` 短暂重连态的展示逻辑，区分“静默自动重试”与“真正断连报错（paused）”，消除假性故障报警。
3. **HTTP/1.1 浏览器连接槽保护：** 确保非活跃会话与断开会话及时释放长连接，避免占满 6 个同源并发槽位。
4. **历史中断重放防御与前端自愈：** 针对 GraphHarbor 重放旧 Run 历史已解决中断的问题，前端 `useSessionInterrupts.ts` 建立 `resolvedReviewIds` 响应式过滤网与权威 `state` 主动对齐机制，阻断死鬼卡片上屏，并在 ID 漂移时自动刷新为最新审批项解除用户死锁。
