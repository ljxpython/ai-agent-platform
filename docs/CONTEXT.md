# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则：** 只保留"当前有效"信息，过期内容直接删除；历史在 `docs/projects/` 和 `docs/changes/` 里。

## 最后更新

2026-09-24 | 优化前端对话界面为仿 GPT 回合锚定与流式防抖滚动设计：首次提问即时收起欢迎卡片并置顶流式输出；后续提问精准停留在视口偏中间位置（32%视口高度）配合动态留白垫片向下流式输出；统一底部悬浮“回到最新”胶囊并支持丝滑上下滑动

## 活跃项目

- [模型思考内容输出排查](projects/20260923-model-reasoning-output/README.md)：done；`ChatOpenAIWithReasoning` 显式标记 `model_provider="openai_compatible"` 使流式 `AIMessageChunk.content_blocks` 实时产出 `reasoning` 块，配合 `MessageContent.vue` 流式默认展开修复，流式实时展示与完成态均通过。
- [前端代码冗余清理与结构化重构](projects/20260923-platform-web-codebase-refactor/README.md)：✅ 已完成（子专题 01~04 全部 `done`，净减 11,760 行代码，`pnpm build` 与 88 套单测全绿）
- [跨服务规范治理](projects/20260922-cross-service-governance/README.md)：🔴 规划中（待人工评审）
- [全平台权限治理](projects/20260920-platform-access-governance/README.md)：技术实现与自动化 Final done，用户人工验收中；完整手工用例、证据模板和清理清单见 08。仅项目内个人记忆入口治理；共享/跨项目记忆、自定义角色等 deferred。未提交或生产部署。

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-09-23 | `ChatOpenAIWithReasoning` 现设置 `model_provider="openai_compatible"`，确保流式 `AIMessageChunk.content_blocks` 实时输出 `{"type": "reasoning", ...}` 供 LangGraph v2 `messages` 频道推送；`RuntimeConfigMiddleware` 强制执行 `tool_calls` 连续性与截断自愈 |
| platform-api | 2026-09-22 | BYOK 双层模型架构 Phase 2 落地；0004 迁移、双层模型 RBAC、私有模型自主 CRUD/注销与网关代理安全打通，测试全绿 |
| platform-web | 2026-09-24 | `ChatSession.vue` / `ChatMessageList.vue` / `scroll-state.ts` 实现仿 GPT 聊天界面回合锚定（首轮置顶、后续提问锚定视口 32% 偏中间位置 + 动态底部留白垫片）与无抖动流式跟随；修复欢迎卡片与乐观消息不同步问题 |
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
