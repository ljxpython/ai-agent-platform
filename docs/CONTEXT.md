# 项目当前状态 - AI 上下文

> **最后更新：** 2026-10-13（知识文档/图片/v2非前端与Final done；真实Worker/Ubuntu RAG、去重/排队/Stop/在途关闭/回退通过，前端接续，所属服务停止）。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

**最后更新：** 2026-10-13

## 最近改动

2026-10-13 | **知识文档/图片平台接线非前端done**：普通executor两Agent原生审批→异步ready→另一成员新旧检索，跨Run处理中/ready同hash零新增入库用量、两项目排队/旧读、20MiB/Stop、撤权/Plan/跨项目、Fork/API/Worker/RAG重启、v1-v2历史及冻结版本回退/恢复通过。API223+182subtests、Runtime379+5Docker skip、Ubuntu RAG119、脚本5及50个后端Python静态检查通过；修复root namespace、图片私有收据/可信转换、5秒iat时差与关闭新上传保留已受理任务。Runtime/API配置恢复上传关闭/来源1，旧768 Ollama显式provider避免源码新配置污染，旧v1 query通过；临时RAG/SSH及本worktree7服务停止，数据保留。RAG/前端业务未改，未提交/合并/生产部署。前端逐文件F01–F06、真实fixture与恢复/发布交接就绪，详见[专项](projects/20261013-knowledge-documents-platform/README.md)。

## 本月归并

2026-10（截至 10-13）| 知识MCP及成员上传协议；Worktree原生隔离；F07/F05/后台A/B闭环。
2026-09 | DearFlow Agent 全链路迁移（partial）、SSE 保活心跳与容错、GraphHarbor post37 子智能体历史持久化、跨服务规范治理（error-envelope/trace active）、权限治理、代码规范自动化与 Python 格式基线清理、前端 SWR 缓存治理、v0.5.0 里程碑发布。

## 活跃项目

- [知识文档/图片平台接线](projects/20261013-knowledge-documents-platform/README.md)：本阶段非前端`done`，T01–T06/Final全部完成；真实多格式/图片/两Agent/成员共享、去重、权限、生命周期与回退通过。API223+182subtests/Runtime379+5Docker skip/RAG119/脚本5；默认upload关闭/v1，旧querysmoke通过、所属服务停止，数据保留。前端F01–F06与无mock浏览器接续，恢复/正式合入手册已交，未Git发布或部署生产。

