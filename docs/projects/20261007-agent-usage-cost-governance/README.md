# Agent 通用 Token/Cost 跟踪与运行用量治理

## 项目概述

- **启动日期：** 2026-10-07
- **目标：** 为所有可接入 Runtime Middleware/Tool 的 Agent 建立可持久化、可授权查询、可按模型价格估算的 Run/Thread 用量能力。
- **负责人：** 后端与 Runtime 由当前开发者负责；前端由用户同事负责。
- **模板类型：** 多专题模板
- **改动级别：** 治理改动，涉及 Runtime 数据、跨服务契约、模型目录价格和权限边界。
- **状态：** `done`，全栈（Runtime、Platform API、Platform Web）开发与端到端验证闭环，用户已验收通过。全量既有失败见 05。
- **预计工作量：** Runtime 3-4 人天，Platform API 3-4 人天，前端 2-3 人天，联调与验证 2-3 人天；仅作排期参考。

## 阅读顺序

1. [源码对照与方案辨析](01-source-analysis.md)：open-swe 的设计、当前项目事实、差距和同事方案的取舍。
2. [Runtime 用量采集与持久化](02-runtime-usage.md)：通用 callback/middleware、Token 归一化、Run/Thread 聚合和 Runtime 数据库落点。
3. [Platform API 价格与查询契约](03-platform-cost-contract.md)：模型价格目录、成本快照、授权查询、Delegation 和 API 落点。
4. [前端交接文档](04-frontend-handoff.md)：交给同事的字段、页面复用、状态、验收和明确不做事项。
5. [验证、发布与回滚](05-verification-rollout.md)：单元、集成、E2E、安全、性能基线、灰度和回滚门禁。

README 是本项目唯一总入口。实现细节写入 [实施记录](implementation/01-runtime-and-platform.md)，进度以各专题任务为准。数据库迁移和验证只在独立 PostgreSQL/Redis 与临时 HTTP 服务执行，现役服务未改动。

采用多专题模板的原因：02 可在无价格时独立交付 Token 采集；03 的模型价格管理可先独立验收，查询使用受控 Runtime fixture 验证；04 可按固定 DTO fixture 完成前端实现。三部分各有代码范围和验收项，最后再联合验收。01 为事实依据，05 为总体门禁，不计作独立功能。

## 三层职责与必要性

| 层 | 是否需要 | 本期职责 | 不归该层 |
|---|---|---|---|
| `runtime-service` | 必须 | 在模型调用边界采集每次调用的标准用量，按 `run_id/thread_id` 持久化，按可信价格快照计算估算成本，提供受保护的内部查询 | 价格 CRUD、项目权限决策、前端文案、保存 Prompt/Completion 原文 |
| `platform-api` | 必须 | 管理模型价格与版本，签发/返回价格快照，校验项目/Thread/Run 权限，代理安全用量 DTO，提供公开查询契约 | 重新扫描消息猜 Token、直接连接 Langfuse、执行 Runtime 模型重试 |
| `platform-web` | 展示需要；由同事实施，不阻塞后端阶段交付 | 在现有 Trajectory 入口提供独立 RunUsage 面板、Thread 摘要；模型目录编辑价格；处理部分数据和权限态 | 直接访问 Runtime/Langfuse、浏览器计算账单、用字符数伪造 Token |
| GraphHarbor | 不改 | 继续持有 Thread/Run/checkpoint/worker 事实；供 Run ID 和 E2E 链路使用 | 不保存平台价格、成本或租户业务字段 |

## 关键决策

