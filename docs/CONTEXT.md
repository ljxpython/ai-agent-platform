# 项目当前状态 - AI 上下文

> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则：** 只保留"当前有效"信息，过期内容直接删除；历史在 `docs/projects/` 和 `docs/changes/` 里。

## 最后更新

2026-10-03 | Runtime 视觉识图全面支持 DeepSeek 官方多模态与盲吞异常消灭完成（done）：彻底解决 `analyze_image` 强绑定火山豆包及盲吞异常抛出无用废话问题。实现 `resolve_vision_config` 多级配置解析（通用 `VISION_*` > DeepSeek 官方配置 `DEEPSEEK_*` > 兼容回退 `DOUBAO_*`）；默认采用 `deepseek-flash` 官方多模态识图；彻底透出底层真实 `error.code` 与 `message`；单测全绿（22 passed）并通过真实页面截图端到端识图实测验收。

2026-10-02 | 长会话断流恢复解耦与历史快照按需懒加载治理完成（done）：彻底根治 100+ 步长会话下 Checkpoint 历史快照（3.4MB+）导致的断流重连 504 假死超时。解耦 useChatSession.ts 中 recoverExpiredStream 对巨型 service.history 的强制阻塞等待，仅拉取轻量级 service.state 实现 0.05 秒瞬时极速自愈，并转为非阻塞异步预热与静默软降级；加固 ChatSession.vue 移除 loadHistory 错误对全局红色横幅的污染，并增加抽屉展开懒加载守卫；新增 504 容错单测（24 passed），全量 19 套聊天组件单测（67 passed）与 pnpm build 打包全绿。

2026-10-02 | DearFlow Agent 创意模式防死循环与无头测试防卷护栏完成（done）：彻底解决“小惊喜”与创意单页场景下 Agent 自建无头测试（osascript/JXA mock DOM/Audio）与递归调用 fetch_web_guidelines 导致的 50 步 ModelCallLimitExceeded 假死熔断问题。明确 fetch_web_guidelines 仅限显式静态审计任务，在 prompts.py 中确立单文件编写完成即刻 present_artifacts 交付原则，严禁在无真实浏览器环境中编写复杂 mock 自测脚本；定向 Agent 单测（24 passed）与 Ruff 格式全绿。

2026-10-02 | DearFlow Agent 灵感建议与“小惊喜”创意工坊完成（done）：全面落地原版 deer-flow 创意互动体验。前端实装微物理动效 ConfettiButton 与可扩展灵感胶囊栏 ComposerSuggestions（含“🎉 小惊喜”、“📝 深度写作”、“🔬 敏捷调研”、“📊 数据洞察”、“💻 交互单页”），并无缝集成 ChatComposer 双向草稿同步；后端在 DearFlow Agent 提示词中确立单文件零依赖纯原生创意编程规范（Web Audio 合成音效 + Canvas/SVG 微动画），与 SandboxedHtmlFrame 形成高保真免刷新试玩闭环；全量前端 Vitest（19 套/67 项）通过，pnpm build 打包通过，后端 Agent 单测（33 项）全绿。

2026-10-02 | DearFlow Agent 接入 Jina Reader 网页深度提取与双通道容灾完成（done）：落地 deer-flow 架构哲学，形成“Tavily 语义搜索（search_web）+ Jina Reader 高质量 Markdown 正文阅读（fetch_page）”黄金组合。实现 jina_extract 并改造 fetch_page 支持 Jina 优先、异常/超时平滑降级 Tavily Extract，严守 public_url SSRF 防护与 _evidence SHA256 原子硬链接落盘；agent.py 解耦工具过滤判定；15 项 research 单测全绿，真实网络端到端提取实测通过。