- [项目成员知识上传平台接线](projects/20261012-project-member-knowledge-upload/README.md)：非前端及V02/Final完成，由20261013专项统一验收；不另建索引/缓存/队列，RAG main c30e2149。旧5be564a修复/模型波动证据保留；前端旧F01–F03代码需继续多格式/图片/v2及真实浏览器，不以模拟知识响应算入库。新增上传默认关闭，所属服务停止，未合并/生产发布。
- [项目知识检索 MCP 接入](projects/20261011-project-knowledge-mcp/README.md)：非前端通用链完成；B01 PDF/Office环境由Ubuntu联验解除，B02代表性10–20份业务资料/标注题仍待提供。前端来源卡与浏览器由同事接续。旧768文本库与新1024多模态库隔离，平台分支feat/project-knowledge-mcp尚未合入；服务停止、数据保留。
- [Agent 通用后台非阻塞任务能力](projects/20261009-agent-generic-production-capabilities/README.md)：`partial`；B01已由post45正式发布/锁接入和notify/Stop/撤权联合验收解除，T02/T03/T04/T06/T07/T09与F01-F11、A/B前后端完成。T01/T05/T08保留全范围验证和新Linux应用镜像门禁，T10/F12尚未全栈Final。新提交默认关闭，现役未部署。
- [F07 自动对话标题复用与补齐](projects/20261009-agent-thread-auto-title/README.md)：`done`；T01-T05 后端/Runtime/CAS、T06 前端接线、T07A 非前端验证、T07B 真实大模型 Playwright 联合闭环均已 100% 完成（首轮提炼“量子力学本质”+改名“老王科研保密项目”+二轮防竞态覆盖，全套 7 张实景截图落地）；用户实操人工验收通过，本地服务安全停止。
- [F05 Agent 模型上下文 PII 脱敏](projects/20261009-agent-pii-redaction/README.md)：`done`；全栈闭环完成，后端算法网关、前端错误消费草稿保留、Playwright 自动化测试闭环及全链路 E01-E03 验收 100% 通过。未部署现役。
- [F10 Agent通用文档读取能力补齐](projects/20261010-agent-document-reading/README.md)：`done`；全链路闭环，Runtime/API/Web 三服务全栈交付。同一 parse_document 补 DOCX/PPTX、定位/有界续读和 Docker reader，移除全 uploads 系统索引，FileRef/raw 接口保留。python-docx1.2.0 与专属镜像冻结；前端 MIME 纠正、原字节认证下载拦截、错误优先绝对高亮、DOCX 段落/表格与 PPTX 幻灯片语义化投影全部实装；Vitest 726 项全绿、vue-tsc 0 错误、ESLint 0 错误、生产构建成功；Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）自动化端到端测试 3 项全绿，4 张全景截图已留痕。用户人工浏览器实测验收通过，本地专属服务已安全停止。未部署现役。
- [Agent 运行完成通知与失败回调](projects/20261009-agent-production-capability-extension/README.md)：`done`。GraphHarbor/Runtime/API非前端实现、post44发布和交接完成；正式最短通过，native定时/回填部分证据已固化；前端 P4.1-P4.3 全部交付并通过 Vitest 与真实模型 Playwright E2E 闭环验收。用户人工实测验收合格，安全合并入主干。
- [F11 通用输入润色](projects/20261010-agent-input-polish/README.md)：评估与规划完成，用户确认暂缓（`deferred`），P2 候选、功能未实施。suggestions 复用、无 Thread 用途授权与旁路成本方案保留，未来重新投入时需人工批准；同事前端交接未排期。
- [Agent 通用 Plan Mode 与计划审批治理](projects/20261008-agent-plan-mode-governance/README.md)：`done`；三服务（Runtime/API/Web）全链路实施与自动化验收全部完成。后端双重门禁、原生审批、快照幂等与安全脱敏闭环；前端开关/徽章、待审卡片、输入框锁定、XSS 防御与状态自愈实装；静态代码门禁全部通过；Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）自动化端到端测试 100% 绿灯；7 张全景截图与 Thread/Run/interrupt 对账无误。未部署现役。
- [Worktree 本地栈资源隔离](projects/20261010-worktree-local-stack/README.md)：done；T01-T07全部验收，默认admin/admin123456、继承各app配置并自动对齐miaomiaoai deepseek-v4.1-flash默认模型策略，主库基础数据复用完成。源库只读，历史/令牌/定时任务排除；24项回归及真实三栈通过，资源回收；存量37条文档路径后置。
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

