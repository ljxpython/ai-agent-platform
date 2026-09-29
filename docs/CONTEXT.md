# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则：** 只保留"当前有效"信息，过期内容直接删除；历史在 `docs/projects/` 和 `docs/changes/` 里。

## 最后更新

2026-09-29 | 平台重大里程碑发布：正式定级发布 `v0.5.0`。确立“面向二次开发与企业落地的 AI Agent 平台底座”核心定位；消灭早期测试流水账与死链，重构中英文主页并发布 3 套 Archify 2K 架构/时序/扩展点全景可视化系统；实装以 `open-swe`、`deepagents` 与 `deer-flow` 为支柱的生产级智能体 `DeerFlow Agent`，支持多模式工作流、长期记忆闭环、沙箱 Workspace 与 PTY 终端；致谢置顶技术核心并发布正式 Release Notes 与 Runbook。

2026-09-29 | architecture/ 方法论升级：新增第七章双层渐进式概念透析规范（30秒原地折叠拐杖 + 概念专篇库）；新建 concepts/ 目录并交付首篇《01-从 MVC 到 DDD 与六边形架构深度透析》；完成 04-platform-api 架构文档原地折叠拐杖挂载

2026-09-29 | docs/ 目录结构整理：quickstart/ 并入 guides/；decisions/ ADR 迁入各自 projects/ 子目录；新建 architecture/ 教学文档目录；新建 docs/README.md 导航入口

2026-09-28 | DearFlow迁移重新盘点与规划完成：沿用20260913专项，新增11能力矩阵（38类Agent能力/23个Skills）、12补齐任务与评审、13验证基线；资源迁入19/23，4项仍延期未迁。纠正原总纲“整体完成”表述，明确Skills单份当前内容、共享Chat和后续记忆/post37历史修复的覆盖关系。本轮核心抽测28 passed/1 skipped；未改业务代码，整体partial，新增治理实施范围待人审。

2026-09-28 | Python 格式基线清理与 CI 全量门禁专项圆满完成（done）：彻底消除 `platform-api`（163 条）与 `runtime-service`（152 条）全量存量 Lint 诊断（0 errors）；全仓 574 个 Python 文件全部完成 Ruff 格式化；安全治理 B023 闭包循环变量绑定、B904 异常链显式保留、B017 确切异常断言与 re-export 符号保护机制；两服务核心单测（325 + 534 项）全绿通过；`.github/workflows/ci.yml` 成功升级全量 Ruff check 与 format check 门禁。

2026-09-28 | 子智能体工具调用历史持久化与回放能力专项完成（done）：GraphHarbor 核心团队响应 RFC 并发布 `0.13.0.post37`，支持定向 `checkpoint_ns` 路由。平台完成 `runtime-service` 依赖锁步、`platform-api` 网关层放通 `checkpoint_ns` 与对齐 LangGraph 官方 SDK 的 `POST /state/checkpoint` 端点；服务栈完整平滑重启就绪；真实历史 Thread `fba64a6c-...` 端到端回归实测 100% 成功拉取到子智能体的 16 条完整消息、10 次内部工具调用（ls/read_file/grep/glob）及 10 步历史快照，彻底根治工具轨迹丢失问题。

2026-09-27 | SSE 事件流保活心跳与连接容错治理专项扩展完成（done）：针对 GraphHarbor 重放旧 Run 历史中断导致前端误报“审批请求已变化”问题，完成根因实锤并输出专项交付文档 `graphharbor-zombie-interrupt-replay-recommendations.md`；同时在前端 `useSessionInterrupts.ts` 引入 `resolvedReviewIds` 响应式过滤网与权威 `state` 主动对齐自愈机制，彻底消除死锁；Vitest 聊天模块 173 项测试全绿。

2026-09-27 | AI 服务路由机制落地：AGENTS.md 新增服务规范读取规则和跨服务规范章节；docs/standards/ 目录建立（error-envelope/trace-propagation active，delegation-jwt/sse-event draft）

2026-09-27 | Harness 自我进化机制补全：AGENTS.md 加「项目收尾反思」（经验提案 + 标准文件毕业）；implement-feature Skill 完成卡加 FEATURES.md 必填勾选项

