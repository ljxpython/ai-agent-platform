# 跨服务规范治理（Cross-Service Governance）

## 项目概述
- **时间：** 2026-09-22 至 待定
- **目标：** 建立四个服务之间的统一契约规范，解决 AI Harness 缺乏服务路由、错误格式不统一、链路追踪断链、关键内部接口无文档等问题
- **负责人：** @lijiaxin
- **模板类型：** 多专题模板
- **状态：** 🔴 规划中（治理改动，待人工评审批准后方可实施）

## ⚠️ 评审要求

本项目为治理改动，涉及跨服务架构规范制定。**以下决策点需要在评审时确认：**

1. **错误 Envelope 格式（02）**：是否接受以 platform-api 现有格式为基础，统一 runtime-service 和 IDS 的错误结构
2. **链路追踪方案（03）**：是否采用 W3C traceparent 作为主追踪头，x-request-id 作为日志关联别名
3. **实施顺序**：是否按 01 → 04 → 02 → 03 → 05 的优先级顺序推进

## 阅读顺序

1. [AI 服务路由机制](01-ai-routing-mechanism.md)：在 AGENTS.md 中建立服务规范索引，让 AI 改哪个服务就读哪份规范（**风险最低，可最先实施**）
2. [错误响应 Envelope 标准](02-error-envelope-standard.md)：统一四个服务的错误响应格式，以 platform-api 现有格式为基准
3. [跨服务链路追踪规范](03-trace-propagation.md)：设计 W3C traceparent 传播链，打通 Langfuse 与平台 trace_id 关联
4. [Delegation JWT Schema 文档化](04-delegation-jwt-schema.md)：将已有的 JWT 实现整理为正式的接口契约文档（**纯文档，无代码变更**）
5. [SSE 事件格式契约](05-sse-event-contract.md)：定义 runtime → platform-api → platform-web 的流式事件格式（**纯文档**）

## 改动范围

- **影响服务：** 全部四个服务 + AI Harness（AGENTS.md）
- **改动级别：** 治理改动
- **子专题独立性：** 每个子专题可独立实施和验收，无强依赖顺序

| 子专题 | 类型 | 风险 | 需要代码变更 |
|---|---|---|---|
| 01 AI 路由机制 | Harness 改动 | 低 | 否（仅 AGENTS.md）|
| 02 错误 Envelope | 架构规范 + 代码 | 中 | 是（runtime-service / IDS）|
| 03 链路追踪 | 架构设计 | 中 | 是（platform-api 生成 + 各服务透传）|
| 04 JWT Schema | 纯文档 | 无 | 否 |
| 05 SSE 契约 | 纯文档 | 无 | 否 |

## 关键决策

1. 错误 Envelope 以 platform-api 现有 `ErrorResponse` 模型为标准，`extra` 字段归入 `error` 内，`request_id` 移入 `meta` 对象
2. 链路追踪采用 W3C traceparent，platform-api 为入口生成方，所有下游服务透传
3. AI 路由机制通过 AGENTS.md 显式服务索引实现，Skill 路径懒加载
4. 跨服务规范优先于服务内部规范（当两者冲突时）

## 背景

经过对四个服务文档的全面读取，识别出以下系统性问题：

| 问题 | 具体现象 |
|---|---|
| AI 无服务感知 | AGENTS.md 无服务路由规则，AI 改 runtime 时不知道读 LangGraph 规范 |
| 错误格式三套 | platform-api 用 `{error:{}}`, runtime 用 `{detail:{}}`, IDS 用 `{detail:"string"}` |
| 链路追踪断链 | x-request-id 提到但无格式/传播规范，Langfuse trace 与平台 trace 无关联 |
| JWT Schema 无文档 | Delegation JWT 有完整实现但无独立契约文档，只散落在代码和 changes 里 |
| SSE 格式无约定 | runtime 产出、platform-api 脱敏、前端消费三段无对齐文档 |
