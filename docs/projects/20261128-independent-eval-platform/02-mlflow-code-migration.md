# 专题 02：MLflow 既有代码迁移清单与清理边界

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**方案已对齐（按方案 X 分流至 `platform-api` / `eval-runner` / `runtime-service`，待开始编码）**

## 1. 盘点原则与目标落点

对 `../mlflow-eval-platform/eval_platform/`（约 1.26 万行 Python 代码）与 `../mlflow-eval-platform/web/src/evaluation-tasks/` 进行逐模块源码级审计后，按方案 X 精准分流到本仓三个端：

1. **直接复用迁移至 `apps/eval-runner/`**：仿真博弈、物理/Trace 取证、DeepEval/规则评分、门禁、运行质量与人工一致性计算；同步把 `judge.py` 的私有 `.env` 配置改为通过 `platform-api` 解析平台网关模型。
2. **去壳重构迁移至 `apps/platform-api/src/platform_api/modules/evaluation/`**：业务资产（题库、用例、冻结版本、Run/检查点、审核队列、巡检配置），彻底淘汰文件锁与 JSON 递归扫描，改为 `platform_api` PostgreSQL + Alembic 表与同步 CRUD。
3. **Graph 迁入 `apps/runtime-service/src/runtime_service/services/`**：出题 Copilot 与诊断专家 LangGraph 状态机（对接平台模型路由与内部回调桥）。
4. **坚决淘汰舍弃**：仅用于绕过 MLflow Auth、React 壳层、私有 `~/.my_best/.env` 网关或文件队列锁的补丁代码，彻底剥离。

---

## 2. 后端模块逐项迁移矩阵（`../mlflow-eval-platform/eval_platform/`）

### 2.1 第一类：高价值核心引擎（直接迁移，仅剥离极少 MLflow 耦合）

| 原模块路径 | 代码量 | 核心能力 | 现有 MLflow 耦合点 | 迁移重构动作 |
|---|---|---|---|---|
| `contracts.py` | 641 行 | `Case`、`Turn`、`InterruptResponse`、`MetricSpec`、`ArtifactAssertion`、`ToolConstraint`、`Evidence`、`MetricResult` | **0 耦合** | 迁入共享契约 / `eval_runner/domain/contracts.py`（`platform-api` 与 `runtime-service` 按相同 Schema 校验），补充白皮书增强指标与 TTFT 字段。 |
| `simulation.py` | 594 行 | 中文动态博弈仿真引擎：7 类澄清表单解析、Plan 打回与核准、工具白名单审批、隐藏事实/延迟夹具注入 | 仅调用 `workbench_access.authorize_grant` | 迁入 `eval_runner/engine/simulation.py`，改为依赖 `platform-api` 授权状态与能力校验。 |
| `targets/agent_platform.py` | 1201 行 | 通过平台 HTTP API 执行被测 Agent、上传夹具、审批基线防偷跑、采集终态工件与用量 | 仅 `collect_traces()` 调用 `MlflowClient` 拉取 Trace | **拆分为两块**：1) 扩展驱动器支持流式 SSE 探针测 TTFT 与多 Graph 能力分层匹配；2) `collect_traces` 保留只读对接 MLflow 查询 Trace。 |
| `tool_evidence.py` | 161 行 | 从原生 LLM/TOOL Span 提取 `requested` / `executed` / `blocked`，识别虚假执行与冲突 | 仅读取 Span 字典结构 | 直接迁入 `eval_runner/evidence/tool_evidence.py`。 |
| `runtime_signals.py` | 105 行 | 从 Trace 恢复 `loop_observation` 死循环信号 | 仅读取 Span 字典结构 | 直接迁入，并向上汇总批次死循环率统计。 |
| `scorers/agent_platform.py` | 692 行 | 13 种代码物理规则 `rule()` + 12 种 DeepEval/语义裁判 `score_case()` | 仅第 394 行 `from mlflow.genai.scorers.deepeval import get_scorer` | 迁入 `eval_runner/scorers/`，将 4 个 DeepEval 内置指标改为直接实例化 `deepeval.metrics.*`，彻底去除 MLflow scorer 依赖。 |
| `scorers/judge.py` & `scorers/budget.py` | ~200 行 | `XiaokJudge`（3 次重试、结构化输出修复、非思考模式）与 `JudgeBudget`（Token/请求硬隔离、防连坐） | **0 耦合** | **去私有网关改造**：废除从 `config.py` 读取 `~/.my_best/.env`（`XIAOK_PROXY_URL` / `BAILIAN_URL`），改为通过 `platform-api` 内部解析接口获取用户选定的**平台网关模型连接**，并融入 `../LightRAG/evaluation/deepeval_runner.py` 的 JSON 截断修补与 429 随机退避。 |
| `gates.py` | 213 行 | `FACT_METRICS` / `SAFETY_METRICS` 一票否决、基线对比防退化门禁 | **0 耦合** | 迁入 `eval_runner/engine/gates.py`（兼供 `platform-api` 对比展示）。 |
| `agent/`（目录） | 5 文件 | LangGraph 出题 Copilot（`prepare -> propose -> validate` 闭环）与事实核算/校验工具 | **0 耦合** | **迁入 `apps/runtime-service/src/runtime_service/services/eval_copilot/`**：复用平台模型路由与预算中间件，通过 HMAC 只读回调从 `platform-api` 读取源会话摘要与草稿。 |
| `diagnosis/`（目录） | 4 文件 | 独立 LangGraph 诊断专家（8 步有界只读取证、引用校验、`compare_runs`） | `results.py` 读 MLflow Run/Artifacts | **迁入 `apps/runtime-service/src/runtime_service/services/eval_diagnosis/`**：复用平台模型路由；原 `results.py` 改为通过 `platform-api` 内部 HMAC 回调按 `offset` 分片读取 PG/证据目录快照。 |
| `calibration.py` & `quality.py` | 308 行 | 人工抽检一致率标定、运行质量异常分类 | **0 耦合** | 迁入 `eval_runner` / `platform-api` 并补充 Cohen's Kappa 计算与四维异常细分。 |
| `datasets/`（内置资产） | JSONL 集合 | `v1/cases.jsonl`（20 题）及 `v2` / `v3-golden` 标准测试集 | **0 耦合** | 作为内置基准种子导入/初始化至平台 `eval_suites`。 |