2026-09-27 | 追踪专项T1—T8、本期V01—V15及R1—R6已验：并发/取消隔离、审批/取消关系、SQLite/PG精确查询、真实worker Run→Langfuse、执行中SSE断连与跨Run重连、权限负例及性能实测均有证据；一次502发生在测试编辑触发API热重载期间，无编辑干扰的复测200。性能按用户确认只留数据、不设SLO。错误响应专项已done。Delegation JWT原专项J1—J6的23项双端矩阵和R01—R04真实生命周期有证据，Final保留当时消息内部回查403的partial结论；后续单独授权的消息回查修复已修改Platform API/Runtime源码，本机真实PostgreSQL及授权矩阵通过，现役跨服务链路未验证。现役reference_agent的runtime.tool.not_allowed是既有工具授权基线差异。SSE专项S1—S10已完成，8条并发受本地HTTP/1.1浏览器origin连接槽限制。未迁移或部署；追踪专项按用户独立授权提交，GraphHarbor不改。

2026-09-26 | GraphHarbor 双包 post33 已发布且 runtime-service 锁定；本机两库归档已完整恢复到隔离库，单项目业务 Run/SSE/HITL 与文件正向链路已有阶段证据。业务边界与事件保留专项仍为 partial：官方完整 OpenAPI 比较发现 203 处差异，跨项目故障、容量及最终回退验收未完成；进度见边界解耦项目 README。

## 活跃项目

- [DearFlow Agent迁移重审与补齐](projects/20260913-dearflow-agent/README.md)：整体partial；本轮分析规划已交付，接续以12的T01—T10为入口。14效果审计已用7个离线故障场景复现响应终止、空回答、错误完成、循环、预算和Todo缺口；优先T03/T07关键可靠性及真实页面验收，音视频/新版扩展单独评审；不恢复已被后续专项取代的旧设计。

- [子智能体工具调用历史持久化与回放能力支持](projects/20260928-graphharbor-subagent-tool-history/README.md)：done；GraphHarbor post37 升级与 platform-api 网关层放通，全链路端到端真实用例实测通过，子智能体内部 10 次工具调用全数可查。
- [SSE 事件流保活心跳与连接容错治理](projects/20260927-sse-stream-heartbeat-and-resilience/README.md)：done；针对每隔 45 秒频繁弹出“恢复连接”假性报错条及重放历史中断导致审批死锁的问题，通过 Platform API 网关注入心跳与前端审批状态机自愈彻底根治；探针实测与单测全绿；GraphHarbor 专属心跳与中断重放两份修复文档已交付。
- [消息内部Run回查委托修复](projects/20260927-message-run-read-delegation/README.md)：partial；Platform API只在消息入口转发请求内已有read委托，Runtime配对验证后用于内部Run GET；本机自动化通过，现役跨服务链路未验证，未部署。
- [Runtime 与 GraphHarbor 业务边界解耦](projects/20260925-runtime-business-boundary-decoupling/README.md)：`partial`，本机两库已清理旧运行数据并迁移，归档隔离恢复通过，正式依赖 post33 已锁定。单项目 run/SSE/HITL 与文件正向链路已有证据；官方全入口差分、跨项目故障和回退门禁仍缺。

- [interaction-data-service 退役](projects/20260924-interaction-data-service-retirement/README.md)：done（本机范围）；仓库/本机独占资源清理、备份恢复、浏览器聊天与成果交付通过。

- [Dear Agent记忆闭环](projects/20260920-dear-agent-memory/README.md)：partial（后端 + Runtime + 前端 `F01—F07` 代码与单测全部完成；仅剩联调环境完整平台 run/SSE 与浏览器 E2E 验收）。

