# 项目当前状态 - AI 上下文

> **最后更新：** 2026-10-10（F04 工具输出预算前端收尾与全链路闭环 done，三服务隔离栈持续常驻等待验收）。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

**最后更新：** 2026-10-10

## 最近改动

2026-10-10 | **F04工具输出预算前端收尾与全链路联合验收**：done。前端完成大工具结果防爆加固：`transcript.ts` 与 `trajectory-adapter.ts` 引入 `${namespace}:${callId}` 复合键隔离映射并优先消费落盘 ToolMessage，根治流式 110 KB 跳变与父子任务同名 ID 覆盖；`ToolResult.vue` 拦截 `/large_tool_results/` 虚拟路径详情跳转防 404、强化十六进制 Hash 与长路径 `break-all` 防 390px 溢出、补齐数组与对象格式证据来源解析；Vitest 3 文件 42 项全绿、`vue-tsc` 0 错误、`pnpm build` 成功；Playwright + Chromium 端到端自动化驱动隔离栈三服务与真实大模型（百炼 · qwen-plus）多轮问答、流式输出、轨迹排障及 F04-W01~W09 多视口全流程验证通过，8 张高保真验证截图已持久化；三服务常驻待人工验收。详见[15专题](projects/20260913-dearflow-agent/15-tool-output-budget-review.md)和[前端落地文档](projects/20260913-dearflow-agent/frontend-handoff-f04.md)。

2026-10-08 | **Agent Workspace 执行容错与安全报告**：done（非前端范围闭环，代码及测试合入主干）。共享 Workspace 失败保护、不可达/结果未知停止 Run、取消清理与资源安全回收、v1 诊断记录与 platform-api 精确五码投影全部实装闭环；本地与 Docker 真实验证通过，前端交接报告与 DTO 已固化。见 [专项](projects/20261007-agent-workspace-resilience/README.md)。

2026-10-08 | **Agent 会话停止与状态报告闭环（全链路）**：done。后端会话停止、回执详情/分页、幂等重试、后台恢复与审计闭环；前端完成三接口接入、严格 Zod DTO 校验、useThreadStopControl 状态机解耦、45s 超时降级与单飞保护、RunStopReportBanner 顶部提示条与 RunStopReportDetails 抽屉报告。vue-tsc 0 错误、ESLint 0 错误、Vite build 生产构建通过、Vitest 115 文件 553 项单测全绿；Playwright + Chromium 驱动三服务连接真实模型 `百炼 · qwen-plus` 自动化端到端测试全链路通过（耗时 10.57s，1440/768/390 视口截图已留痕），用户人工验收通过并零功能损失合并入主分支。详见 [专项](projects/20261007-agent-run-cancellation/README.md)。

2026-10-08 | **Agent 运行准备幂等与有界重试**：全链路闭环完成。公共 prepare latch、目录修复/篡改拒绝、按 graph 的模型/只读 task 有界重试、部分流保护、provider 终止与 Worker 基础设施恢复分离已实现；v1 diagnostics 新增安全 preparations/retries。Platform Web 完成拆分 RunPreparationsSection 与 RunRetriesSection 专职展示子组件，严格 attempts/role 正则防注入与琥珀色降级；49 项定向单测、vue-tsc 0 错误、eslint 0 错误、生产打包全绿；Playwright + Chromium 全链路三服务真实模型问答、轨迹排障及 F01-F10 专项浏览器视觉与安全验收全部通过，全流程截图留存。专项 done，未部署现役。见 [专项](projects/20261007-agent-production-capabilities/README.md)。

2026-10-08 | **Agent 通用 Token/Cost 跟踪治理全栈闭环**：done。用户端到端与真实大模型自动化闭环验收通过，合并入主分支。Runtime Service 实现自有 ledger、缓存计价与内部 Usage 汇聚；Platform API 实现模型费率快照与 Usage 授权网关代理；Platform Web 实装 Run/Thread 双级 Token/Cost 检查器、open-swe 风格上下文运行水位仪表（Usage Meter）、模型调用流水明细、服务端截断预警，以及模型编辑器 6 项费率 Decimal 安全配置与可逆清空保护；全栈真实模型自动化闭环与单测全绿。见 [专项](projects/20261007-agent-usage-cost-governance/README.md)。

