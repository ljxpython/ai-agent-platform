# 项目当前状态 - AI 上下文

> **最后更新：** 2026-10-13（知识文档与图片平台接线全栈交付、前端F01–F06实装与自动化/人工验收done；Runtime 单节点远端沙箱与Token看板全栈闭环done；所属服务已停止）。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

**最后更新：** 2026-10-26

## 最近改动

2026-10-26 | **全域架构文档全景同步与技术资产演进工程**：系统性抹平 10 月份 52 项已交付成果与 `docs/architecture/` 之间的 8 大技术断层；升级宏观拓扑图与选型原则，扩充通信大动脉为 6 条干线（新增知识中台单向通道与双轨监控抓取通道）；全面重构可观测性文档（落实 W3C traceparent 与 Loki TSDB 毫秒日志穿透）；新增原生知识中台与单向免隧道自治架构规范；全面重写 DearFlow 记忆系统（异步解耦、双池 MMR 重排与软淘汰）；新增 Token 看板百万聚合读模型专篇与 186MB 轻量可观测、异步记忆 MMR、弹性 MCP 容错三大硬核 concepts 专篇；新增 4 篇端到端场景时序（Plan Mode、Trace-to-Logs 穿透、知识检索、模型容灾）；刷新全局 README 知识地图，自动化相对链接 100% 绿灯校验。
2026-10-23 | **工业级链路可视化升级与 Langfuse 多租户精准路由闭环**：彻底解决 Langfuse 404 跨租户路由报错，实现基于项目级精准搜索与 filter 参数的三级自适应 URL 构造器（全面支持 `VITE_LANGFUSE_PROJECT_ID` 等环境变量配置）；阻断平台代理查询 Loki 自身的自回声日志污染；重构工业级排障大屏（四联指标概览卡片、耗时瀑布流甘特条、毫秒级纯前端即时搜索与双视角 Tab 对比切换），适配平台标准深浅色主题；全量单测、TypeScript 0 错误、生产构建及 Playwright 自动化验证 100% 绿灯。
2026-10-22 | **分布式全链路追踪与日志关联可观测性工程全栈交付**：对标大厂分布式排障体验（字节诊断、阿里 ARMS），在 Platform API 与 Runtime Service 全面落实 W3C `traceparent`（`00-{trace_id}-{span_id}-01`）跨微服务协议透传与结构化日志 `service`、`trace_id`、`span_id` 打标；基于 Grafana Loki (TSDB) + Promtail 建立超轻量微服务日志中心；在生产主机 sshmy1 实装部署，Prometheus + Grafana + Loki + Promtail 四容器常驻总内存仅 **186.47 MiB**（CPU < 1%）；在前端实装可观测诊断中心与 Explore 联动，根据单一 `trace_id` 一键穿透展示跨服务毫秒级对齐日志流，并结合 Derived Fields 提供直达 Langfuse 链路树的高亮外链；全量测试与 TypeScript 检查 100% 绿灯。
2026-10-22 | **工业级可观测性与指标大盘全栈落地与前端方案 B 内嵌**：建立 Langfuse + Prometheus 双轨制架构；彻底重构 Platform API 内存锁计数器，引入标准 prometheus-client 并提供防内存泄漏的路径归一化；在 API (2142) 与 Runtime (8123) 暴露标准 /metrics 接口；生产主机 sshmy1 成功部署 Prometheus (19.59MB) 与 Grafana (50.5MB)，常驻内存总增量仅 70.09MB，双抓取 Targets 100% UP；实装前端方案 B 内嵌大盘（`ObservabilityDashboardPage.vue`，Kiosk 沉浸式无边框、深浅色主题双向联动、全屏与独立窗口跳转、系统探测快速直达），远端 Grafana 容器安全配置 `GF_SECURITY_ALLOW_EMBEDDING=true` 与免密只读已平滑热生效，前端全量 906 项单测及构建 100% 绿灯。

## 活跃项目

