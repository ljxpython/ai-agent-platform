# 架构文档全景同步与技术资产演进工程 - 任务拆分

## Phase 1: 顶层宏观拓扑与跨服务通信大动脉同步

### Task 1.1: 宏观拓扑、技术栈与设计原则升级
- **改动内容：** 更新 01 目录，将 Prometheus/Loki/Promtail、远端 Docker 沙箱与 LightRAG 知识中台纳入系统全景与选型清单；补充弹性装配降级原则与只读防自杀原则。
- **文档位置：** `docs/architecture/01-overview/01-system-topology.md`, `02-tech-stack.md`, `03-design-principles.md`
- **预期结果：** 系统全景图与服务职责清晰涵盖最新落地基础设施。
- **验证项：** 检查 Mermaid 拓扑语法有效性，技术栈版本与 `apps/` 真实依赖一致。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 1.2: 全链路可观测性大动脉全面重构
- **改动内容：** 彻底重构追踪文档，全面写入 W3C `traceparent` 协议规范、Prometheus+Grafana+Loki+Promtail 双轨制架构、自适应 Langfuse URL 路由机制及前端毫秒日志穿透方案。
- **文档位置：** `docs/architecture/02-cross-cutting/04-trace-and-observability.md`
- **预期结果：** 具备高保真 HTTP Headers、Loki TSDB 架构及前端穿透伪代码。
- **验证项：** 对照 `projects/20261022-trace-to-logs-distributed-observability/` 验证真实性。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 1.3: 新增知识中台与单向免隧道自治架构文档
- **改动内容：** 建立知识中台跨服务规范，详细阐述 Canvas 力导向图谱工坊、Scoped HMAC/JWT 动态凭据签发与无隧道单向入站自治设计。
- **文档位置：** `docs/architecture/02-cross-cutting/06-knowledge-studio-and-zero-tunnel.md`
- **预期结果：** 补齐平台知识库从上传、异步入库、自治验签到 MCP 检索的跨服务规范。
- **验证项：** 对照 `projects/20261014-knowledge-zero-tunnel-auth/` 校验契约。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 1.4: 跨服务通信矩阵、委托鉴权与 SSE 管道同步
- **改动内容：** 更新通信矩阵（新增知识中台与指标抓取干线）、委托鉴权（新增知识 Scoped HMAC/JWT 凭据）与 SSE 管道（LangGraph v3 帧防洪与 410 断流自愈）。
- **文档位置：** `docs/architecture/02-cross-cutting/01-communication-matrix.md`, `02-delegation-auth.md`, `03-sse-streaming-pipeline.md`, `05-data-isolation.md`
- **预期结果：** 跨服务通信大动脉文档与当前运行代码无缝对齐。
- **验证项：** 检查 4 条干线与最新路由代码一致。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

---

## Phase 2: 执行面 Runtime 与核心智能体沉淀

### Task 2.1: DeerFlow 记忆系统全面重构与 MMR 算法透析
- **改动内容：** 彻底重写记忆引擎文档，替换旧的同步阻塞架构，详细阐述异步后台非阻塞提取（<5ms）、Prescreen 成本门禁、中文分词+IDF、双池 MMR 多样性重排与平滑淘汰；新增概念专篇深入剖析 MMR 算法数学模型。
- **文档位置：**
  - `docs/architecture/07-agents/01-dearflow-agent/02-memory-engine.md`
  - `docs/architecture/05-runtime-service/concepts/13-asynchronous-memory-and-mmr-algorithm.md`
- **预期结果：** 包含真实 SQL Advisory Lock 伪代码、双池 MMR 贪分配公式与真实时延测试数据。
- **验证项：** 算法公式渲染无误，代码映射到 `memory/` 真实模块。
- **预计：** 1.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 2.2: 弹性 MCP 装配与防装配自杀容错沉淀
- **改动内容：** 更新工具装配文档，详细记录装配期 10s 超时隔离、全局捕获降级、运行期优雅降级机制与 `MultiServerMCPClient` 多 Server 隔离；新增概念专篇进行切斯特顿栅栏深度审视。
- **文档位置：**
  - `docs/architecture/05-runtime-service/04-tools-and-skills.md`
  - `docs/architecture/05-runtime-service/concepts/14-resilient-mcp-fault-isolation.md`
- **预期结果：** 详述“缺工具即自杀”反模式的治理推演与生产级容错设计。
- **验证项：** 对照 `apps/runtime-service/src/runtime_service/services/mcp/` 源码映射。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 2.3: 远端 Docker 沙箱与 Smart Zip 流式资产管线更新
- **改动内容：** 更新沙箱与资产管线，记录单节点远端 Docker 沙箱支持、拔除 Base64 采用 Smart Zip（ZIP_STORED）流式直出（打包耗时降低 98.3%）、前端路径锁与 CSP 防护。
- **文档位置：**
  - `docs/architecture/05-runtime-service/concepts/09-workspace-sandbox-pty-and-asset-pipeline.md`
  - `docs/architecture/07-agents/01-dearflow-agent/04-workspace-sandbox.md`