- [前端对话会话 SWR 缓存与流式长效保活治理](projects/20260924-chat-session-cache-and-stream-resumption/README.md)：原项目记录done；现役已有页面KeepAlive及SWR消息水合。切Thread重建与SDK断流缺口由[SSE专项](projects/20260926-sse-event-contract/README.md)阶段实现补齐，普通真实链路及1/4条短容量已验，8条容量受HTTP/1.1浏览器连接槽限制，Final blocked。
- [模型思考内容输出排查](projects/20260923-model-reasoning-output/README.md)：done；`ChatOpenAIWithReasoning` 显式标记 `model_provider="openai_compatible"` 使流式 `AIMessageChunk.content_blocks` 实时产出 `reasoning` 块，配合 `MessageContent.vue` 流式默认展开修复，流式实时展示与完成态均通过。
- [前端代码冗余清理与结构化重构](projects/20260923-platform-web-codebase-refactor/README.md)：✅ 已完成（子专题 01~04 全部 `done`，净减 11,760 行代码，`pnpm build` 与 88 套单测全绿）
- [跨服务规范治理](projects/20260922-cross-service-governance/README.md)：错误响应与追踪本期done；追踪T1—T8、真实链路、PG查询及性能实测见专项Final。JWT J1—J6与R01—R04已验，后续消息回查源码修复与本机测试通过、部署后真实链路未验证；SSE S1—S10完成，S11容量Final受HTTP/1.1连接槽限制而blocked。原专项边界保留，后续消息专项单独授权Runtime入口修改；GraphHarbor不改。
- [全平台权限治理](projects/20260920-platform-access-governance/README.md)：技术实现与自动化 Final done，用户人工验收中；完整手工用例、证据模板和清理清单见 08。仅项目内个人记忆入口治理；共享/跨项目记忆、自定义角色等 deferred。未提交或生产部署。
- [代码规范自动化](projects/20260925-code-quality-automation/README.md)：partial；根级 pre-commit 与变更文件 CI 门禁已落地，历史 Python 格式基线待单独清理。
- [Python 格式基线清理](projects/20260925-python-format-baseline-cleanup/README.md)：done；历史存量 315 条诊断全部清零（0 errors），全仓 574 个 Python 源码文件完成格式化，CI 成功升级全量 Ruff check 与 format check 门禁。

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-09-28 | 存量 Python 诊断全部清零且 100% 格式化；GraphHarbor post37 升级并支持 checkpoint_ns；消息入口内部Run GET改用已验证的配对read委托；单测全通 |
| platform-api | 2026-09-28 | 存量 Python 诊断全部清零且 100% 格式化；网关层放通 checkpoint_ns 与 /state/checkpoint；网关层 SSE 流保活心跳注入保持；单测全通 |
| platform-web | 2026-09-27 | ChatSession 解耦 reconnecting 与红色报错条，仅 paused 展示恢复连接；错误解析、SDK流恢复/410单飞及Workspace线程池有证据；全量Vitest聊天单测221 passed；真实8条容量受HTTP/1.1 origin连接槽限制 |
| AI Harness（AGENTS.md + Skills） | 2026-09-26 | 整单结束前须逐项核对未完成任务；Task 未完成时只记 Phase，剩余项确需用户行动才可按 blocked 汇报；详见 docs/changes/20260926-harness-completion-reporting.md |

## 近期关键决策

- 2026-09-21: 引入两阶段验证（Phase 验证 + Final 验证），禁止每改一小块就全量回归
- 2026-09-21: tasks.md 改为四段式结构（改动内容/代码位置/预期结果/验证项）
- 2026-09-21: 引入 Task Completion Card + 合规 checklist（可观测层）
- 2026-09-21: 引入 docs/CONTEXT.md（记忆层）+ docs/lessons/（反馈层）
- 2026-09-22: 全平台权限治理按人工批准实施；P1 ACL 属平台数据库，保留 D08 删除/审批、60 秒与激活刷新、限时审计 takeover；旧会话数据库历史已按授权清理。Runtime/GraphHarbor 代码不改，自定义角色 deferred，D24—D28 保留后续讨论。
- 2026-09-22: 批准采纳平台公共模型与项目私有模型 (BYOK) 双层架构决策（详见 docs/decisions/20260922-byok-project-model-architecture.md），解耦平台中心化底座与项目自主密钥，消除脱敏凭据误报假故障问题。
- 2026-09-27: 追踪审计查询性能本期仅记录实测数据；仓库无批准SLO，不临时设达标阈值。

## 踩坑提醒

→ 见 `docs/lessons/`（按服务索引，开工前按需读取对应文件）
