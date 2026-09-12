# Chat 流式输出标准化与 open-swe 架构对齐

## 项目概述
- **时间：** 2026-09-12 至 2026-09-13
- **目标：** 完全对齐官方 LangGraph SDK 原生机制与 open-swe 最佳实践，打通前端真实流式输出（打字机效果、思考过程实时呈现、视口平滑滚底与终态平滑对账），消除假流式与等待卡顿。
- **负责人：** @lijiaxin
- **状态：** 已完成（流式消息管道、工具调用呈现、多轮对话支持、平滑滚底已全部完成并经真实联调验证）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`（主要消息管道与渲染优化）、`platform-api`（流模式参数核验）
- **改动级别：** 链路改动
- **预计工作量：** 1 人天

## 关键决策
1. **完全拥抱官方 SDK 与 LangGraph Server 标准协议**：不造私有 WebSocket 或自研流式协议轮子，完全基于官方 Protocol v2（`commands` + `/stream/events`）通道和 live projections。
2. **借鉴 open-swe 的 `streamMessagesToUi` 纯函数视图映射**：解除现有 `useTranscriptMessages` 对终态 `values` 的死锁依赖，让 live token 顺畅流向 UI。
3. **思考过程与工具调用原生呈现**：直接利用 `@langchain/core` 的 `contentBlocks` 与 `reasoning_content`，将思考过程与正文内容干净解耦，支持流式实时展开。
4. **自适应视口滚屏跟随**：基于 token 增长与防抖微任务实现平滑滚底，告别“只在消息条数增加才滚屏”的迟钝体验。