## 当前各服务状态（与主干最新对齐）

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| runtime-service | 2026-10-13 | 知识上传/图片私有收据与可信转换、root审批、来源v1/v2定位/F04预算已实现，Final379+5Docker skip；实际两Agent/成员共享/去重/排队/Stop/Fork/重启/回退通过，PDF/Office环境解除，业务题集质量另待；新增写默认关闭/v1，所属服务已停；锁定/安装正式 post45；F07精确标题委托、受管一次非流式调用就绪；受管后台执行/对账/Stop及A/B前后端已验，B01解除；新增 completion projector、安全白名单和受签 callback context；四图主子共享 attempt 预算/软收尾与 Run Token 额度；F05 PII脱敏默认关闭，模型副本/旁路脱敏与结构失效阻断已实装；F04 官方参数压缩/主备阈值与正文 SHA256 引用保护（filesystem_cls 预算）全链路闭环；F02 共享循环检测中间件（连续 3 轮预警与 5 轮安全硬终止拦截）、Worker 接管支持、真实模型验证通过；Plan 公共状态/三工具/双门禁、四图主子接线、Context v6 和规划 memory 跳过完成；解除默认 4096 max_tokens 兜底限制，系统提示词强化思考链 Token 预算约束；模型稳定性降级、工具容错、上下文窗口管理、执行预算及 Token/Cost 跟踪治理与运行准备幂等/有界重试全链路融合；Workspace 执行容错闭环；F15评估关闭；F11 暂缓；F10 固定 Docker reader/DOCX/PPTX 有界续读/附件索引收紧与全链路验收已闭环；未部署现役。 |
| platform-api | 2026-10-13 | 成员知识三角色权限/四GET/四用途HMAC、图片原名query贯通已实现，Final223+182subtests含真实PG并发及SQLite/PG迁移；5秒iat容差无过期宽限，上传开关仅禁新upload、在途start/activate仍复核权限；实际RAG/Worker/成员链通过，新增写默认关闭，所属服务已停；知识MCP可信项目绑定/公开边界已实现，新Thread/fork重签，用户/服务账号撤权实测通过；F07首轮opt-in/私有seed与公开pending、comment+edit与CAS就绪；后台四入口/精确operation/DTO/ACL/审计/HMAC与guard已验；post45正式acceptance adapter、最终bytes/key/digest发送前落盘与平台迁移0007完成，Platform132+116subtests/真实PG迁移1通过，发布后notify/Stop/撤权联合通过，B01解除；新增 migration 20261009_0007、origin/event/receipt、HMAC receiver、历史 completion、私有 feed/read、ACL/deletion suppression 和 cron backfill；F05 精确隐私失败投影、私有策略剥离与标题 Thread 委托已验；F04 契约与回归通过，无破坏性改动；私有预算/Token/loop 注入拒绝与脱敏；执行预算、F01 Token 及 F02 loop 精确安全码；Plan 原生审批/ACL/幂等、Context v6执行链、公开agent_plan/fork/cron边界完成；Run Usage 可选 token_budget DTO、ACL/撤权真实链路通过；模型恢复、上下文、诊断、费率 Usage、Stop 接口均已实装；Workspace 五码精确投影与 DTO 校验完成；F10 Office MIME网关与六字段/撤权/审计、两图真实链路专项验收完成；未部署现役。 |
| platform-web | 2026-10-13 | 知识文档F01–F06多格式/图片/完整JSON/审批回执/v2来源定位/轮询及知识库大面板已全部落地，Playwright + Chromium真实模型（deepseek-v4.1-flash）端到端自动化测试8步全绿闭环通过，8张全流程实景截图留痕；MCP目录工具防盲搜死循环优化落地；用户现场实测验收通过；所属服务已停止。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-12 | 知识授权回调纳入本环境生成，旧Worktree缺/空新增回调从本登记API派生，显式跨环境拒绝；脚本5项与重启ready通过；全场景本地原生PG/Redis优先及禁止滥用Docker硬约束实装；Worktree 开发/联调前必读 worktree-development 规范；统一登记隔离资源，共享依赖缓存但独立安装，默认本地账号 admin/admin123456、默认模型对齐 miaomiaoai deepseek-v4.1-flash、配置继承与首次只读基础数据初始化已验收；知识MCP/独立Ollama新增登记/所属启停，4项自检及真实重启通过。7个既有Worktree已同步31个本地栈工具/规范文件；未来新Worktree需从包含该基线的提交创建。Worktree依赖/真实Worker隔离、模型配置重加密、源历史与新审计区分及多会话发布协作经验已写入[ai-workflow](lessons/ai-workflow.md)；回调/迁移回退/Docker日志/执行目录经验已写入[runtime-service](lessons/runtime-service.md)。整单结束前须逐项核对未完成任务，未完成时只记Phase；恢复发布任务时核对正式产物归属与锁文件。 |

F07实施与验证入口以tasks.md/verification.md为准；正式post43和同名本地CAS候选来源/哈希不同，不能只凭版本名认定正式能力。
