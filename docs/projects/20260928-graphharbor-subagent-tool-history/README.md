# 专项：子智能体工具调用历史持久化与回放能力支持

## 项目概述
- **时间：** 2026-09-28 至 2026-10-05
- **目标：** 解决子智能体（Subagent/DeepAgent）在会话持久化后工具调用历史丢失问题；输出正式提给 GraphHarbor 团队的能力增强提案（RFC）；设计并实施平台端（platform-api / platform-web）的承接升级方案与离线兜底机制。
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **状态：** 已完成（已接入 GraphHarbor 0.13.0.post37 修复版本并通过端到端真实数据全量验证）

## 快速导航
- [致 GraphHarbor 团队需求提案 (RFC)](graphharbor-rfc.md) —— **核心交付物：提给 GraphHarbor 团队的需求规范与接口建议**
- [整体方案设计与端侧承接](plan.md) —— **包含 GraphHarbor 解决后我们端如何承接、以及若不解决我们的兜底实现**
- [任务拆分与阶段推进](tasks.md) —— **开发与联调分解任务**
- [验证计划与验收矩阵](verification.md) —— **端到端链路验证要求**

## 改动范围
- **影响服务：**
  - `GraphHarbor Server`（上游 LangGraph Agent Server，负责 Checkpoint 查询能力升级）
  - `apps/platform-api`（网关转发层、参数放通与子任务上下文透传）
  - `apps/platform-web`（前端会话历史重构、`<SubtaskDetail>` 离线数据点亮）
- **改动级别：** 链路改动 / 跨服务协议协作
- **预计工作量：** 4 人天（含跨团队联调与端到端验证）

## 关键决策
1. **真实数据已落库，痛点在读取协议**：已通过底层 PostgreSQL 验证，子智能体所有内部工具调用（`ls`, `read_file`, `grep`, `glob` 等）在 `checkpoint_blobs` 表中均完整保存，问题在于 REST 接口没有暴露跨 namespace 历史读取能力。
2. **输出标准 RFC 对接 GraphHarbor**：制定 [graphharbor-rfc.md](graphharbor-rfc.md)，提供 `checkpoint_ns` 定向查询与 `expand_subagents` 批量汇聚两套方案，降低上游改造成本。
3. **两手准备（双轨设计）**：
   - **主路线**：GraphHarbor 团队采纳 RFC，升级 API，平台端做标准协议承接；
   - **兜底路线**：若 GraphHarbor 排期延后，`platform-api` 在执行结束阶段将子图工具摘要注入 `task` tool 的 `artifact`，前端即可立即展示，绝不阻塞业务上线。
