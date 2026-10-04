# Chat 会话状态机加固与流式体验优化 (Chat Session State and Stream Hardening)

## 项目概述
- **时间：** 2026-10-04 至 2026-10-04
- **目标：** 解决 Dear Agent / Chat 页面在权限刷新竞争、排队消息异常展示、中断与运行态指示冲突、以及首轮思考流式输出缺失的四大交互与状态机顽疾。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`
- **改动级别：** 链路改动 / 会话状态机加固
- **预计工作量：** 0.5 人天

## 关键决策
1. **排队消息 Banner 严格收敛**：只有当确实存在排队任务或待投递回执时（`totalCount > 0`）才允许渲染，空队列下的后台轮询失败转为静默重试，绝不允许弹出“排队 0”的大黄条打扰用户。
2. **权限刷新容错降级（防误踢）**：`refreshCurrentProjectAccess` 在请求失败（如网络抖动或 Token 正在并发刷新）时，保留现有的 `currentProjectAccess` 缓存，仅在明确收到确切的 403 权限剥夺时才清空，根治“当前页面权限已失效”误踢问题。
3. **HITL 交互工具与 Live Step 解耦**：当会话处于中断（`isInterrupted`）或正在展示 `request_information` 等人工澄清表单时，`shouldShowLiveStep` 强制判定为 `false`，彻底清除与“等待补充信息”并存的矛盾指示。
4. **思考流（Reasoning）渐进反馈加固**：针对 DeepSeek 等具备思维链（reasoning-delta）的模型，确保在纯思考流式阶段提供动态感知与骨架反馈，避免界面长时间假死后突兀弹出卡片。