- [GitHub 调研工具与远程沙箱证据元组契约韧性治理](projects/20261026-github-tool-and-remote-evidence-resilience/README.md)：`done`；针对 GitHub 匿名调用 403 限流击穿引入 GITHUB_TOKEN 鉴权支持（借鉴 deer-flow），实测限流额度提升至 5000/hr；同时彻底修复 Remote Sandbox RPC 证据回传将元组退化为 List 导致 LangChain 强校验失败抛出 `runtime.execution_failed` 的致命缺陷。53 项单测全绿。
- [全域架构文档全景同步与技术资产演进工程](projects/20261025-architecture-docs-synchronization/README.md)：`done`；系统性抹平 10 月份 52 项已交付成果与 `docs/architecture/` 之间的 8 大技术断层，4 个 Phase 全部交付闭环并通过六维合规验证，0 坏链。
- [分布式全链路追踪与日志关联可观测性工程](projects/20261022-trace-to-logs-distributed-observability/README.md)：`done`；对标大厂分布式排障体验，基于 W3C traceparent 协议 + Grafana Loki/Promtail 超轻量日志中心（实测四容器常驻总内存仅 186.47MB），实现根据单一 trace_id 在一屏内同时展现微服务调用拓扑瀑布图与各服务毫秒级对齐的详细上下文日志，前端一键穿透与 Derived Fields 跳转全面实装，生产主机 sshmy1 验证通过。
- [工业级可观测性与指标大盘架构工程](projects/20261022-industrial-observability-architecture/README.md)：`done`；建立 Langfuse + Prometheus 双轨制工业级可观测体系，彻底淘汰内存锁计数器，向外暴露标准 `/metrics` 接口，生产主机 `sshmy1` 实装 Prometheus + Grafana 双容器（总内存常驻仅 70.09MB，双 Targets 100% UP），实装方案 B 前端无缝内嵌工业指标大盘（Kiosk 沉浸、深浅主题联动、全屏与全量 906 单测全绿）。
- [LightRAG MCP 知识库真实文档状态与图谱资产对齐](projects/20261021-lightrag-mcp-real-doc-status-alignment/README.md)：`done`；彻底消除假数据与跨租户内存串台，13 份多模态文档与真实状态完全透出，项目名称一一对齐，远端已部署，Playwright 真实模型测试通过。
- [LightRAG 工业级知识中台全量能力复刻与无缝集成](projects/20261019-full-lightrag-studio-integration/README.md)：`done`；彻底根治登录框弹窗，完整复刻 Graph Studio 2.0、Chat Studio 与 Knowledge Hub 三大工业级能力，测试与构建 100% 绿灯。
- [知识中台原生化重构 - 路线 C](projects/20261019-native-knowledge-studio/README.md)：`done`；彻底移除详情页冗余面板，废除 iframe 外挂，实装原生智能问答与 Canvas 力导向图谱工坊，测试与构建 100% 绿灯。
- [项目详情与知识中台交互收敛](projects/20261019-project-detail-knowledge-streamline/README.md)：`done`；项目详情页彻底纯净化，专注于基础信息与成员管理，测试构建全绿。
- [前端可观测性与端到端排障链路增强](projects/20261019-frontend-observability-and-diagnostic-tracing/README.md)：`done`；有界内存错误缓冲区 (Cap=10)、全局 ErrorBoundary 拒绝白屏、Axios/SSE 全链路 Request ID 对齐、DiagnosticDetailModal 就地排障模态窗、open-swe 风格 Actionable 建议字典与后端分类器、Langfuse 分布式链路追踪（Open Trace 直达外链）、轨迹错误节点兜底注入全栈落地并通过 Playwright 自动化 E2E 验收（4 张实景截图固化）。
- [Native Systemd 生产级架构加固与运维治理](projects/20261016-native-systemd-production-hardening/README.md)：`done`；非 root 专用受限账号 aiplatform 与内核级沙箱落地、Platform API 2 Worker 并发与 2G 内存熔断、Nginx 生产安全头与 600s 流式反代超时调优、PostgreSQL 每日凌晨自动 gzip 压缩轮转备份（留存 7 天）与 Journald 2G 封顶全部闭环并通过生产实测（HTTPS 证书依用户确认 deferred 暂缓）。
- [记忆系统架构升级 (Agent Memory System Upgrade)](projects/20261015-agent-memory-system-upgrade/README.md)：`done`；吸收 DeerFlow 记忆系统核心工程与算法优势，实现异步后台提取解耦（主请求耗时降至 < 5ms）、Prescreen 成本门禁、中文混合分词+IDF+双池 MMR 多样性检索、近重复合并与平滑淘汰；保留权威 PostgreSQL 存储、CAS 乐观锁与人工审核制；跨服务契约（Runtime stats 透传、API 校验、Web 健康进度条）全栈交付；Runtime 33 项单测、API 契约测试、Web 5 项单测及 vue-tsc 类型检查全部 100% 通过。
- [弹性 MCP 工具装配与运行时解耦保护](projects/20261015-resilient-mcp-loading/README.md)：`done`；对标 OpenSWE 生产级容错机制进行去业务化移植，实现 MCP 服务与工具的装配期故障隔离（10s 超时控制与全局异常捕获降级）与运行期优雅降级，彻底废除“缺工具即自杀”的反模式强校验；单测套件 170 项全绿；Playwright + Chromium 真实大模型端到端自动化验收 100% 绿灯，彻底消灭 `runtime.execution_failed`。
- [Docker 对话级沙箱生命周期管理与原生流式传输改造](projects/20261015-docker-sandbox-lifecycle-and-streaming/README.md)：`done`；纯 Docker 低开销对话沙箱架构落地；彻底拔除 Base64 JSON 传输大文件与全内存缓冲反模式；实装前端路径锁、下载Toast、Smart Zip智能归档（ZIP_STORED）与独立流式连接池；远端云主机 sshmy2 完成生产部署与验证；打包 9.4MB 大文件耗时从 21.5s 压降至 0.36s（下降 98.3%）；Playwright + Chromium 自动化端到端测试 100% 绿灯。
- [知识库免隧道自治与单向架构治理](projects/20261014-knowledge-zero-tunnel-auth/README.md)：`done`；彻底移除 SSH 反向隧道，实装本地自治自验；远端收敛为纯单向入站服务（仅需 22/8000 端口）；Playwright + Chromium 自动化端到端测试 100% 绿灯。
- [Agent 显式挂载多 MCP 与极简治理](projects/20261014-agent-explicit-mcp-mounting/README.md)：`done`；基于 LangChain 官方 `MultiServerMCPClient` 原生多 Server 纳管能力，贯彻 KISS 极简原则；实现 Agent 维度的显式按需挂载与多 Server 隔离，杜绝全量工具混调导致的大模型幻觉与 Token 浪费。全量单测 100% 通过。
- [知识库动态多项目绑定与免重启鉴权](projects/20261014-dynamic-knowledge-binding/README.md)：`in_progress`（Phase 1、Phase 2 及远端 Phase 3.1 实施验证完毕，本地全栈已就绪）；彻底淘汰静态 .env 手工配置与服务重启，建立基于 Platform-API 数据库持久化、Scoped HMAC/JWT 动态凭据签发、以及 RAG 远端知识库无状态即时验签与物理隔离的多租户免重启生产架构。待 Web 端开启新对话进行端到端体验验收。
- [知识文档/图片平台接线](projects/20261013-knowledge-documents-platform/README.md)：`done`（2026-10-13 用户验收通过）；T01–T08全部完成；前端F01–F06与无mock浏览器闭环、8步Playwright自动化测试全绿、MCP防死循环优化落地；所属服务已停止。
- [项目成员知识上传平台接线](projects/20261012-project-member-knowledge-upload/README.md)：`done`；由20261013专项统一验收；RAG真实联合链、审批/排队/去重/回退均通过。
- [项目知识检索 MCP 接入](projects/20261011-project-knowledge-mcp/README.md)：`done`；通用MCP与别名工具目录接入完成，多模态/文本库隔离。
- [Runtime 单节点远端 Docker 沙箱](projects/20261012-runtime-remote-docker-sandbox/README.md)：done（2026-10-13 用户本期验收）；T00–T15 本期收口，B01/B02 解除；正式整机重启/后续独立 Final、真实编辑和留存夹具/interrupt 排查 [deferred](projects/20261012-runtime-remote-docker-sandbox/follow-ups.md)。五服务已停。
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
|---|---|---|
| runtime-service | 2026-10-22 | W3C traceparent 协议中间件（解析与派生子 Span）与结构化日志 [service] [trace_id] [span_id] 打标闭环；微服务链路单测全绿；所属服务已停。 |
| platform-api | 2026-10-22 | W3C traceparent 标准头自动生成与下游传递、响应头回显；结构化日志过滤与追踪标签注入；单元测试全绿。 |
| platform-web | 2026-10-22 | 全链路可观测诊断中心（ObservabilityDashboardPage.vue）与错误模态框直达链路打通；支持输入 traceId 穿透查询微服务详细日志与 Explore 联动；单测全绿、TypeScript 0 错误。 |
| AI Harness（AGENTS.md + Skills） | 2026-10-13 | 知识授权回调纳入本环境生成，旧Worktree缺/空新增回调从本登记API派生，显式跨环境拒绝；全场景本地原生PG/Redis优先及禁止滥用Docker硬约束实装；Worktree 开发/联调前必读 worktree-development 规范；统一登记隔离资源，共享依赖缓存但独立安装，默认本地账号 admin/admin123456、默认模型对齐 miaomiaoai deepseek-v4.1-flash、配置继承与首次只读基础数据初始化已验收；知识MCP/独立Ollama新增登记/所属启停，4项自检及真实重启通过。7个既有Worktree已同步31个本地栈工具/规范文件；未来新Worktree需从包含该基线的提交创建。Worktree依赖/真实Worker隔离、模型配置重加密、源历史与新审计区分及多会话发布协作经验已写入[ai-workflow](lessons/ai-workflow.md)；回调/迁移回退/Docker日志/执行目录经验已写入[runtime-service](lessons/runtime-service.md)。整单结束前须逐项核对未完成任务，未完成时只记Phase；恢复发布任务时核对正式产物归属与锁文件。 |

F07实施与验证入口以tasks.md/verification.md为准；正式post43和同名本地CAS候选来源/哈希不同，不能只凭版本名认定正式能力。