2026-10-02 | 工作区 HTML 现代化沙箱渲染支持完成（done）：彻底解决智能体生成的单文件 HTML 在工作区中由于一刀切禁用脚本/外链导致的 Tailwind CSS、Google Fonts 样式坍塌问题。采用双重防御模型：前端 SandboxedHtmlFrame 授予 sandbox="allow-scripts" 但坚决剔除 allow-same-origin（Origin 锁定为 null 杜绝窃取凭据与跨域 DOM 越权），后端 html_preview.py 升级白名单 CSP（放行常见公认安全 CDN，严格限制 connect-src https: 杜绝内网探测）并扩充 link/script/svg 白名单；全量 43 项 Python 工作区单测全绿，前端 Vitest 验证通过，真实博客 HTML 渲染 100% 还原。

2026-10-01 | Runtime 数据库精简重构完成：新增 Scope 类型和 Memory/Skills SQL helper，保留原事务及锁边界；43 项 PostgreSQL 定向测试通过，全量 564 passed / 61 skipped / 2 failed。Docker 不可用与终端文件未生成两项失败在原 Memory/Skills 源码对照下复现，见专项验证记录。

2026-09-30 | Workflow Demo 模型连接修复：复用公共 fetch_model_connection，补齐模型配置请求签名与异常配置拒绝行为，保留响应节点延迟获取和审批恢复引用优先级。用户确认保留 Agent 显式装配模型、工具和中间件，本轮不实施 RuntimeAgentHarness 架构重构。

2026-09-30 | DearFlow Agent 真实案例端到端全链路实录交付：在 `docs/architecture/07-agents/01-dearflow-agent/` 交付重磅实录《07-真实案例端到端全链路生命周期实录：从用户一句话到沙箱结果落盘》，以真实生产复合场景（GitHub分析+Python沙箱绘图+不可变制品发布+长期记忆注入）为抓手，深度解密 Platform-Web 乐观更新与 SSE 泵、Platform-API 双层 RBAC 与 60s Delegation JWT 签发、Runtime 控制面与 MessageInbox 咨询锁入库、Worker 调度与 10+ 中间件洋葱圈拦截、Docker 断网沙箱与原子硬链接发布，以及在 PostgreSQL、Redis 和物理磁盘上的状态演进细节与 6 重安全栅栏。

2026-09-30 | runtime-service 可观测性与追踪管线专篇交付：完成概念专篇《12-运行时可观测性架构、Langfuse 与 OTel 追踪管线深度剖析》，逐一拆解 `apps/runtime-service/src/runtime_service/observability/` 架构与源码，深度剖析 `_FailSoftCallback` 软着陆动态代理吞噬 APM 异常防止业务中断、零信任元数据消杀与敏感密钥粉碎、本地常驻 `_RuntimeDiagnosticsCallback` 离线 0.05 秒自测断言，以及 5 秒守护线程优雅排空防死锁机制；在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service 猴子补丁与人机中断专篇交付：完成概念专篇《11-LangGraph 官方源码级猴子补丁与人机中断避坑深度剖析》，调用官方 MCP 查证 upstream 最新 main 分支源码，深度解密 `patches.py` 方法级替换（Method Swizzling）消灭 `StreamToolCallHandler` 把人机审批当中断的流式假报警、防御 `ToolNode` 异步冒泡吞没缺陷，阐述类方法零侵入自执行与幂等守卫；并在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service Web控制面与消息对账专篇交付：完成概念专篇《10-运行时 Web 控制面、消息收件箱与对账引擎深度剖析》，逐一拆解 `apps/runtime-service/src/runtime_service/webapp.py` 核心职责，深度剖析 `lifespan` 强杀清理 Docker 伪终端僵尸容器、8 大业务子路由汇聚大厅、`MessageInbox` 咨询锁原子入库与 `reconcile_run` 终态自愈对账机制；在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service 工具/技能/沙箱架构边界澄清：在 `04-tools-and-skills.md` 中重磅补充第一节《核心架构澄清：我们常说的“薄封装”到底封装了什么？Tools / MCP / Skills / 沙箱来自哪里？》，全面破除“LangGraph包办沙箱与技能”的误解，确立“LangGraph专职状态图调度 + LangChain BaseTool协议归一 + MCP安全网关转译 + DeepAgents技能治理 + 平台自研Docker断网沙箱”四分天下架构全景。

