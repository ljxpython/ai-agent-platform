# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则：** 只保留"当前有效"信息，过期内容直接删除；历史在 `docs/projects/` 和 `docs/changes/` 里。

## 最后更新

2026-09-23 | platform-web 全面完成前端代码冗余清理与结构化重构（4 个子专题全部 `done`：双生会话模块合并、useChatSession 拆解、三大超长控制面页面拆分、HTTP 错误解包收敛），净减 11,760 行重复代码；`pnpm build`（vue-tsc + vite build）与 Vitest 88 套单测（355 用例）100% 通过，本地运行恢复正常

## 活跃项目

- [前端代码冗余清理与结构化重构](projects/20260923-platform-web-codebase-refactor/README.md)：✅ 已完成（子专题 01~04 全部 `done`，净减 11,760 行代码，`pnpm build` 与 88 套单测全绿）
- [跨服务规范治理](projects/20260922-cross-service-governance/README.md)：🔴 规划中（待人工评审）
- [全平台权限治理](projects/20260920-platform-access-governance/README.md)：技术实现与自动化 Final done，用户人工验收中；完整手工用例、证据模板和清理清单见 08。仅项目内个人记忆入口治理；共享/跨项目记忆、自定义角色等 deferred。未提交或生产部署。

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-09-23 | 升级 `graphharbor` / `graphharbor-runtime` 至 `0.13.0.post32`（修复 `ProductionWorker` 多槽位并发 `slot-0..3` 及 `_StreamEventBuffer` 32条/50ms 批量写库）；`dearflow_agent` 单步推理超时提升至 `240s` |
| platform-api | 2026-09-22 | BYOK 双层模型架构 Phase 2 落地；0004 迁移、双层模型 RBAC、私有模型自主 CRUD/注销与网关代理安全打通，测试全绿 |
| platform-web | 2026-09-23 | 完成全仓结构化重构（净减 11,760 行重复代码）；优化工具卡片状态机区分 LLM「正在生成参数 · 已生成 X.Xk 字符」与「执行中」阶段并支持 `write_file` 流式预览 |
| interaction-data-service | — | — |
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