### 2.2 第二类：领域逻辑保留、移入 `platform-api` PostgreSQL 与调度重构

| 原模块路径 | 代码量 | 原设计痛点 | 迁移重构方式 |
|---|---|---|---|
| `work_items.py` | 1573 行 | 全部工作项存在 `.local-stack/work-items/*.json` + 文件锁，曾触发 $O(N \times M)$ 读盘卡死 | 保留草稿/修订/候选采纳/版本冻结校验逻辑，全面迁入 `platform-api/modules/evaluation/` + PG 表（`eval_suites` / `eval_cases` / `eval_versions`）。 |
| `dataset_registry.py` | 414 行 | 混合维护本地 JSON 索引与 MLflow Dataset 元数据 | 保留版本不可变快照（`content_hash`）与防篡改校验，元数据由 `platform-api` PostgreSQL 管理；不再强制向 MLflow 注册 Dataset。 |
| `tasks.py` & `task_worker.py` | 677 行 | 文件队列 + 进程互斥锁，跨重启状态恢复繁琐 | 控制面状态表迁入 `platform-api`（`eval_runs` / `eval_run_cases` + Redis 队列/分布式锁），实际并发调度迁入 `apps/eval-runner/`（支持暂停、断点续跑、仅重跑失败题）。 |
| `run.py` | 581 行 | 混杂 CLI、并发执行与强制向 MLflow `start_run` / `log_table` / `log_feedback` 同步写入 | 保留 `ThreadPoolExecutor`/异步并发逻辑、Case 检查点隔离、以及 `evaluator_identity` 指纹校验；结果直接写入共享 PG 与证据存储，支持 `eval-runner` CLI 跑 CI 门禁。 |
| `connections.py` | 340 行 | 将来源、题库、靶场、MLflow 实验四者死绑 | **彻底拆解**：废除 `Connection`；改为“题库资产”与“开考时动态选择目标隔离项目（`target_project_id`）+ 平台模型目录 UUID”。 |
| `curation.py` & `inspection.py` | 667 行 | 依赖 MLflow Review Queue 实现坏样本回流与定期巡检 | 人工审核与定时巡检规则迁入 `platform-api`（PG 表），巡检执行触发进 `eval-runner`，告警复用平台通知中心。 |
| `trace_reader.py` | 488 行 | 为了绕过 MLflow API 卡死而在 SQLite/Artifact 层硬读 protobuf/JSON | 若 MLflow 仅作链路追踪，在 `eval-runner` 仅保留受控只读 `TraceFetcher`（按 `trace_id` 拉取 Span 给规则取证，设 8MiB/1万 Span 硬上限）。 |

