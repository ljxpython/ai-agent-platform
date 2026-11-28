# 独立评测中台迁移与平台原生化改造方案

> 启动日期：2026-11-28｜当前状态：**部分完成（partial：一阶段控制面、LightRAG 工坊、TTFT/Token 透传与 PK 已交付；二阶段 `Task 6.1–6.4` 白盒取证、L1/L2 全算子、DeepEval 独立运行器与中文动态多轮仿真已完成编码并真实跑通 3 题代表集；`Task 6.5` 10 题 `v3-golden` 已入库但剩余 7 题含 RAG/PlanReview、远端沙箱与定时巡检 Cron 待续，详见专题 06）**
> 文档模式：多专题方案（按业务架构、代码迁移、并发引擎、指标体系、前端与验证、以及二阶段审计拆分为 6 篇专题，不另建全局 `plan.md` / `tasks.md` / `verification.md`）。

## 1. 业务背景与要解决的问题

当前评测工作台寄生在关联仓库 `../mlflow-eval-platform` 中，业务人员与研发团队在日常出题、运行评测和排查问题时持续遇到两类工程摩擦：

1. **界面与数据模型强绑定 MLflow Experiment 壳层**：出题工坊寄生在 MLflow 原生实验与运行视图中，前端单文件膨胀至四千余行且与原生追踪表格 hooks 耦合，导致加载死锁、滚动死锁以及概念切换负担。同时，`Connection` 抽象将“资料来源、题库存储、执行靶场、追踪实验”强绑在一起，切换环境就会找不到题库。
2. **近期故障与中断频发，大量精力消耗在补丁兼容**：近期的大量改动集中在修复身份 Cookie 滑动续期、跨机工作项列表递归读盘卡顿、跨服务鉴权阻塞、单并发串行跑近 50 分钟、裁判预算连坐中断、单题超时写死等问题。这些内耗源于“在 MLflow 外挂壳子里做完整评测应用”，而非评测算法本身不可行。

**本次改造的核心目标（已确认架构模式）：**
把核心评测能力从 `../mlflow-eval-platform` 迁移并重构进 `ai-agent-platform` 生态中，**充分复用现有 `platform-api + PostgreSQL + Redis` 底座**降低重复基建开发量，同时严守职责边界：
- **`platform-api`**：承担评测资产 CRUD、版本冻结、权限与会话脱敏交付、Readiness 预检、运行与对比统计（**控制面不运行 LangGraph 图，也不在 HTTP 线程内跑长阻塞评测**）；
- **`runtime-service`**：承载所有 LangGraph 执行，包含放开白名单后的多被测 Agent（支持能力分级）以及新迁入的**出题专家 (`eval_copilot`)** 与 **诊断专家 (`eval_diagnosis`)** 两个 Graph；
- **`apps/eval-runner`**：共享同一套 PG + Redis 底座的轻量独立 Worker 进程与 CLI，承担并发 Case 调度池、多轮仿真、流式 SSE 测 TTFT、MLflow Trace 取证、L1 物理规则与 DeepEval 打分（**直连平台网关已配置模型**，废除私有 `.env`）；
- **`platform-web`**：以原生 Vue 3 + ECharts 6 重构工作台，功能对齐 `../LightRAG` 并融合 Agent 多轮/白盒特性，UI 严格遵循 `platform-web` 既有设计规范；
- **MLflow**：彻底退回并专注于 `TRACING_PROVIDER=mlflow` 下的纯链路追踪查看。

### 期望的端到端业务流程

1. **多源沉淀题目**：研发或业务负责人可以从线上任意项目的历史/当前会话一键脱敏转入评测集，也可以上传/导入标准考卷，或借助 AI 出题助手生成与修订多轮用例，形成独立、可版本化冻结的评测集资产。
2. **指定隔离项目开考**：发起评测时，显式指定一个**目标隔离项目**（如专门的评测靶场项目）和待测 Agent/模型配置；先执行开考前就绪度检查（Readiness Guard），再发起受控并发评测（支持暂停、断点续跑、仅重跑失败用例），不污染线上业务项目的数据、记忆与预算。
3. **白盒取证与分级裁决**：评测引擎通过平台公开接口驱动被测 Agent，利用 MLflow 链路追踪按项目实验（`project-{project_id}`）回收 Span 轨迹与文件工件，按“L1 物理与规则硬断言 -> L2 语义与大模型裁判 -> L3 人工抽检标定”输出 3 大形态 × 7 大核心维度的清晰指标。
4. **对比 PK、归因与追溯**：在平台页面查看全量用例得分、对比不同版本/参数矩阵的涨跌与退化红灯、呼出诊断专家做三层缺口归因（Data / Retrieval / Reasoning Gap），点击单题 `Trace` 链接直接穿透至 MLflow 查看底层调用链。

