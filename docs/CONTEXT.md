# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则：** 只保留"当前有效"信息，过期内容直接删除；历史在 `docs/projects/` 和 `docs/changes/` 里。

## 最后更新

2026-09-26 | 跨服务规范治理：错误响应与SSE方案就绪；SSE保留线程级持续保活及原有渲染/交互，用户已同意进入下一专项。追踪已按批准契约形成T1—T8执行文档，状态为“方案就绪、实现未开始”；JWT本期方向及简化生命周期已批准：到期不自动取消已接受Run、不增加SSE持续重鉴权、新请求按当前权限重新签发；字段与23项operation矩阵、J1—J6任务及验收已细化，实现未开始。AI规范路由不再独立立项，后续按仓库级文档小改动处理。Runtime/GraphHarbor完全不改；本轮只写文档及静态核查，功能自动化、真实链路、性能及回退未执行。

2026-09-26 | GraphHarbor 双包 post33 已发布且 runtime-service 锁定；本机两库归档已完整恢复到隔离库，单项目业务 Run/SSE/HITL 与文件正向链路已有阶段证据。业务边界与事件保留专项仍为 partial：官方完整 OpenAPI 比较发现 203 处差异，跨项目故障、容量及最终回退验收未完成；进度见边界解耦项目 README。

## 活跃项目

- [Runtime 与 GraphHarbor 业务边界解耦](projects/20260925-runtime-business-boundary-decoupling/README.md)：`partial`，本机两库已清理旧运行数据并迁移，归档隔离恢复通过，正式依赖 post33 已锁定。单项目 run/SSE/HITL 与文件正向链路已有证据；官方全入口差分、跨项目故障和回退门禁仍缺。

- [interaction-data-service 退役](projects/20260924-interaction-data-service-retirement/README.md)：done（本机范围）；仓库/本机独占资源清理、备份恢复、浏览器聊天与成果交付通过。

- [Dear Agent记忆闭环](projects/20260920-dear-agent-memory/README.md)：partial（后端 + Runtime + 前端 `F01—F07` 代码与单测全部完成；仅剩联调环境完整平台 run/SSE 与浏览器 E2E 验收）。

- [前端对话会话 SWR 缓存与流式长效保活治理](projects/20260924-chat-session-cache-and-stream-resumption/README.md)：原项目记录done；现役已有页面KeepAlive及SWR消息水合。2026-09-26核对发现切Thread仍重建ChatSession，锁定Vue SDK无joinStream；线程实例保活与断流恢复缺口由[SSE专项](projects/20260926-sse-event-contract/README.md)补齐，尚未实施。
- [模型思考内容输出排查](projects/20260923-model-reasoning-output/README.md)：done；`ChatOpenAIWithReasoning` 显式标记 `model_provider="openai_compatible"` 使流式 `AIMessageChunk.content_blocks` 实时产出 `reasoning` 块，配合 `MessageContent.vue` 流式默认展开修复，流式实时展示与完成态均通过。
- [前端代码冗余清理与结构化重构](projects/20260923-platform-web-codebase-refactor/README.md)：✅ 已完成（子专题 01~04 全部 `done`，净减 11,760 行代码，`pnpm build` 与 88 套单测全绿）
- [跨服务规范治理](projects/20260922-cross-service-governance/README.md)：规划中；[错误响应](projects/20260926-error-response-contract/README.md)、[SSE](projects/20260926-sse-event-contract/README.md)、[追踪](projects/20260926-trace-context-propagation/README.md)方案就绪、实现未开始；追踪为平台内部编号与请求/提交/Run/既有观测闭环，完整W3C/OTel后置。JWT执行包已细化、实现未开始；AI规范路由不再独立立项。Runtime/GraphHarbor不改。
- [全平台权限治理](projects/20260920-platform-access-governance/README.md)：技术实现与自动化 Final done，用户人工验收中；完整手工用例、证据模板和清理清单见 08。仅项目内个人记忆入口治理；共享/跨项目记忆、自定义角色等 deferred。未提交或生产部署。
- [代码规范自动化](projects/20260925-code-quality-automation/README.md)：partial；根级 pre-commit 与变更文件 CI 门禁已落地，历史 Python 格式基线待单独清理。
- [Python 格式基线清理](projects/20260925-python-format-baseline-cleanup/README.md)：规划中；约 731 条 Ruff 诊断、297 个文件格式差异待后续分批治理，本次不实施。

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-09-26 | Dear个人记忆能力保留；已锁定 PyPI GraphHarbor post33 并完成 frozen 安装，单项目真实模型 run/SSE/HITL 已验证，跨身份和故障矩阵未完成 |
| platform-api | 2026-09-26（文档） | 追踪治理方案就绪、实现未开始；JWT字段/身份/生命周期及执行包已细化、未实施；不代表新增关联查询已交付。原有Dear个人记忆、Thread ACL内部回查/token/grant复核、预留/对账及共享撤权能力保留；BYOK双层模型按原有能力运行 |
| platform-web | 2026-09-24 | 完成 Dear Agent 无线程个人记忆治理重构（`DearAgentMemoryPage.vue` + `memory.service.ts` + `ThreadAccessControl.vue` 分享隐私提示 + 移除孤儿 `useDearGovernanceContext.ts`），16 条单测/typecheck/eslint 全绿；同时保留会话 SWR 缓存与路由 KeepAlive 保活 |
| AI Harness（AGENTS.md + Skills） | 2026-09-21 | 今日完成全面优化，详见 docs/changes/20260921-harness-optimization.md |

## 近期关键决策

- 2026-09-21: 引入两阶段验证（Phase 验证 + Final 验证），禁止每改一小块就全量回归
- 2026-09-21: tasks.md 改为四段式结构（改动内容/代码位置/预期结果/验证项）
- 2026-09-21: 引入 Task Completion Card + 合规 checklist（可观测层）
- 2026-09-21: 引入 docs/CONTEXT.md（记忆层）+ docs/lessons/（反馈层）
- 2026-09-22: 全平台权限治理按人工批准实施；P1 ACL 属平台数据库，保留 D08 删除/审批、60 秒与激活刷新、限时审计 takeover；旧会话数据库历史已按授权清理。Runtime/GraphHarbor 代码不改，自定义角色 deferred，D24—D28 保留后续讨论。
- 2026-09-22: 批准采纳平台公共模型与项目私有模型 (BYOK) 双层架构决策（详见 docs/decisions/20260922-byok-project-model-architecture.md），解耦平台中心化底座与项目自主密钥，消除脱敏凭据误报假故障问题。

## 踩坑提醒

→ 见 `docs/lessons/`（按服务索引，开工前按需读取对应文件）