2026-10-07 | **Agent 工具调用容错与生产接线全链路完成**：Runtime/Platform API 完成选择性错误分类、DearFlow/Showcase/Reference 主子图接线、MCP/workspace 边界、v3 tools 流安全出口和公开 fatal 脱敏；Platform Web 完成纯函数错误摘要提取、微胶囊 Tag 徽章与展开态格式化代码块排版；核心单测全绿（31 passed），静态类型与构建通过；三服务全栈浏览器联合验收 F01-F08 全部通过，全专项闭环 done。见 [专项](projects/20261006-agent-tool-error-resilience/README.md)。

2026-10-07 | **Agent 可观测性与追踪补齐**：全链路闭环完成。Runtime/Platform API 完成模型错误分类、安全诊断、启动阶段计时与只读投影；Platform Web 完成独立解耦面板 RunDiagnostics、Zod 白名单剔除敏感字段、防竞态 useRunDiagnostics、TrajectoryView 常驻入口与模式切换、ChatSession 历史 Run 自动拉取与最新默认选中；vue-tsc 0 错误、ESLint 0 错误、Vite build 与前端全仓 115 套件 535 项单测全绿。未部署现役服务。见 [专项](projects/20261006-agent-observability-hardening/README.md)。

## 本月归并

2026-10（截至 10-10）| F04 工具输出预算前后端全链路闭环；会话停止与报告闭环；Token/Cost 全栈跟踪治理；运行准备幂等与重试；执行预算与软收尾；超时治理与排队死锁自愈；模型稳定性降级、上下文窗口工程化；Workspace 执行容错与安全报告；工具容错、观测、推荐问题和定时任务闭环；聊天、权限及流资源治理。

2026-09 | DearFlow Agent 全链路迁移（partial）、SSE 保活心跳与容错、GraphHarbor post37 子智能体历史持久化、跨服务规范治理（error-envelope/trace active）、权限治理、代码规范自动化与 Python 格式基线清理、前端 SWR 缓存治理、v0.5.0 里程碑发布。

## 活跃项目

- [Agent Workspace 执行容错与安全失败报告](projects/20261007-agent-workspace-resilience/README.md)：`done`（非前端本地与 Docker 范围全部闭环，全栈代码与测试已合并进入主干；前端交接与报告已固化）；后端五精确安全码、结果未知停止、取消回收与诊断记录已融合闭环。未部署现役。
- [Agent通用运行取消与中断能力](projects/20261007-agent-run-cancellation/README.md)：`done`（全链路闭环）；后端三接口、持久Stop/恢复、inbox屏障与确定性报告完成；前端Stop控制器状态机、Banner、Drawer与真实模型Playwright E2E自动化闭环完成（F01–F10闭环，截图已留痕，用户实测验收合格）；B01解除；B02等待正式PyPI发布指令/正式源锁接入。
- [Agent 运行准备幂等与有界重试](projects/20261007-agent-production-capabilities/README.md)：done；公共 prepare latch、目录修复、有界重试与诊断接口已实现，前端双专职子组件实装，49 项单测与 Playwright + Chromium 全链路自动化 E2E 闭环全部通过。未部署现役。
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
- [DearFlow Agent迁移重审与补齐](projects/20260913-dearflow-agent/README.md)：整体partial；接续以12的T01—T10为入口。2026-10-10 [15/F04](projects/20260913-dearflow-agent/15-tool-output-budget-review.md)全链路done，R01—R04/R05-A后端实现与真实HTTP/PG/Worker质量回退通过，R05-B前端防爆加固、42项单测、Playwright真实模型E2E及8张截图通过，R05-C联合验收闭环。14效果审计原可靠性/Todo缺口及其余T07日志事项保留，不因F04实施而标完成；音视频/新版扩展单独评审。
- [子智能体工具调用历史持久化与回放能力支持](projects/20260928-graphharbor-subagent-tool-history/README.md)：done；GraphHarbor post37 升级与 platform-api 网关层放通，全链路端到端真实用例实测通过，子智能体内部 10 次工具调用全数可查。
- [SSE 事件流保活心跳与连接容错治理](projects/20260927-sse-stream-heartbeat-and-resilience/README.md)：done；针对每隔 45 秒频繁弹出“恢复连接”假性报错条及重放历史中断导致审批死锁的问题，通过 Platform API 网关注入心跳与前端审批状态机自愈彻底根治；探针实测与单测全绿；GraphHarbor 专属心跳与中断重放两份修复文档已交付。
- [消息内部Run回查委托修复](projects/20260927-message-run-read-delegation/README.md)：partial；Platform API只在消息入口转发请求内已有read委托，Runtime配对验证后用于内部Run GET；本机自动化通过，现役跨服务链路未验证，未部署。
- [Runtime 与 GraphHarbor 业务边界解耦](projects/20260925-runtime-business-boundary-decoupling/README.md)：`partial`，本机两库已清理旧运行数据并迁移，归档隔离恢复通过，正式依赖 post33 已锁定。单项目 run/SSE/HITL 与文件正向链路已有证据；官方全入口差分、跨项目故障和回退门禁仍缺。