2026-09-30 | runtime-service 工作区沙箱与资产管线专篇交付：完成概念专篇《09-工作区沙箱、PTY终端与资产管线深度透析》，逐一拆解 `apps/runtime-service/src/runtime_service/workspace/` 全部 15 个文件职责，深度透析 `scoped.py` 单向哈希物理路径隔离、`execution.py` 断网无特权 Docker 极苛沙箱、`terminal.py` 环形缓冲交互 PTY、`archives.py` 内存流式防解压炸弹与 Zip Slip、`html_preview.py` 严格白名单与超强 CSP 消杀防 Stored XSS，以及 `artifact_refs.py` 基于 `dir_fd` 与 `os.link` 原子硬链接发布不可变交付物；在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service 数据库双轨制专篇交付：完成概念专篇《08-Runtime 数据库双轨制架构与应用表全景透析》，揭秘为什么 `db/` 几乎无代码，深度剖析引擎链（LangGraph 官方表托管 checkpoints）与应用链（`0001_application.py` 四大约束表 inbox/memory/skills/tasks）分工、无 ORM 原生 SQL 设计哲学与控制面 vs 执行面数据边界划分；并在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service 核心内核模块剖析专篇交付：完成概念专篇《07-Runtime 核心内核模块源码全景剖析与职责透析》，逐一拆解 `apps/runtime-service/src/runtime_service/runtime/` 全部 11 个文件职责，包含真实业务攻防推演、DearFlowAgent 组合根源码调用映射、0.05秒脱机极速自测范式与本地脱机 vs 生产运行态持久化落盘（runtime_message_inbox + checkpoints）分水岭剖析；在 `01-architecture.md` 与全局概念总字典中完成全量挂载。

2026-09-30 | runtime-service 架构深潜与请求验签消杀专篇交付：完成概念专篇《06-请求验签与配置净化全链路深度透析》，深度解密海关边检大厅模型、`auth/platform.py` Delegation JWT 60s 验签与 `@auth.on` 防跨线程越权守卫、`runtime/` 18 类高危配置熔断消杀、工具黑名单物理求差与模型凭据用完即焚拉取；并在 `01-architecture.md` 与全局概念总字典中完成挂载。

2026-09-30 | runtime-service 架构深潜与 MessageInbox 专篇交付：完成概念专篇《05-MessageInbox 数据库咨询锁与消息对账全链路深度透析》，剖析传菜窗木板模型、为什么 PostgreSQL 咨询锁（pg_advisory_xact_lock）完爆行锁、租约超时自愈、全链路 4 大阶段调用时序与 Checkpoint 确定性对账闭环；完成 `01-architecture.md` 原生表格重构（彻底解决 Typora 下 HTML details 折叠失效与标签裸露 Bug），并在 README.md 概念总字典完成全量注册。

2026-09-30 | RuntimeAgentHarness 专项立项规划完成：针对 Runtime 执行层 Agent 组合根样板代码超标（150+行安全胶水代码）、安全验签重复建设与测试体验痛点，完成标准项目文档规划（README/plan/tasks/verification），提出 AgentBuildContext 与 @runtime_agent 框架解耦模式。

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
| runtime-service | 2026-10-03 | 图像识别分析工具（analyze_image）支持 DeepSeek 官方多模态识图（deepseek-flash）与通用 VISION_*，消灭盲吞异常并保留错误详情；单测全通 |
| platform-api | 2026-09-28 | 存量 Python 诊断全部清零且 100% 格式化；网关层放通 checkpoint_ns 与 /state/checkpoint；网关层 SSE 流保活心跳注入保持；单测全通 |
| platform-web | 2026-10-02 | 解耦断流恢复对 3.4MB 巨型 history 的阻塞依赖，毫秒级极速自愈并后台静默预热；加固 ChatSession 抽屉懒加载与错误隔离；ChatComposer 接入灵感胶囊栏与撒花微动效；SandboxedHtmlFrame 免刷新预览；单测全通与打包通过 |
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
