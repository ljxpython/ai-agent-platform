# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

## 最近改动

2026-10-06 | **Agent 回答后推荐问题**：全链路完成。Platform API 与 Runtime Service 完成 suggestions 配置/生成、Delegation 隔离与 one-shot 推理；Platform Web 实装带 x-project-id 与单例缓存 API、思维链与多模态清洗纯函数、生命周期状态机（KeepAlive 补偿、Stop 抑制、竞态防护）、FollowUpSuggestions 紧凑展示组件与草稿冲突确认弹窗；27 项单测、vue-tsc 0 错误、ESLint 0 错误与生产打包全绿。未部署现役或远端平台。见 [专项](projects/20261005-agent-followup-suggestions/README.md)。

2026-10-05 | **定时 Agent 任务**：全链路完成。后端与隔离验收 done；前端定时任务模块实装，对标 playbook 与 control-plane 规范，吸纳 DeerFlow 纯函数 Cron 预设，支持 Card Grid 列表、双栏响应式 Inspector 抽屉、运行历史按需懒加载与权限守卫；481 项单测全绿、vue-tsc 0 错误、生产构建全绿。见 [专项](projects/20261005-scheduled-agent-tasks/README.md)。

### 同日流资源专项

2026-10-05 | **多会话流连接与运行缓存治理**：done；GraphHarbor post39 双包正式发布并完成 PyPI 独立安装，本地 Runtime API/Worker 升级重启；Redis 清理确认终态与用户授权的 618 个未知遗留流后约 586 MiB。三会话连续切换、后台队列、六个 Run success 与消息去重浏览器验收通过；权限故障/真实撤权 4 项通过。见 [专项](projects/20261005-chat-stream-resource-governance/README.md)。

### 同日权限专项

2026-10-05 | **平台权限状态与刷新治理**：本地 done。项目权限区分临时不可确认与真实拒绝；列表/后台刷新失败保留有效快照，路由与页面统一具体权限判断；作用域 403、刷新合并、认证服务 503 保留会话；Runtime ACL 共享连接池兼容文件路径加载，默认超时 10 秒。前端 473 passed/1 skipped、Runtime 114 项及最终定向 41 项、API 13 项/299 子测试、4 项故障注入及 4 项真实安全浏览器通过。未部署远端平台；Runtime 更改已随本次本地升级重启生效。见 [专项](projects/20261005-platform-access-refresh-governance/README.md)。

## 本月归并

2026-10（截至 10-05）| Chat state/history 委托补齐与错误恢复；Chat 后台会话 DOM 虚拟化隔离与流式切换卡死根治、智能体切换隔离与列表远程拉取解耦治理、Chat 顶栏选择 Agent 历史列表联动过滤失效与 Pad 侧栏体验治理、对话前端视口平滑锚定与流式跟随根治、Clean Architecture 五层解耦重构、多会话后台无感自动排队消费与权限失效误杀彻底根治、切回历史时序正序合并、多会话切回假死死锁/空白水合/报错隔离、LangGraph v3 默认消费与 DeltaChannel 离线/PG 评估、模型畸形 ToolCall 自动缝合与孤儿块剔除、平台用户软删除三重安全栅栏、DeepSeek 官方多模态视觉识图、长会话断流解耦与历史懒加载、DearFlow 防死循环护栏、小惊喜创意工坊与 Jina Reader 接入、HTML 沙箱现代化渲染、Runtime DB 精简重构。

2026-09 | DearFlow Agent 全链路迁移（partial）、SSE 保活心跳与容错、GraphHarbor post37 子智能体历史持久化、跨服务规范治理（error-envelope/trace active）、权限治理、代码规范自动化与 Python 格式基线清理、前端 SWR 缓存治理、v0.5.0 里程碑发布。

## 活跃项目

- [Agent 回答后推荐问题](projects/20261005-agent-followup-suggestions/README.md)：done（本地全链路代码与门禁已完成）；Platform API + Runtime Service + Platform Web 全栈闭环，单测、静态类型、Lint 与生产构建全绿；真实三服务 E2E 与远端人工标准评审待具备环境后执行。

- [定时 Agent 任务](projects/20261005-scheduled-agent-tasks/README.md)：全链路 done；后端 CRUD/once/manual/预览/分页和执行前拒绝审计完成，发布包隔离链路通过；前端定时任务模块实装，对标 playbook 与 control-plane 规范，全仓 107 套件 481 单测、vue-tsc 与生产打包全绿。未部署现役或远端平台。

- [Chat 持久消息队列](projects/20261005-durable-chat-prompt-queue/README.md)：进行中，用户已批准治理方案；已核对 localStorage 消费根因、审批/FIFO/取消缺口，开始实施。现有平台修复已推送 `b85e00f`。

- [多会话流连接与运行缓存治理](projects/20261005-chat-stream-resource-governance/README.md)：done；多会话与真实撤权浏览器、最终构建验证通过；GraphHarbor post39 双包已发布，本地 Runtime 已升级重启；Redis 从峰值 18.01 GiB 降至约 0.57 GiB。

