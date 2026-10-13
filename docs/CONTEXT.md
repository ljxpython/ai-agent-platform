# 项目当前状态 - AI 上下文

> **最后更新：** 2026-10-13（Runtime 单节点远端沙箱本期用户验收通过、done；正式整机重启/后续独立 Final、真实编辑及夹具/interrupt 排查转 deferred。所属五服务已停止，用户授权专项 Git 交付、安全合并与 Worktree/专属数据库清理）。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

**最后更新：** 2026-10-13

## 最近改动

2026-10-13 | **Runtime 三模式沙箱本期验收与交付**：用户明确验收通过、问题后续完成，专项 done。local/本地 Docker/sshmy2 HTTPS+mTLS Node、持久绑定、文件/Office/skills/PTY/后台、2 槽与容器/数据独立回收交付；公网两图/真实模型/浏览器/权限/Stop/fork/隔离、安全/性能/进程恢复/回退已验，B01/B02 解除。Runtime 广泛回归 1713 passed，离线 daemon 的 Office 四项相关复验6 passed；API42/Web51/容量12；媒体修复独占库65 passed/3 skipped，失败与跳过原事实保留。wawapii 生图成功，两次编辑 unknown 可能计费；正式整机重启/后续独立 Final、编辑下载/响应留存夹具与残留 interrupt 转 [F01–F04](projects/20261012-runtime-remote-docker-sandbox/follow-ups.md)，不重购、不再重启。五项所属开发服务已停止，原 local 配置已恢复；Git 交付/安全合并及专属数据库/Worktree 清理已授权，执行中。deer-flow 两模块原样来源/MIT 与两条批准经验已落笔；平台无产品代码变更，现役平台未切流。

## 本月归并

2026-10（截至10-13）| 三模式沙箱本期验收完成；原生资源与 Worktree 隔离；F07/F05/后台接受回执/Token看板全栈闭环。
2026-09 | DearFlow Agent 全链路迁移（partial）、SSE 保活心跳与容错、GraphHarbor post37 子智能体历史持久化、跨服务规范治理（error-envelope/trace active）、权限治理、代码规范自动化与 Python 格式基线清理、前端 SWR 缓存治理、v0.5.0 里程碑发布。

## 活跃项目

