# 项目当前状态 - AI 上下文

> **最后更新：** 2026-10-08（Agent 执行预算/步骤限制告警与软收尾、运行生命周期超时治理与排队死锁自愈，以及 Agent 通用 Token/Cost 跟踪治理全栈闭环，用户端到端自动化与人工验收通过，全项标为 done 并零功能损失合并进入主分支）。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

**最后更新：** 2026-10-08

## 最近改动

2026-10-08 | **Agent 通用 Token/Cost 跟踪治理全栈闭环**：done。用户端到端与真实大模型自动化闭环验收通过，合并入主分支。Runtime Service 实现自有 ledger、缓存计价与内部 Usage 汇聚；Platform API 实现模型费率快照与 Usage 授权网关代理；Platform Web 实装 Run/Thread 双级 Token/Cost 检查器、open-swe 风格上下文运行水位仪表（Usage Meter）、模型调用流水明细、服务端截断预警，以及模型编辑器 6 项费率 Decimal 安全配置与可逆清空保护；全栈真实模型自动化闭环与单测全绿。见 [专项](projects/20261007-agent-usage-cost-governance/README.md)。

2026-10-08 | **Agent 执行预算与软收尾全链路完成**：done。用户端到端自动化与人工验收通过，合并入主分支。Runtime/Platform API 完成通用预算模型限额薄扩展、managed 图余量、软时间、精确预算安全码、custom 白名单及隔离 Worker 验证；Platform Web 完成 Zod 白名单投影、弹性解包 safeExtractBudgetNotice、响应式 useRunBudget（200条LRU有界去重、增量指针防掉帧、运行态防闪烁、Run/namespace 隔离）、ChatAgentStatusBar Amber/Success 停机展示（预警态保留取消按钮、文案解耦、A11y）、子任务独立微横条/徽章、Thread 耗尽禁用分流；修复拖选退出、文案截断及继续执行报错消失；单测全绿，vue-tsc/ESLint 0 错误与 Vite build 全绿。见 [专项](projects/20261007-agent-execution-budget/README.md)。

2026-10-08 | **Agent 运行生命周期超时治理与排队死锁根除**：done。用户在真实浏览器端完成全链路验收。四图主子共享 attempt 预算、软收尾、模型 error 与 Worker timeout 分离；前端实装黄色超时警示胶囊、双通道停止确认；治本修复 `storageKey` 响应式漂移导致的本地 localStorage 幽灵未决锁残留，补充双重自愈机制与【放弃并恢复草稿】逃生通道；服务安全停止。见 [专项](projects/20261006-agent-run-timeout-governance/README.md) 及 [变更记录](apps/platform-web/docs/changes/20261007-prompt-queue-unconfirmed-deadlock-and-switch-healing.md)。

2026-10-07 | **Agent 模型调用稳定性治理**：done。Platform API/Runtime Service/Platform Web 全栈交付闭环。修复 FastAPI 500 强类型校验拦截与前端表单 step/就地保存高亮反馈；故障注入死端口实测 ModelResilienceMiddleware 毫秒级降级至 DeepSeek 备用模型并流式完成全生命周期；用户在浏览器端完成全链路人工实测，验收通过。见 [专项](projects/20261006-agent-model-resilience/README.md)。

2026-10-07 | **Agent 上下文窗口管理工程化**：done。Platform API/Runtime/Platform Web 完成全栈交付。后端与 Runtime 交付可信容量、预算 guard、隐藏摘要流、Context v5、受控维护 Run、私有字段脱敏；前端交付模型容量配置与展示（F01）、整理状态微胶囊及 4 秒自动淡出/草稿输入打断机制（F02）、手动维护动作与菜单守卫（F03）。隔离 PG、真实模型 10 次质量集、HTTP v2/v3、Worker 重启/回滚，以及前端 63 项定向单测、vue-tsc 0 错误与生产打包均通过。用户已在真实控制台与聊天会话中完成端到端人工实测，全链路验收通过，交付闭环。见 [专项](projects/20261006-agent-context-window-governance/README.md)。

2026-10-07 | **Agent 工具调用容错与生产接线全链路完成**：Runtime/Platform API 完成选择性错误分类、DearFlow/Showcase/Reference 主子图接线、MCP/workspace 边界、v3 tools 流安全出口和公开 fatal 脱敏；Platform Web 完成纯函数错误摘要提取、微胶囊 Tag 徽章与展开态格式化代码块排版；核心单测全绿（31 passed），静态类型与构建通过；三服务全栈浏览器联合验收 F01-F08 全部通过，全专项闭环 done。见 [专项](projects/20261006-agent-tool-error-resilience/README.md)。