- [平台权限状态与刷新治理](projects/20261005-platform-access-refresh-governance/README.md)：本地 done；临时故障保留页面/登录，真实撤权仍生效；单测、故障注入与真实安全链路通过。未生产部署。

- [Chat 前端对话架构治理与 Clean Architecture 重构](projects/20261004-chat-frontend-clean-architecture-refactor/README.md)：done；对标谷歌范式完成 5 层解耦。剥离模型参数、视口跟随、分支动作与传输自愈；ChatSession 降至 1959 行，useChatSession 压降至 1198 行，消息流水线纯函数化；前端 429 项单测、vue-tsc 0 错误、生产构建全绿。
- [LangGraph v3 默认消费与 DeltaChannel 评估](projects/20261004-langgraph-v3-delta-evaluation/README.md)：partial；后端默认 v3、前端交接、离线 Spike 和本地 PostgreSQL 体积测量已完成，回滚门禁和前端浏览器验收待执行；节点 timeout/error_handler/RunControl 暂不实施。
- [Chat 会话状态机加固与流式体验优化](projects/20261004-chat-session-state-and-stream-hardening/README.md)：done；彻底解决切屏失焦权限刷新误踢、空队列误弹排队 0 黄条、中断等待澄清时底部悬挂正在处理矛盾提示、以及 DeepSeek 思维链首轮流式卡顿假死四大顽疾；前端 22 项单测全绿、静态类型检查与生产打包全绿。
- [平台用户软删除与生命周期治理](projects/20261003-platform-user-soft-delete/README.md)：done；平台用户软删除闭环，扩展 UserStatus.DELETED，三大安全护栏（防自杀、最后活跃超管、唯一项目管理员防孤儿项目），重命名释放用户名/subject，吊销 token，退出关联项目；前后端单测与生产构建全绿。
- [长会话断流恢复解耦与历史快照按需懒加载治理](projects/20261002-chat-history-lazy-loading-and-timeout-resilience/README.md)：done；解耦断流恢复对 3.4MB 巨型 history 的阻塞依赖，仅拉取 state 毫秒级极速自愈并后台静默预热；加固 ChatSession 抽屉懒加载与错误隔离，单测与生产构建全绿。
- [DearFlow Agent 灵感建议与“小惊喜”创意工坊](projects/20261002-dearflow-surprise-me-feature/README.md)：done；前端 Confetti 动效按钮与灵感胶囊栏实装，后端创意交互网页生成规范与工作区沙箱高保真免刷新预览闭环，单测及生产打包全绿。
- [DearFlow Agent 接入 Jina Reader 网页深度提取](projects/20261002-dearflow-jina-reader-integration/README.md)：done；Jina Reader API（r.jina.ai）高质量 Markdown 深度提取与双通道平滑容灾降级已实装，单测与真实网络提取验证全绿。
- [工作区 HTML 现代化沙箱渲染支持](projects/20261002-workspace-html-sandbox-preview/README.md)：done；前后端精准沙箱隔离与 CSP 白名单升级，Tailwind CDN / Google Fonts 完整放行，单元测试与全链路真实博客页面验收全绿。
- [Runtime 数据库访问边界收敛与类型补全](projects/20260930-runtime-database-repository-refactor/README.md)：本期 done；Scope 与 Memory/Skills SQL 抽取完成，43 项定向通过；全仓两项范围外失败已对照复现，详见 verification.md。
- [Runtime Agent 组合根脚手架重构与 DX 体验治理](projects/20260930-runtime-agent-harness-refactor/README.md)：规划中；针对组合根样板代码超标（150+行安全胶水代码）与测试构造心智摩擦，完成方案设计与任务拆分，待方案评审。
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
| runtime-service | 2026-10-06 | 新增 follow-up suggestions 独立 endpoint、JWT scope 隔离、无工具 one-shot 模型调用与输出清洗；suggestions 定向测试 10 passed，改动文件 Ruff 通过。真实模型与现役 Runtime 未联调。 |
| platform-api | 2026-10-06 | 新增 suggestions 配置/Thread API、ACL/模型策略校验、`suggestions-generate` delegation 与 Runtime 降级；suggestions + delegation 定向测试 8 passed、48 个子测试，改动文件 Ruff 通过。未部署现役或远端平台。 |
| platform-web | 2026-10-06 | Agent 回答后推荐问题全链路实装（带 x-project-id API、思维链清洗纯函数、生命周期状态机、FollowUpSuggestions 紧凑展示与草稿冲突确认弹窗）；定时 Agent 任务模块维持已验状态。全仓单测全绿、vue-tsc 0 errors、生产打包通过。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-04 | AGENTS.md 与 Skill 重复内容已去除（场景步骤 + 验证标准章节移入 Skill），CONTEXT.md 改为渐进式快照结构；整单结束前须逐项核对未完成任务，Task 未完成时只记 Phase |

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