- [Runtime 单节点远端 Docker 沙箱](projects/20261012-runtime-remote-docker-sandbox/README.md)：done（2026-10-13 用户本期验收）；T00–T15 本期收口，B01/B02 解除；正式整机重启/后续独立 Final、真实编辑和留存夹具/interrupt 排查 [deferred](projects/20261012-runtime-remote-docker-sandbox/follow-ups.md)。五服务已停；用户授权 Git 交付、安全合并、Worktree/专属数据库清理，执行中。
- [后台任务接受回执接入与联合收口](projects/20261011-background-acceptance-closeout/README.md)：`done`；全栈闭环完成，前端修补、Playwright 真实模型自动化测试与三视口全景留痕通过，用户人工验收通过，已合并入主干。
- [平台/项目Token看板](projects/20261011-token-usage-dashboard/README.md)：`done`；全栈端到端实现、B01容量优化、W01–W04前端交付、无头抽屉复用、布局防抖消除、503容量饱和适配全部完成；Playwright真实模型端到端自动化联合复验通过（24.1s，全套截图已留痕）；用户人工浏览器实测验收通过，本地服务已安全停止。
- [Agent 通用后台非阻塞任务能力](projects/20261009-agent-generic-production-capabilities/README.md)：`done`；接受回执接入与联合收口闭环，所有剩余门禁已回填并通过。新提交默认关闭，现役未部署。
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
| runtime-service | 2026-10-13 | 单节点三模式沙箱本期用户验收 done：完整公网两图/浏览器/Worker/Stop/文件恢复/隔离、安全/性能/回退与源/MIT已验；所属五服务停止。正式整机重启/后续独立 Final、wawapii 编辑下载/留存夹具及残留 interrupt 转 F01–F04 deferred；生图成功、两次编辑 unknown 可能计费，保全原回执不重购；媒体 caller 候选 wheel 未部署 Node。用户授权 Git 交付/安全合并与专属资源清理，现役平台未切流。Token看板HMAC两入口、0004索引/0005可重建桶、精确Run位集合/脏补齐/重建及单查询线程/连接已验；公开百万容量两轮和写影响通过、B01解除，原额度恢复/价格保留；真实PG/应用重启、旧应用保留0005链回退及DeepSeek核账/安全通过。聚合负载与迁移回退经验已沉淀；修复credential_id认证500。锁定/安装正式 post45；F07精确标题委托、受管一次非流式调用就绪；B01接续修复 credential/callback 共存与 Stop 候选过滤，冷 Linux 镜像/两根真实模型及原矩阵非前端 Final 通过，K01–K08 done；受管后台执行/对账/Stop及A/B前后端已验；新增 completion projector、安全白名单和受签 callback context；四图主子共享 attempt 预算/软收尾与 Run Token 额度；F05 PII脱敏默认关闭，模型副本/旁路脱敏与结构失效阻断已实装；F04 官方参数压缩/主备阈值与正文 SHA256 引用保护（filesystem_cls 预算）全链路闭环；F02 共享循环检测中间件（连续 3 轮预警与 5 轮安全硬终止拦截）、Worker 接管支持、真实模型验证通过；Plan 公共状态/三工具/双门禁、四图主子接线、Context v6 和规划 memory 跳过完成；解除默认 4096 max_tokens 兜底限制，系统提示词强化思考链 Token 预算约束；模型稳定性降级、工具容错、上下文窗口管理、执行预算及 Token/Cost 跟踪治理与运行准备幂等/有界重试全链路融合；Workspace 执行容错闭环；F15评估关闭；F11 暂缓；F10 固定 Docker reader/DOCX/PPTX 有界续读/附件索引收紧与全链路验收已闭环；未部署现役。 |
| platform-api | 2026-10-13 | 沙箱专项仅现有网关/ACL/分享撤权/fork/PTY/后台/错误契约回归，42 passed/1 skipped与公网真实链已验，无产品代码改动。Token看板三GET、usage两权限、当前范围/ACL/cursor/审计及merge0008已验；整链路2admission槽/5秒含排队，新增503 fixture；公开百万容量两轮通过、B01解除，不直查Runtime库；F07首轮opt-in/私有seed与公开pending、comment+edit与CAS就绪；后台四入口/精确operation/DTO/ACL/审计/HMAC与guard已验；post45正式acceptance adapter、最终bytes/key/digest发送前落盘与平台迁移0007/0008/0009完成，SQLite/PG、固定字节/只读回执/guard与独立非前端Final通过，notify/Stop/撤权模型1/0/0，B01解除；新增 migration 20261009_0007、origin/event/receipt、HMAC receiver、历史 completion、私有 feed/read、ACL/deletion suppression 和 cron backfill；F05 精确隐私失败投影、私有策略剥离与标题 Thread 委托已验；F04 契约与回归通过，无破坏性改动；私有预算/Token/loop 注入拒绝与脱敏；执行预算、F01 Token 及 F02 loop 精确安全码；Plan 原生审批/ACL/幂等、Context v6执行链、公开agent_plan/fork/cron边界完成；Run Usage 可选 token_budget DTO、ACL/撤权真实链路通过；模型恢复、上下文、诊断、费率 Usage、Stop 接口均已实装；Workspace 五码精确投影与 DTO 校验完成；F10 Office MIME网关与六字段/撤权/审计、两图真实链路专项验收完成；未部署现役。 |
| platform-web | 2026-10-13 | 沙箱专项增加三模式/恢复 Playwright，真实模型/Office/后台/HTML/CSP/认证下载通过，相关51单测与静态检查通过，无产品代码改动。Token看板W01–W04全栈交付完成：双入口、4组指标卡、原生SVG图表、排行榜钻取、明细分页、无头RunUsage抽屉、顶栏切项目布局防抖与503容量保护友好适配；Playwright真实大模型E2E全绿；F07 自动对话标题全栈全链路闭环，双入口统一复用 useAutomaticThreadTitle；K09后台任务接受文案（accepted/unknown）/候选过滤/useChatSession Iron Gate真实interrupt异步保护与K10 Playwright真实大模型端到端自动化验收全部闭环（390/768/1440三视口留痕通过）；F01-F11与ABF01-ABF03已完成：能力/探针门禁、短任务恢复提示及真实local浏览器独立验收通过；F05 PII脱敏错误消费、输入草稿/附件保留、Playwright E2E自动化闭环完成；F04 大工具输出预算防爆加固：transcript 复合键防覆盖与 ToolMessage 优先、ToolResult 虚拟路径防跳转与多格式证据来源解析；F02 循环检测 ViewModel/状态机/RunDiagnostics 卡片与 Playwright 真实模型测试通过；F13 浏览器语音听写（F13-T01~T04）全链路交付；Agent Run completion 前端 P4.1-P4.3 全部交付闭环（Pinia 全局通知 Store 单例、RunNotificationCenter 顶栏与 ChatPage 双端常驻挂载、细粒度错误码白名单投影与离开跳转防护、useRunCompletion 历史 Run 终态诊断卡片）；F10 DOCX/PPTX 扩展名/空 MIME 校验、原字节认证下载拦截、Word/PPT 专属徽标、无预览仅下载、工作区415人性化提示、专用模板错误优先高亮与段落/幻灯片语义投影全实装；F01 Token 额度保护全栈落地；规划开关与审阅卡片闭环；Vitest/vue-tsc/ESLint/build 全绿。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-11 | 全场景本地原生PG/Redis优先及禁止滥用Docker硬约束实装；Worktree 开发/联调前必读 worktree-development 规范；统一登记隔离资源，共享依赖缓存但独立安装，默认本地账号 admin/admin123456、默认模型对齐 miaomiaoai deepseek-v4.1-flash、配置继承与首次只读基础数据初始化已验收。7个既有Worktree已同步31个本地栈工具/规范文件；未来新Worktree需从包含该基线的提交创建。Worktree依赖/真实Worker隔离、模型配置重加密、源历史与新审计区分及多会话发布协作经验已写入[ai-workflow](lessons/ai-workflow.md)；回调/迁移回退/Docker日志/执行目录经验已写入[runtime-service](lessons/runtime-service.md)。整单结束前须逐项核对未完成任务，未完成时只记Phase；恢复发布任务时核对正式产物归属与锁文件。 |

F07实施与验证入口以tasks.md/verification.md为准；正式post43和同名本地CAS候选来源/哈希不同，不能只凭版本名认定正式能力。
