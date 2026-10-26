# 架构文档全景同步与技术资产演进工程 - 整体方案

## 背景
`docs/architecture/` 是平台在 2026 年 9 月末（v0.5.0 发布期）建立的顶层技术资产库，遵循极为严谨的 `METHODOLOGY.md` 六维工业级方法论。

然而，在 10 月 1 日至 10 月 23 日期间，平台在极高强度的工程迭代中落地了 **52 项核心生产能力与基础设施重构**（如分布式可观测性全链路日志穿透、LightRAG 原生知识中台与零隧道自治、DeerFlow 记忆系统异步解耦与 MMR 重排、弹性 MCP 装配防崩、Docker 远端沙箱与 Smart Zip 流式传输、Token 看板可重建读模型、Plan Mode 先规划后执行、前端 Clean Architecture 5层解耦等）。

目前，架构文档与主干代码之间已经出现了严重的**“技术断层（Documentation Drift）”**：
- 很多新模块在 `docs/architecture/` 中完全缺位（如知识中台、Token 读模型）；
- 部分已有文档的内容已严重滞后于最新代码（如可观测性仍停留在单体 Trace、记忆引擎仍停留在旧的同步阻塞阻塞架构）；
- 开发者与二次开发团队如果依据旧文档做决策，极易踩坑或产生误解。

因此，必须启动本次治理改动，全面对齐代码最新事实源，将新增的重大架构演进与深潜概念系统化补齐。

---

## 目标
1. **抹平 8 大核心架构断层**：对齐 10 月份全部 52 项已交付成果的架构事实。
2. **扩充架构全景与跨服务干线**：将“分布式全链路可观测性”与“知识中台零隧道自治”正式并入平台核心架构拓扑。
3. **补齐 4 大端到端高频新场景时序**：在 `06-scenarios/` 中沉淀 Plan Mode、Trace-to-Logs 穿透、知识检索与模型容灾降级时序。
4. **沉淀关键概念深潜专篇**：在 `concepts/` 中补充 MMR 多样性算法、PostgreSQL Advisory Lock 咨询锁并发对账、弹性 MCP 容错等生产级知识资产。
5. **保持 METHODOLOGY.md 规范一致性**：新旧文档 100% 具备源码坐标映射、真实 Schema、高保真伪代码与切斯特顿栅栏对比。

---

## 现状技术断层分析矩阵 (Delta Matrix)