### 2.3 第三类：淘汰舍弃清单（不迁移）

以下模块完全服务于旧 MLflow 外挂架构与私人本地网关，迁入后**全部淘汰**：
- `config.py` 中的本地 `~/.my_best/.env`（`XIAOK_PROXY_URL` / `XIAOK_PROXY_API_KEY` / `BAILIAN_URL`）私有网关加载逻辑（改直连平台模型网关）
- `app.py`（FastAPI 强行插队 MLflow 路由）、`authoring_api.py`（MLflow 专属网关）
- `browser_login.py`（7 天滑动 Cookie 补丁）、`sso.py`（MLflow 影子账号同步）、`access.py`、`authorization_batches.py`、`network.py`（统一使用 `platform-api` 既有 IAM 与 JWT 体系）
- `mlflow_results.py`（`_evaluations.json` / `_assessments.json` 拼装上传器）与 `feedback_projection.py`
- `web/src/evaluation-tasks/AuthoringPage.tsx` 及所有 MLflow React/Redux 壳层组件（前端在 `platform-web` 以 Vue 3 原生重构）。

---

## 3. 前端与参考能力迁移关系

| 参考来源 | 可迁移或借鉴部分 | 不迁移部分 |
|---|---|---|
| `../mlflow-eval-platform/web/src/evaluation-tasks/` | 动态博弈时间轴交互设计（`SimulationTimeline`）、诊断专家抽屉交互（`EvaluationExpert`）、候选 Diff 审阅与部分采纳逻辑（`CandidateReview` / `ProposalChanges`）、Step 1~4 降噪原则 | 4200 行 `AuthoringPage.tsx` 巨石组件、`TracesV4SessionDrawerContent`、所有 `@databricks/*` 与 MLflow Store 依赖 |
| `../LightRAG/lightrag_webui/src/features/evaluation/` | 资产全景卡片与血缘标签（`DatasetPanoramaView`）、开考就绪度守卫横幅、矩阵多模式对比配置、打擂大厅按题库聚合与涨跌幅（`EvaluationTaskCenter`）、Head-to-Head 对比 PK 弹窗（`EvaluationComparisonModal`） | LightRAG 专属知识库切库字段与硬编码外网端口 |

---

## 4. 存量资产平滑兼容策略（按需导入）

- 若 `../mlflow-eval-platform/.local-stack` 下已有历史发布的黄金集或业务转换题库（`work-items/*.json` / `.jsonl`），可提供一次性导入 CLI `eval-runner import-legacy --dir ...`（写入平台 PostgreSQL `eval_suites`）：
  - 读取旧 `Case` v1/v2/v3 JSONL 与 `work_items` 快照，校验结构与 `content_hash` 后写入对应项目资产；
  - 保留历史来源标记与版本记录，不强求用户手工重新出题。

---

## 5. 本专题规划任务（待启动实施）

### Task 2.1：抽离评测核心引擎、直连平台模型网关并迁移专家 Graph
**状态：** 待开始（方案 X 归属已对齐）。
**完成标准：** `contracts`、`simulation`、`tool_evidence`、`scorers`（原生 `deepeval.metrics` + 平台模型目录解析）与 `gates` 迁入 `apps/eval-runner/`；资产 CRUD 迁入 `platform-api`；出题 Copilot 与诊断专家作为标准 Graph 迁入 `runtime-service/services/` 并通过单元测试。
**涉及位置：** `apps/eval-runner/`、`apps/platform-api/src/platform_api/modules/evaluation/`、`apps/runtime-service/src/runtime_service/services/`。

- [ ] 迁移领域契约与规则/语义评分器，剥离 `mlflow.genai` 及 `~/.my_best/.env` 私有网关依赖，改为解析平台网关模型。
- [ ] 迁移中文动态博弈引擎与支持多 Graph + 流式 SSE 探针的执行客户端，接入只读 MLflow Trace 拉取适配器。
- [ ] 将出题 Copilot (`eval_copilot`) 与独立诊断专家 (`eval_diagnosis`) 迁入 `runtime-service` 并接入 `platform-api` HMAC 内部数据桥，补齐单元测试。

**下一步：** 随其余专题实施任务一并获准后启动脚手架搭建。