2026-10-07 | **Agent 可观测性与追踪补齐**：全链路闭环完成。Runtime/Platform API 完成模型错误分类、安全诊断、启动阶段计时与只读投影；Platform Web 完成独立解耦面板 RunDiagnostics、Zod 白名单剔除敏感字段、防竞态 useRunDiagnostics、TrajectoryView 常驻入口与模式切换、ChatSession 历史 Run 自动拉取与最新默认选中；vue-tsc 0 错误、ESLint 0 错误、Vite build 与前端全仓 115 套件 535 项单测全绿。未部署现役服务。见 [专项](projects/20261006-agent-observability-hardening/README.md)。

2026-10-06 | **Agent 回答后推荐问题**：全链路完成。Platform API 与 Runtime Service 完成 suggestions 配置/生成、Delegation 隔离与 one-shot 推理；Platform Web 实装带 x-project-id 与单例缓存 API、思维链与多模态清洗纯函数、生命周期状态机（KeepAlive 补偿、Stop 抑制、竞态防护）、FollowUpSuggestions 紧凑展示组件与草稿冲突确认弹窗；27 项单测、vue-tsc 0 错误、ESLint 0 错误与生产打包全绿。未部署现役或远端平台。见 [专项](projects/20261005-agent-followup-suggestions/README.md)。

2026-10-05 | **定时 Agent 任务**：全链路完成。后端与隔离验收 done；前端定时任务模块实装，对标 playbook 与 control-plane 规范，吸纳 DeerFlow 纯函数 Cron 预设，支持 Card Grid 列表、双栏响应式 Inspector 抽屉、运行历史按需懒加载与权限守卫；481 项单测全绿、vue-tsc 0 错误、生产构建全绿。见 [专项](projects/20261005-scheduled-agent-tasks/README.md)。

### 同日流资源专项

2026-10-05 | **多会话流连接与运行缓存治理**：多会话与真实撤权浏览器、最终构建验证通过；GraphHarbor post39 双包已发布，本地 Runtime 已升级重启；Redis 从峰值 18.01 GiB 降至约 0.57 GiB。见 [专项](projects/20261005-chat-stream-resource-governance/README.md)。

### 同日权限专项

2026-10-05 | **平台权限状态与刷新治理**：本地 done。项目权限区分临时不可确认与真实拒绝；列表/后台刷新失败保留有效快照，路由与页面统一具体权限判断；作用域 403、刷新合并、认证服务 503 保留会话；Runtime ACL 共享连接池兼容文件路径加载，默认超时 10 秒。前端 473 passed/1 skipped、Runtime 114 项及最终定向 41 项、API 13 项/299 子测试、4 项故障注入及 4 项真实安全浏览器通过。未部署远端平台；Runtime 更改已随本次本地升级重启生效。见 [专项](projects/20261005-platform-access-refresh-governance/README.md)。

## 本月归并

2026-10（截至 10-08）| Token/Cost 全栈跟踪治理闭环（含真实大模型全链路 E2E）；执行预算与软收尾、超时治理与排队死锁自愈；模型稳定性降级、上下文窗口工程化；工具容错、观测、推荐问题和定时任务闭环；聊天、权限及流资源治理。

2026-09 | DearFlow Agent 全链路迁移（partial）、SSE 保活心跳与容错、GraphHarbor post37 子智能体历史持久化、跨服务规范治理（error-envelope/trace active）、权限治理、代码规范自动化与 Python 格式基线清理、前端 SWR 缓存治理、v0.5.0 里程碑发布。

## 活跃项目