---

## 2. 可行性结论与核心判断

| 评估问题 | 结论 | 事实依据 |
|---|---|---|
| **1. 从 MLflow 迁出并独立运行是否可行？** | **完全可行，且收益极高** | `eval_platform` 约 1.26 万行核心代码里，契约、仿真、工具白盒解析、规则/语义打分、门禁、出题图与诊断图几乎不依赖 MLflow 服务端逻辑；`scorers/agent_platform.py` 仅通过一层 `get_scorer` 包装调 DeepEval，可直接替换为原生 `deepeval.metrics`。 |
| **2. `runtime-service` 是否需要改动？** | **已拍板受控扩展** | 放开多 Graph 评测白名单（`dearflow_agent`、`showcase_demo`、`reference_agent`、`workflow_demo`），在缺口图补齐 `assert_target` / `record_execution` 并实施能力分级；同时将 **出题专家 (`eval_copilot`)** 与 **诊断专家 (`eval_diagnosis`)** 作为新 Graph 迁入 `runtime-service/services/`，清理空残余 `services/evaluation_assistant/`；TTFT 由评测端 SSE 探针测量，不入侵运行时业务节点。 |
| **3. 能否复用底座并保持清晰解耦与单机承载力？** | **完全可行（实测可控）** | 实测 `deepeval` 导入仅增 ~79 MiB RSS；此前主机内存压力主要源于冗余 MLflow 应用及 Redis Run 事件流缓存曾膨胀至 1.4~1.9 GB。复用现有 PG + Redis 底座并把并发与 DeepEval 拆入轻量 `eval-runner` Worker 进程、同时给 Redis 事件流设置严格 TTL/体积上限，全栈可稳妥同机部署于 `sshmy1` 并支持 CLI 独立运行。 |
| **4. 能否落地白皮书的 7 维指标体系？** | **可务实落地主体，不做过度设计** | 维度 1~4 与维度 6 已在 `eval_platform` 重度实现；维度 5 的死循环率聚合与 RAG 召回指标、维度 7 的 SSE TTFT/P99/精确成本/异常细分/轻量 Pass^k 可直接补齐；DeepEval 裁判直接选用平台模型管理里的授权模型；分布式真机集群与影子流量网关一期不做。 |

---

## 3. 专题导航与总体状态

| 专题编号 | 专题文档 | 覆盖内容 | 当前状态 | 关联影响域 |
|---|---|---|---|---|
| **01** | [总体架构、环境隔离与 Runtime 边界](01-architecture-and-isolation.md) | **方案 X** 三端职责划分、`sshmy1` 资源评估、专家入驻 `runtime-service` 回调桥、多 Graph 白名单与隔离靶场 | **已完成编码与单测（done）** | `platform-api`、`runtime-service`、`apps/eval-runner` |
| **02** | [MLflow 既有代码迁移清单与清理边界](02-mlflow-code-migration.md) | `eval_platform` 全部模块按目标服务拆解迁移与淘汰清单（含一期与二期续迁清单） | **部分完成（partial：核心引擎、`simulation`、`tool_evidence`、`runtime_signals`、全量 L1/L2 与 10 题库导入已迁移并实测 3 题；直连 MLflow Protobuf 读取 Bridge 改为走网关状态/工作区采集）** | `../mlflow-eval-platform/eval_platform` → 本仓三端 |
| **03** | [评测引擎、并发调度与断点续跑机制](03-eval-service-concurrency-and-engine.md) | 复用 PG/Redis 的表结构、`eval-runner` 并发池（默认 3、范围 1~5）、JSON-RPC SSE TTFT 分段探针、Token/费用透传与门禁（巡检 Cron 后置） | **已完成（done：基础运行器、独立 `eval-runner/.venv` DeepEval、中断续跑与耗时/费用透传已真跑；注 `仅重跑失败题` 汇总偏差与 Cron 后置见 06）** | `platform-api`、`apps/eval-runner`、`scripts/local-stack.sh` |
| **04** | [评测指标体系建设与白皮书对齐方案](04-metrics-and-whitepaper-alignment.md) | 3 大形态 × 7 大维度、SSE TTFT 探针、平台模型裁判、L1/L2/L3 裁决、三层归因、克制边界 | **已完成设计并实装（partial 实证：L1 安全/工件规则、动态仿真与 DeepEval 裁判已在 3 题真跑；RAG 类 7 题尚待补测）** | `apps/eval-runner`、`runtime-service`、`platform-web` |
| **05** | [前端工作台设计（借鉴 LightRAG）与全链路浏览器验收](05-frontend-eval-studio-and-e2e.md) | 原生 Vue 工作台（3 项精简评测专栏、PK 收口进打擂大厅、LightRAG 级 Side-by-Side 与性能剖析、雷达图修复、动态交互轴、`/browser` 截图） | **已完成（done：含二阶段动态澄清轮次/审批次数/事实披露事件轴与 PK 实测截图）** | `apps/platform-web`、`platform-api`、`eval-runner` |
| **06** | [7 维指标判定依据审计、老仓迁移落差与二阶段攻坚计划](06-metric-reliability-and-migration-gap-audit.md) | 逐维实盘核查判定依据可信度、控制面取证/续跑、L1/L2 算子、动态多轮仿真、真实缺陷修复与 `v3-golden` 真跑验证（Task 6.1–6.5） | **部分完成（partial：`Task 6.1–6.4 done`；`Task 6.5` 已导入 10 题并在 local 栈真跑 3 题与 PK，剩余 7 题与远端沙箱待补）** | `platform-api`、`apps/eval-runner`、`runtime-service`、`platform-web` |