| 序号 | 领域 / 模块 | 当前 `docs/architecture/` 现状 | 主干代码真实运行现状 (事实源) | 演进要求与动作 |
|---|---|---|---|---|
| **1** | **全链路可观测性** | `02-cross-cutting/04` 仅包含基础 Trace ID 传递与单体 Langfuse 概要 | W3C `traceparent` 标准透传、Prometheus + Grafana + Loki + Promtail 超轻量中心（<190MB）、三级自适应 Langfuse URL 路由、前端毫秒级日志穿透瀑布流、有界内存错误环形缓冲区 (Cap=10) | **全面重构** `02-04-trace-and-observability.md`，并在 Runtime/API concepts 补充实战透析 |
| **2** | **知识中台与自治** | 架构目录中几乎**完全空白**，未纳入核心拓扑 | 原生知识中台（Canvas 力导向图谱工坊 2.0、Chat Studio、Knowledge Hub）；免隧道单向自治架构（Scoped HMAC/JWT 动态凭据，废除 SSH 反代）；多模态文档/图片异步入库与段落/页码精确引用 | **宏观拓扑升级**，在 `02-cross-cutting/` **新增** `06-knowledge-studio-and-zero-tunnel.md` |
| **3** | **记忆系统 (Memory)** | `07-01-02-memory-engine.md` 描述旧版同步阻塞抽取（主请求延迟 2~5s，100条死板 409 拒服） | 吸收 DeerFlow 优势：异步后台非阻塞提取（主延迟 < 5ms）、Prescreen 成本门禁、中文分词+IDF、双池 MMR 多样性重排、置信度+新鲜度平滑淘汰、PostgreSQL 咨询锁 CAS 乐观并发 | **全面重构** `07-agents/01-dearflow-agent/02-memory-engine.md`，新增 MMR 算法 concepts |
| **4** | **工具与 MCP 装配** | `05-04-tools-and-skills.md` 假定工具装配强校验，缺失工具即阻断 | 对标 OpenSWE 生产级容错：装配期 10s 超时与全局异常隔离、运行期优雅降级（废除缺工具即自杀）、Agent 显式挂载多 MCP Server（`MultiServerMCPClient`） | **升级** `05-runtime-service/04-tools-and-skills.md`，增加装配期故障隔离与切斯特顿栅栏对比 |
| **5** | **沙箱与资产管线** | `05-runtime-service/concepts/09` 假定 Base64 JSON 传输与单机本地沙箱 | 单节点远端 Docker 沙箱支持、彻底拔除 Base64 采用 Smart Zip（ZIP_STORED）流式直出（打包耗时降低 98.3%）、前端路径锁与 CSP 防护 | **更新** `05-runtime-service/concepts/09-workspace-sandbox-pty-and-asset-pipeline.md` |
| **6** | **用量与 Token 看板** | 架构文档无独立用量计量与读模型体系 | 平台与项目两级看板、百万级可重建聚合投影读模型（解除 B01 瓶颈）、12位原文字符串高精度金额、open-swe 运行水位仪表（Usage Meter） | **在 `04-platform-api/` 新增** `05-token-usage-and-read-models.md` |
| **7** | **运行控制与稳定性** | 仅有通用 Agent 流程描述，缺少高级调度治理 | Plan Mode 先规划后执行（原生审批中断）、执行预算与步骤硬限软收尾、只读工具重复调用死循环熔断、模型容灾降级（Model Fallback）、通用长任务/Webhook（post44）、通用文档读取（DOCX/PPTX）、PII 脱敏 | **在 `05-runtime-service/` 更新** 核心图执行，并在 `06-scenarios/` 新增 4 个时序文档 |
| **8** | **前端 Clean 架构** | 前端文档偏向早期组件排布 | 5 层 Clean Architecture 解耦、useSessionInterrupts 审批自愈、全局 ErrorBoundary、LangGraph v3 默认流与 `service.state` 毫秒级断流自愈 | **更新** `03-platform-web/01-architecture.md` 与 `02-chat-session-engine.md` |

---

## 方案设计：架构文档目录演进全景

保持现有优雅的层级结构不变，精准注入新资产：