- [Agent 通用 Token/Cost 跟踪与运行用量治理](projects/20261007-agent-usage-cost-governance/README.md)：done；Runtime + Platform API + Platform Web 全栈闭环，16 项隔离真实后端链路与包含真实大模型调用的 5 项 Playwright 自动化端到端测试全部通过，五重质量门禁全绿。未部署现役服务。
- [Agent 执行预算、步骤限制告警与软收尾](projects/20261007-agent-execution-budget/README.md)：done（全链路闭环）；Runtime 253 项回归、API 81 项回归与 23 场景真实 Worker 验证齐全；前端 F01-F04 实装并完成 116 套件 571 项单测、vue-tsc 0 错误、ESLint 0 错误。端到端自动化验收与人工实测完成。
- [Agent 运行生命周期超时治理](projects/20261006-agent-run-timeout-governance/README.md)：done；已完成正式post42接入、12组HTTP、匹配回退、前端T11超时治理与停止时序实装，以及T12用户真实浏览器端端到端联调验收（含排队死锁自愈）。本地服务已安全停止。
- [Agent 模型调用稳定性治理](projects/20261006-agent-model-resilience/README.md)：`done`；全链路闭环，Platform API、Runtime Service 与 Platform Web 全栈交付。后端模型恢复策略/受管备模型/分类重试/契约签名与网关快照、前端编辑页配置/真实失败态/推荐问题门禁/停止确认超时保护/备用模型微胶囊 Tag 全量实装；单测门禁全绿，故障注入主备降级实测通过，用户人工浏览器实测验收通过。
- [Agent 上下文窗口管理工程化](projects/20261006-agent-context-window-governance/README.md)：`done`；Platform API、Runtime Service 与 Platform Web 全栈交付闭环，模型容量配置/展示、整理状态微胶囊及平滑淡出、受控手动整理动作与全套单测/类型/构建门禁全绿，用户人工实测验收通过。
- [Agent 工具调用容错与生产接线补齐](projects/20261006-agent-tool-error-resilience/README.md)：done；全链路闭环，Runtime/API 共享选择性分类、主子图接线、安全消息与执行中缺根保护完成；Platform Web 纯函数摘要、微胶囊 Tag 徽章与格式化排版实装；核心单测全绿，浏览器联合验收 F01-F08 全部通过。未生产部署。
- [Agent 可观测性与追踪补齐](projects/20261006-agent-observability-hardening/README.md)：done（本地隔离环境全链路闭环）；Runtime/API 诊断与安全投影完成；Platform Web 独立解耦面板 RunDiagnostics、模式切换、防竞态 Composable 与全量门禁总检全绿（vue-tsc 0 errors、ESLint 0 errors、打包全绿、535 项单测全绿）。未部署现役服务。
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

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-10-08 | 锁定/安装正式 post42；四图主子共享 attempt 预算/软收尾，模型 error 与 Worker timeout 分开；模型稳定性降级、工具容错、上下文窗口管理、执行预算及 Token/Cost 跟踪治理（自有 ledger/缓存计价）全链路融合就绪；未部署现役。 |
| platform-api | 2026-10-08 | 私有预算注入拒绝/脱敏及停止确认透传；预算四精确安全码、custom 白名单、tasks/debug 错误清洗；模型恢复策略、上下文容量 CRUD 与 Run 诊断端点、模型费率快照与 Usage 授权网关代理全量实装；未部署现役。 |
| platform-web | 2026-10-08 | 预算告警投影、useRunBudget、ChatAgentStatusBar Amber/Success 停机展示、子任务独立微横条；超时警示黄色胶囊、双通道停止确认、排队提交死锁治本根除与切换自愈实装；备用模型微胶囊、工具错误摘要、运行诊断面板、上下文容量展示、Run/Thread 用量与成本检查器、open-swe 水位表全部融合；全仓单测、vue-tsc 与生产打包全绿。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-07 | 整单结束前须逐项核对未完成任务，未完成时只记Phase；用户批准的多会话发布协作经验已写入ai-workflow经验库，恢复时先核对正式产物归属与锁文件 |

## 近期关键决策

- 2026-09-21: 引入两阶段验证（Phase 验证 + Final 验证），禁止每改一小块就全量回归
- 2026-09-21: tasks.md 改为四段式结构（改动内容/代码位置/预期结果/验证项）
- 2026-09-21: 引入 Task Completion Card + 合规 checklist（可观测层）
- 2026-09-21: 引入 docs/CONTEXT.md（记忆层）+ docs/lessons/（反馈层）
- 2026-09-22: 全平台权限治理按人工批准实施；P1 ACL 属平台数据库，保留 D08 删除/审批、60 秒与激活刷新、限时审计 takeover；旧会话数据库历史已按授权清理。Runtime/GraphHarbor 代码不改，自定义角色 deferred，D24—D28 保留后续讨论。
- 2026-09-22: 批准采纳平台公共模型与项目私有模型 (BYOK) 双层架构决策（详见 docs/decisions/20260922-byok-project-model-architecture.md），解耦平台中心化底座与项目自主密钥，消除脱敏凭据误报假故障问题。
- 2026-09-27: 追踪审计查询性能本期仅记录实测数据；仓库无批准SLO，不临时设达标阈值。