1. **Runtime 是用量事实源。** 记录采集 Run 和每次物理模型调用；callback ID 只能去重同一次观测，真实重试产生的新调用必须累加。GraphHarbor 仍是原生 Run 状态源。
2. **Platform API 是价格和授权源。** 在现有模型目录增加可选结构化价格，Runtime 通过短期模型引用获得完整快照，版本由服务端生成；价格缺失时成本为 `unknown`，不猜价格。
3. **Token 总量与费用分开。** `total_tokens` 是 input + output，cache/reasoning 为明细；成本按普通输入、缓存读取、缓存写入（含 5m/1h）和输出分别计价。缺少实际用到的费率时成本未知，不把缓存视为免费。
4. **不引入 LangSmith、Datadog 或独立计费系统。** 复用现有 LangChain usage metadata、Langfuse/OTel 观测和三服务边界；本期成本是 `estimated` 观测值，不是财务结算。
5. **复用诊断入口与请求模式，保留独立用量面板。** 新增同级 RunUsage，不扩大已有 RunDiagnostics 和 ChatSession；跨项目排行榜、预算、告警、账单导出后置。
6. **采集故障不影响 Agent。** 数据库不可用、价格缺失或外部观测关闭时，Run 继续执行，查询明确返回 `partial/unavailable/unknown`。
7. **人工评审是实施门禁。** 评审前只维护规划和前端交接；批准后再触发实现、迁移和跨服务验证。

## 范围边界

本期包含：已接线图的主 Agent、子 Agent、摘要模型，以及能证明父 Run 归属的 vision/memory 模型调用；Run/Thread 用量聚合；模型价格快照和估算成本；安全查询、前端交接及同事后续面板接入。Agent 不需要让 LLM 决定是否调用“记账 Tool”，在组合根装配 callback 即可。通用 helper 可用于自定义 Middleware/Tool 内的模型调用。

HTTP one-shot suggestions 和旧标题生成不创建 native Run，首期列为明确排除的 Thread 辅助开销，不伪造 Run ID、不混入 Agent 合计。图片生成/编辑、外部搜索和 MCP 供应商费用也不属于 LLM Token 成本。未来要显示整个产品的总成本，应另行批准辅助调用身份、价格与账务范围。

本期不包含：财务账单、额度扣费、预算告警、供应商发票对账、Prompt/Completion 原文存储、LangSmith 专属 API、Slack/GitHub/PR/Reviewer 业务、外部 SaaS trace 链接、全新独立前端 Usage 页面。

## 实施阶段与评审

| 阶段 | 出口 | 任务入口 |
|---|---|---|
| G0 人工评审 | 批准费用口径、数据归属、操作权限、保留/回滚边界并留下记录 | [评审项](05-verification-rollout.md#phase-0方案评审门禁) |
| P1 Runtime Token | 采集/缺失/去重/父子/重启用例通过；无价格也可用 | 02 的 R02-1 至 R02-6 |
| P2 模型价格与成本 | 价格权限、快照、Decimal 计算、缓存 TTL 和未知语义通过 | 03 的 P03-1 至 P03-3 |
| P3 安全查询 | usage-read 两端契约、Thread 聚合、权限和 DTO 通过 | 03 的 P03-4 至 P03-6 |
| P4 前端 | 同事按交接完成面板、模型价格编辑及 F01-F08 | 04 |
| Final | 后端真实链路、前端联验、故障注入、性能与回退都有证据 | 05 |

本轮验收范围是 02、03、05 的全部非前端任务和 04 的交接报告。前端代码与浏览器联验由用户明确交给同事，本轮不执行 F04-1 至 F04-6 / E10。后端完成后整项目保持 `partial`，同事完成前端并联合验收后再将整项目标记 `done`。

评审记录：**2026-10-07 用户批准**：“方案评审通过，可以开始实施了。把除了前端的开发项都开发完成，除非有 Block 项”。批准范围包含本文及 02/03/05 的数据库迁移设计、价格口径、usage-read、隔离环境验证及保留/回退边界。前端代码不在本轮实施范围；完成后提供接入报告。未授权生产部署、现役服务变更或 Git 提交。

## 现有专项关系

- [可观测性与追踪](../20261006-agent-observability-hardening/README.md)已经完成的诊断和 Langfuse 接线继续复用；本期持久用量独立于 Langfuse 开关，不重做该专项。
- [运行消息队列](../20261005-durable-chat-prompt-queue/README.md)提供同一 Run 多条 HumanMessage 的验收场景，不将 HumanMessage 当作 invocation 边界。
- [Harness 组合根规划](../20260930-runtime-agent-harness-refactor/README.md)未实施；本期不依赖或顺带开发新 Builder。
- [JWT 标准](../../standards/delegation-jwt.md)和网关活规范已增加 `usage-read` 及两个 GET；JWT 全局仍有其他专项遗留验收，保持 draft。