- **预期结果：** 明确本地开发、本地 Docker 与远端 Docker 三种模式的切换与流式传输时序。
- **验证项：** 检查流式连接池与路径锁源码坐标。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 2.4: Runtime 核心调度与稳定性全矩阵同步
- **改动内容：** 更新图执行与审批文档，记录 LangGraph v3 默认事件流、执行预算软收尾、只读工具防死循环熔断、模型 Fallback 容灾策略以及 Plan Mode 规划中断恢复。
- **文档位置：**
  - `docs/architecture/05-runtime-service/02-langgraph-execution.md`
  - `docs/architecture/05-runtime-service/03-hitl-and-interrupts.md`
- **预期结果：** 详述运行时防死循环、容灾降级与规划审批的状态机流转。
- **验证项：** 状态机迁移图与 `graphs/` 源码逻辑一致。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

---

## Phase 3: 控制面 Platform-API 与前端 Clean 架构同步

### Task 3.1: 新增 Token 看板可重建聚合读模型架构文档
- **改动内容：** 新增用量与 Token 看板架构专篇，详细解析平台/项目两级汇总、百万级调用下可重建聚合投影读模型、12 位原文字符串金额计算与 open-swe 运行水位进度条。
- **文档位置：** `docs/architecture/04-platform-api/05-token-usage-and-read-models.md`
- **预期结果：** 呈现读写分离、聚合投影表结构与高并发防抖时序。
- **验证项：** 表结构与 Alembic 迁移脚本核对无误。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 3.2: Platform-API 控制面与网关安全治理同步
- **改动内容：** 更新 API 控制面文档，补齐 PII 脱敏算法网关、模型多 Provider 费率与容量配置、Webhook post44 终态通知持久化与定时任务调度。新增 186MB 超轻量可观测体系哲学专篇。
- **文档位置：**
  - `docs/architecture/04-platform-api/01-architecture.md`, `02-runtime-gateway.md`, `03-iam-and-governance.md`, `04-catalog-management.md`
  - `docs/architecture/04-platform-api/concepts/08-lightweight-observability-philosophy.md`
- **预期结果：** 控制面架构全面覆盖 10 月份新增的治理能力。
- **验证项：** 接口契约与 FastAPI 路由声明对齐。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 3.3: Platform-Web Clean Architecture 5层解耦与状态机加固
- **改动内容：** 更新前端架构与会话引擎文档，深入剖析 5 层解耦、全局 ErrorBoundary、useSessionInterrupts 审批自愈状态机、切屏假死根治与 ObservabilityDashboardPage 组件设计。
- **文档位置：** `docs/architecture/03-platform-web/01-architecture.md`, `02-chat-session-engine.md`, `03-component-design.md`
- **预期结果：** 前端状态机模型、Composable 职责与防御体系完全对齐最新代码。
- **验证项：** 检查 Vue 组件路径与 Pinia Store 引用。
- **预计：** 1 天
- **状态：** `[x]` 已完成 (2026-10-26)

---

## Phase 4: 全新端到端场景时序闭环与总览看板刷新

### Task 4.1: 新增 4 大端到端高频新场景时序
- **改动内容：** 在 06 目录新增 4 篇工业级时序文档：
  1. `04-plan-mode-flow.md`（Plan Mode 先规划后执行时序）
  2. `05-trace-to-logs-flow.md`（Trace-to-Logs 毫秒级日志穿透排障时序）
  3. `06-knowledge-studio-flow.md`（知识上传、异步入库与零隧道检索时序）
  4. `07-model-resilience-fallback-flow.md`（模型瞬态故障主备降级时序）
- **文档位置：** `docs/architecture/06-scenarios/04~07.md`
- **预期结果：** 每篇包含高清 Mermaid 时序图、真实 HTTP/SSE 报文与前后端函数级断点链路。
- **验证项：** Mermaid 语法校验通过，各阶段函数名与代码完全吻合。
- **预计：** 1.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 4.2: 架构目录 README.md 全景地图与总看板刷新
- **改动内容：** 刷新 `docs/architecture/README.md`，更新系统知识全景索引树、概念透析总字典直达表，并更新分批推进进度看板。
- **文档位置：** `docs/architecture/README.md`
- **预期结果：** 索引树 100% 覆盖全部新增与更新文档，无死链、坏链。
- **验证项：** 运行坏链自检，确保所有相对路径准确无误。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

### Task 4.3: Final 全量六维标准合规核查
- **改动内容：** 按照 `METHODOLOGY.md` 六维标准，对本次更新和新增的全部文档进行逐项合规审查。
- **验证项：** 源码坐标映射率 100%、Schema 真实性 100%、伪代码可读性与防守案例闭环。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 (2026-10-26)

## 进度追踪
- [x] Phase 1 顶层宏观拓扑与跨服务大动脉完成 (2026-10-26)
- [x] Phase 2 执行面 Runtime 与核心智能体完成 (2026-10-26)
- [x] Phase 3 控制面 Platform-API 与前端 Clean 架构完成 (2026-10-26)
- [x] Phase 4 端到端新场景时序与总览看板刷新完成 (2026-10-26)
- [x] Final 全量六维标准合规核查通过 (2026-10-26)