---

## 4. 已拍板确认的核心决策清单

以下关键架构与产品决策已全部确认锁定，作为后续实施与验收的唯一基线：

1. **总体架构模式（方案 X）**：复用 `platform-api + PostgreSQL + Redis` 底座，全栈部署于 `sshmy1`。`platform-api` 负责同步控制面资产 CRUD 与权限（修订 [architecture.md](../../../apps/platform-api/docs/handbook/architecture.md) 明确允许评测资产/结果表归口控制面）；`runtime-service` 负责所有 Graph；独立轻量 Worker 进程 **`apps/eval-runner`** 负责并发评测调度、仿真、SSE TTFT 采样、Trace 取证与 DeepEval 打分。
2. **专家智能体归属**：出题专家（`eval_copilot`）与诊断专家（`eval_diagnosis`）作为独立 LangGraph 放入 `apps/runtime-service/src/runtime_service/services/`，通过 HMAC 内部回调 `platform-api` 获取草稿与分片证据，复用统一模型网关、容灾、预算与 MLflow Tracing。
3. **DeepEval 模型网关**：废弃原私有 `~/.my_best/.env`（`XIAOK_PROXY_URL` / `BAILIAN_URL`）配置；DeepEval 推理模型与 Embedding 模型**直接从平台网关模型目录（`runtime_catalog_models`）按授权选择并解析调用**，计入平台预算治理。
4. **多 Agent 评测与能力分级**：去掉 `dearflow_agent` 唯一限制，首批放开 `dearflow_agent`、`showcase_demo`、`reference_agent`、`workflow_demo`（排除 `platform_assistant`），按各图实际能力实施分级匹配，并在开考前 **Readiness 守卫** 中拦截不兼容断言。
5. **指标体系与 TTFT**：对齐白皮书 3 大形态 × 7 维度 + L1/L2/L3 + 三层 Gap 归因；在 `eval-runner` 通过流式 SSE 接口直接测量每题真实 **TTFT 首字延迟**与 P50/P95/P99 分位数。
6. **并发上限与隔离靶场防误触**：
   - 并发度默认 `concurrency = 3`，前端可调范围 **`1 ~ 5`**；同时限制 Redis 事件流大小与 TTL，避免内存膨胀；
   - 允许用户选用任意具备运行权限的项目作为目标隔离靶场，但对**非专用测试靶场项目在开考弹窗给出明显黄/红风险警告**，确认后放行。
7. **前端工程载体与规范**：直接在 `apps/platform-web` 以 Vue 3 + ECharts 6 原生重构（放弃 iframe 与旧 MLflow 壳层），功能交互对齐 LightRAG 并融合 Agent 特性，视觉组件严格遵循 `platform-web` 控制面与视觉基线规范。

> **当前阶段事实说明**：一阶段与二阶段 `Task 6.1–6.4` 代码均已在本仓落地并经本地端到端实测验证；未做未经授权的二阶段 Git 提交/推送与生产部署，剩余 `v3-golden` 7 题（RAG/PlanReview）与定时巡检 Cron 待后续窗口补完。