```text
docs/architecture/
├── README.md                                # [同步更新] 刷新全景大地图、知识地图索引与进度看板
├── METHODOLOGY.md                           # [保留] 六维编写规范基石
│
├── 01-overview/                             # 【第一层：宏观拓扑】
│   ├── 01-system-topology.md                # [更新] 拓扑大图补充可观测体系(Prometheus/Loki)、远端沙箱与知识中台子系统
│   ├── 02-tech-stack.md                     # [更新] 补充 Loki、Promtail、Prometheus-client、LightRAG 等新选型
│   └── 03-design-principles.md              # [更新] 补充弹性装配降级原则与只读防自杀原则
│
├── 02-cross-cutting/                        # 【第二层：跨服务通信大动脉】
│   ├── 01-communication-matrix.md           # [更新] 补充知识库免隧道协议与可观测性抓取干线
│   ├── 02-delegation-auth.md                # [更新] 补充 Scoped HMAC/JWT 动态凭据与知识库验签
│   ├── 03-sse-streaming-pipeline.md         # [更新] 补充 LangGraph v3 帧协议与 410 毫秒级极速自愈
│   ├── 04-trace-and-observability.md        # [全面重构] W3C traceparent 跨服务透传、Loki 毫秒日志中心、Langfuse 路由
│   ├── 05-data-isolation.md                 # [更新] 补充知识库物理隔离与多租户三元组约束
│   └── 06-knowledge-studio-and-zero-tunnel.md # [新增] 原生知识中台架构与单向免隧道自治机制
│
├── 03-platform-web/                         # 【第三层：前端架构】
│   ├── 01-architecture.md                   # [更新] 5层 Clean Architecture 架构与全局 ErrorBoundary
│   ├── 02-chat-session-engine.md            # [更新] 审批自愈状态机、v3 帧防洪与断流自愈
│   └── 03-component-design.md               # [更新] 补充 ObservabilityDashboard、Token看板、PlanReview 组件标准
│
├── 04-platform-api/                         # 【第四层：控制面与网关】
│   ├── 01-architecture.md                   # [更新] 领域模型更新
│   ├── 02-runtime-gateway.md                # [更新] 补充 W3C Header 注入、Loki 自回声阻断
│   ├── 03-iam-and-governance.md             # [更新] 补充 PII 脱敏网关与模型恢复策略治理
│   ├── 04-catalog-management.md             # [更新] 模型 6 项费率配置与上下文容量配置
│   ├── 05-token-usage-and-read-models.md    # [新增] 百万级 Token 可重建聚合投影读模型架构
│   └── concepts/
│       └── 08-lightweight-observability-philosophy.md # [新增] 186MB 超轻量可观测体系设计哲学
│
├── 05-runtime-service/                      # 【第五层：Agent 执行引擎】
│   ├── 01-architecture.md                   # [更新] 双进程与远端 Docker 沙箱通信
│   ├── 02-langgraph-execution.md            # [更新] v3 事件流、预算软收尾、只读工具防死循环熔断
│   ├── 03-hitl-and-interrupts.md            # [更新] Plan Mode 规划中断与原生审批流恢复
│   ├── 04-tools-and-skills.md               # [更新] 弹性 MCP 装配隔离、MultiServerMCPClient、Smart Zip 流式直出
│   └── concepts/
│       ├── 13-asynchronous-memory-and-mmr-algorithm.md # [新增] 异步记忆提取与双池 MMR 重排算法透析
│       └── 14-resilient-mcp-fault-isolation.md       # [新增] 弹性 MCP 容错与装配期短路保护机制
│
├── 06-scenarios/                            # 【第六层：端到端场景时序】
│   ├── 01-agent-chat-flow.md                # [更新] 补充 v3 协议与 PII 脱敏阶段
│   ├── 02-hitl-approval-flow.md             # [更新] 审批自愈与 Iron Gate 避让
│   ├── 03-subagent-dispatch.md              # [保留]
│   ├── 04-plan-mode-flow.md                 # [新增] 先规划后执行（Plan Mode）端到端全链路时序
│   ├── 05-trace-to-logs-flow.md             # [新增] Trace-to-Logs 分布式排障日志穿透时序
│   ├── 06-knowledge-studio-flow.md          # [新增] 知识上传、异步入库与只读检索时序
│   └── 07-model-resilience-fallback-flow.md # [新增] 模型瞬态故障毫秒级主备降级时序
│
└── 07-agents/                               # 【第七层：具体智能体深潜】
    └── 01-dearflow-agent/
        ├── 02-memory-engine.md              # [全面重构] 异步解耦、Prescreen 门禁、MMR 算法与软淘汰
        └── 04-workspace-sandbox.md          # [更新] 远端 Docker 沙箱、Smart Zip 流式传输、PTY 终端
```

---

## 实施计划

- **Phase 1: 顶层宏观拓扑与跨服务通信大动脉同步**
  - 更新 `01-overview/` 3 篇文档，引入可观测性、知识中台与远端沙箱。
  - 重构 `02-cross-cutting/04-trace-and-observability.md`。
  - 新增 `02-cross-cutting/06-knowledge-studio-and-zero-tunnel.md`。
  - 更新数据隔离与 SSE 流式管道文档。

- **Phase 2: 执行面 Runtime 与核心智能体沉淀**
  - 重构 `07-agents/01-dearflow-agent/02-memory-engine.md`。
  - 更新 `05-runtime-service/04-tools-and-skills.md`（弹性 MCP 与 Smart Zip）。
  - 新增概念专篇：异步记忆与 MMR 算法、弹性 MCP 容错短路。
  - 更新沙箱与 PTY 终端文档。

- **Phase 3: 控制面 Platform-API 与前端 Clean 架构同步**
  - 新增 `04-platform-api/05-token-usage-and-read-models.md`。
  - 更新 `04-platform-api/` 网关、IAM/PII 与模型目录。
  - 更新 `03-platform-web/` Clean Architecture、审批自愈状态机与可观测大盘组件。
  - 新增概念专篇：186MB 超轻量可观测体系设计哲学。

- **Phase 4: 全新端到端场景时序闭环与总览看板刷新**
  - 新增 4 大时序专篇：Plan Mode、Trace-to-Logs 穿透、知识中台检索、模型主备降级。
  - 刷新 `docs/architecture/README.md` 全景地图与状态看板。
  - 执行六维标准合规性核查。