## 各服务当前状态

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-10-09 | F04非前端done：官方参数压缩/主备阈值与正文SHA256引用保护，真实HTTP/PG/Worker/审批/回退/质量均验；仅前端接续。当前锁定/安装正式post43（本轮未升级）；四图主子共享attempt预算/软收尾，模型error与Worker timeout分开；稳定性降级、工具容错、上下文窗口管理、执行预算及Token/Cost跟踪、运行准备幂等/有界重试已融合；持久Stop/租约恢复、inbox屏障、资源证据及确定性报告、Workspace执行容错/取消回收已融合；未部署现役。 |
| platform-api | 2026-10-09 | F04现有state/history/v2-v3/ACL/Workspace契约回归通过，无新API/DTO或生产源码改动；普通files和原文tools流维持现状。私有预算注入拒绝/脱敏及停止确认透传；预算四精确安全码、custom 白名单、tasks/debug 错误清洗；runtime_prepare 私有字段防注入/公开剥离；diagnostics v1 增 optional preparations/retries 与 workspace_executions；Workspace 五码精确投影与 DTO 校验完成；模型恢复策略、上下文容量 CRUD 与 Run 诊断端点、模型费率快照与 Usage 授权网关代理、会话 cancel/detail/list 及精确委托全量实装；未部署现役。 |
| platform-web | 2026-10-10 | F04大工具输出预算加固实装：transcript复合键防覆盖与ToolMessage优先、ToolResult虚拟路径防跳转与多格式证据来源解析；42项单测、vue-tsc 0错误、Playwright真实模型端到端E2E全绿；会话停止控制器与状态机、停止报告抽屉及 Banner 全链路实装；运行准备与重试摘要、预算告警投影、超时警示黄色胶囊、双通道停止确认、排队提交死锁治本根除与切换自愈实装；备用模型微胶囊、工具错误摘要、运行诊断面板、上下文容量展示、Run/Thread 用量与成本检查器、open-swe 水位表全部融合；全仓单测、vue-tsc 与生产打包全绿。未部署现役。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-08 | 整单结束前须逐项核对未完成任务，未完成时只记Phase；用户批准的多会话发布协作经验已写入ai-workflow经验库，恢复时先核对正式产物归属与锁文件。 |

## 近期关键决策

- 2026-09-21: 引入两阶段验证（Phase 验证 + Final 验证），禁止每改一小块就全量回归
- 2026-09-21: tasks.md 改为四段式结构（改动内容/代码位置/预期结果/验证项）
- 2026-09-21: 引入 Task Completion Card + 合规 checklist（可观测层）
- 2026-09-21: 引入 docs/CONTEXT.md（记忆层）+ docs/lessons/（反馈层）
- 2026-09-22: 全平台权限治理按人工批准实施；P1 ACL 属平台数据库，保留 D08 删除/审批、60 秒与激活刷新、限时审计 takeover；旧会话数据库历史已按授权清理。Runtime/GraphHarbor 代码不改，自定义角色 deferred，D24—D28 保留后续讨论。
- 2026-09-22: 批准采纳平台公共模型与项目私有模型 (BYOK) 双层架构决策（详见 docs/decisions/20260922-byok-project-model-architecture.md），解耦平台中心化底座与项目自主密钥，消除脱敏凭据误报假故障问题。
- 2026-09-27: 追踪审计查询性能本期仅记录实测数据；仓库无批准SLO，不临时设达标阈值。
- 2026-10-07: 会话停止采用双通道自愈与精确委托，原生 cancel-active 入口绑定 context_hash，支持持久回执与离线报告。
