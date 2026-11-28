# 专题 03：评测引擎、并发调度与断点续跑机制

> 所属项目：[独立评测中台迁移与平台原生化改造方案](README.md)｜状态：**方案已对齐（方案 X，待开始编码）**
> **架构前提说明**：基于已确认的 **方案 X**，题库资产/版本/运行主数据通过 Alembic 落库至 `platform-api` 现有 **PostgreSQL** 并由控制面提供同步 REST CRUD；并发执行、多轮仿真、流式 SSE 测 TTFT、DeepEval 打分（直连平台网关模型）与定时巡检/CLI 门禁运行在共享 PG + Redis 底座的轻量进程 **`apps/eval-runner`** 上，同机部署于 `sshmy1`。

## 1. 引擎定位与复用底座的运行形态

新增轻量工作进程包 `apps/eval-runner/`（FastAPI/健康探针可选 + Typer/CLI + 异步/线程池调度器），全面复用平台现成基建而不重造轮子：

1. **底座统一共享（不重造 Auth/DB）**：
   - 直连平台同一套 PostgreSQL（读取任务与用例快照、原子更新单题检查点状态、写入评分结论，大体积 `evidence.json` 落受控本地/共享归档目录并在 DB 保存相对路径与索引）；
   - 共用同一套 Redis 负责分布式调度锁、待执行任务队列与实时进度事件广播（**硬约束：进度事件仅传状态摘要与游标，禁止将大正文打入 Redis 并统一配置短 TTL，防止重演 1.4~1.9 GB Redis 内存占用问题**）；
   - 通过平台内部签名从 `platform-api` 获取已配置的**裁判 LLM 模型与 Embedding 模型连接**，以及驱动被测 Agent 的执行令牌。
2. **独立 CLI / 巡检 / CI 门禁能力**：
   - 接入 `scripts/local-stack.sh` 统一启停（遵循 Worktree 隔离规范）；
   - 同时保留独立 CLI（`eval-runner worker` / `eval-runner gate --suite ... --target-project ...` / `eval-runner patrol`），无需借助浏览器即可直接在服务器或 CI 跑通发版门禁。

---

## 2. 核心数据模型（落库 `platform_api` PostgreSQL，告别文件锁与递归读盘）

针对旧版 `work_items.py` 依赖文件锁和全目录扫描引发的列表慢、状态同步难问题，在 `platform-api` 通过 Alembic 建立 7 张评测核心表（大体积完整证据快照存磁盘归档，PG 只存元数据、得分、耗时摘要与引用路径）：

| 核心表名 | 职责说明 | 关键字段 |
|---|---|---|
| `eval_suites` | 评测集（工作项）主表 | `id`, `name`, `description`, `suite_type` (`golden`/`regression`/`curated`/`benchmark`), `owner_project_id`, `source_project_id`, `default_graph_id`, `created_by`, `archived_at` |
| `eval_cases` | 用例明细表（支持草稿编辑） | `id`, `suite_id`, `case_key`, `split` (`dev`/`holdout`), `schema_version`, `required_capabilities_json`, `turns_json`, `simulation_json`, `expectations_json`, `metrics_json`, `updated_at` |
| `eval_suite_versions` | 不可变发布版本快照 | `id`, `suite_id`, `version_num`, `content_hash`, `frozen_cases_json`, `published_by`, `published_at` |
| `eval_runs` | 评测执行批次（支持矩阵与对比） | `id`, `suite_id`, `version_id`, `target_project_id`, `target_graph_id`, `target_snapshot_json`, `judge_model_id`, `embedding_model_id`, `matrix_group_id`, `mode`, `concurrency`, `repeat_k`, `status`, `gate_exit_code`, `summary_metrics_json`, `created_by`, `created_at`, `finished_at` |
| `eval_run_cases` | **单题并发与断点检查点表** | `id`, `run_id`, `case_key`, `attempt_idx`, `status` (`pending`/`running`/`completed`/`failed`/`error`/`paused`/`skipped_incompatible`), `thread_id`, `trace_ids_json`, `rule_passed`, `overall_score`, `duration_ms`, `ttft_ms`, `token_usage_json`, `cost_usd`, `error_category`, `evidence_path`, `results_json` |
| `eval_human_reviews` | L3 人工抽检与争议标定表 | `id`, `run_case_id`, `reviewer_id`, `human_verdict` (`pass`/`fail`), `reason`, `aligned_with_judge`, `created_at` |
| `eval_patrol_schedules` | 定时巡检配置表 | `id`, `name`, `suite_id`, `version_id`, `target_project_id`, `target_graph_id`, `judge_model_id`, `cron_expr`, `enabled`, `notify_channels_json`, `last_run_id` |

---

## 3. 受控并发执行（默认 3、范围 1~5）与断点续跑引擎

解决“串行跑慢 + 中断白跑 + 裁判连坐”痛点，执行引擎按以下机制运转：

### 3.1 Case 级隔离与受控并发池
- **已确认并发规格**：每个 `eval_run` 默认 `concurrency = 3`，前端可调范围固定为 **`1 ~ 5`**；`eval-runner` 进程另设全局信号量防止多批同时开跑挤爆 `sshmy1` 4GB 宿主机与下游模型并发配额。
- **天然无碰撞隔离**：每个 Case（及 Pass^k 模式下每次 `attempt_idx`）在 `target_project_id` 下创建全新 `thread_id`，拥有独立磁盘产物工作目录 `results/{run_id}/{case_key}/attempt_{k}/evidence.json` 和独立 `JudgeBudget` 计数槽位，Case 间无任何共享可变状态。
- **流式 SSE 探针测 TTFT**：`eval-runner` 驱动被测 Agent 时优先使用平台流式 SSE（`/api/langgraph/threads/{thread_id}/runs/stream` 或等价评测流），从请求发出 `t0` 监听至首个有效助手机器人内容分片到达 `t1`，精确计算 `ttft_ms`（跳过心跳帧与空建图元数据帧），同时保留完整响应与执行终态。
- **两级信号量防流控**：将“被测 Agent 对话轮次（`agent_semaphore`）”与“DeepEval 平台模型裁判打分（`judge_semaphore`）”拆分限流，某题跑完 Agent 后立即释放执行槽位并异步进入裁判池，避免裁判排队拖慢吞吐。

### 3.2 检查点驱动的暂停、断点续跑与失败重跑
吸取 `../mlflow-eval-platform` 近期 `029701cfe` 与 `20b5ed68e` 的实战经验，直接作为一等公民原生内置：
1. **单题原子检查点**：每道 Case 跑完 `Simulation -> Evidence Collection -> Scoring` 任一阶段，立即更新 PG `eval_run_cases` 状态并落盘 `evidence.json`。
2. **故障零连坐**：某题遇到大模型裁判 500/超时、网络瞬断或工具异常，先做最多 3 次指数退避重试；若仍失败，仅将该题标记为 `error`（记录 `error_category`），**绝不拉闸整批任务**，其余并发 Case 正常推进。
3. **三大控制动作**：
   - **暂停（Pause）**：通过 Redis/PG 状态发出协作停止信号，等待在途单个对话轮次安全收口后将剩余 `pending` 题目保持在检查点，状态置为 `paused`；
   - **继续未完成（Resume）**：仅过滤状态为 `pending` / `paused` / `cancelled` 的题目入池，已 `completed` 的题目直接复用结果并重算汇总门禁；
   - **仅重跑失败题（Retry Failed Only）**：仅将 `failed` 或 `error` 的题目复位重跑，保留已通过题目的完整证据和评分。
4. **同证据重评（Re-score Without Re-running Agent）**：保留核心优势——修改评分标准时，直接复用已有 `evidence.json` + MLflow Trace 重新运行 L1/L2 打分器，0 次调用被测 Agent。

---

## 4. 矩阵打擂、能力分级 Readiness 守卫与门禁触发

1. **多参数矩阵打擂（Matrix Battle）**：
   - 借鉴 LightRAG 的 `matrix-run`：一次提交生成同一 `matrix_group_id` 下的多个关联 `eval_run`（对比不同模型 `model_id`、不同 Graph、温度或 Prompt），共用冻结题库版本 `version_id`，跑完自动开放横向对比 PK 数据。
2. **能力分级与开考前就绪度守卫（Readiness Guard，已确认）**：
   - 借鉴 LightRAG `/readiness` 并结合多 Graph 能力差异：开考前校验目标项目权限、目标 Graph（`dearflow_agent` / `showcase_demo` / `reference_agent` / `workflow_demo`）激活状态、所选平台裁判/Embedding 模型是否可用；**逐题比对用例所需能力与所选 Graph 能力（如无工作区的 `reference_agent` 是否能执行带 `/workspace/work/` 文件断言的题），不兼容题目在开考弹窗直接提示原因并拦截**；对非专用测试靶场项目弹出黄/红风险警告待确认后放行。
3. **三大触发机制对齐白皮书**：
   - **手动触发**：Web 工作台交互式启动、单题调试；
   - **定时巡检（Scheduled Patrol）**：`eval-runner patrol` 或轻量内置调度器按 Cron 触发，退化或异常时通过 `platform-api` 通知中心/Apprise 发送飞书/Webhook 告警；
   - **发版门禁（CI Gate CLI/HTTP）**：提供 `POST /api/evaluation/gates/evaluate` 与 CLI `eval-runner gate`，输出标准 `exit_code`（`0=通过`、`1=业务/安全门禁未达标`、`2=基础设施错误`）。

---

## 5. 各组件职责交互总表

| 交互方 | 通道与协议 | 传递内容与用途 |
|---|---|---|
| `platform-web` ⇄ `platform-api` | 标准 REST + JWT | 资产管理、Readiness 检查（含能力分级与风险提示）、发起/暂停/重跑批次、7 维成绩与 PK 查询、L3 人工标注；专家对话走 `/api/langgraph/*` |
| `eval-runner` ⇄ 共享 PG/Redis | 同实例 PG 连接 + Redis | 拉取队列任务与并发控制、写 `eval_run_cases` 单题检查点、推精简进度状态（严格 TTL 与大小上限） |
| `eval-runner` → `platform-api` | 内部 HMAC 签名 + 公开执行入口 | 1) 解析平台网关模型与 Embedding 连接 (`/internal/judge-model-config`) 并上报预算用量；2) 通过 `/api/evaluation/...` + 流式 SSE 跑被测 Agent 与测 TTFT；3) 触发巡检告警通知 |
| `runtime-service`（专家图） → `platform-api` | HMAC 只读回调 | `eval_copilot` 取源会话与草稿；`eval_diagnosis` 按 `offset` 分片取 `overview`/`cases`/`evidence`/`compare_runs` |
| `eval-runner` → `MLflow Server` | 只读 MLflow Client API | 按 `project-{target_project_id}` 检索评测期间由 `runtime-service` 产生的 Trace/Span，提取工具/检索证据并生成 `trace_url` |

---

## 6. 本专题规划任务（待启动实施）

### Task 3.1：`platform-api` 评测表迁移、控制面 API 与 Readiness 接口
**状态：** 已完成（done，`platform-api` 全套评测测试 128 passed）。
**完成标准：** 在 `apps/platform-api` 完成 7 张 `eval_*` 表（+ `eval_sandbox_projects`）Alembic 迁移及同步 CRUD API、Readiness 能力分级校验（含非专用靶场风险标签）、DeepEval 模型连接内部解析端点，单元测试全通。
**涉及位置：** `apps/platform-api/migrations/`、`apps/platform-api/src/platform_api/modules/evaluation/`。

- [x] 新增 `eval_*` Alembic 迁移脚本与同步 CRUD Service / Router 层。
- [x] 实现资产 CRUD、冻结发布、任务创建/控制（Pause/Resume/Retry Failed/Re-score）、Readiness 校验及 PK 对比接口。
- [x] 实现内部裁判模型连接解析与 HMAC 数据分片回调。

### Task 3.2：搭建 `apps/eval-runner` 并发执行池、TTFT 探针与门禁 CLI
**状态：** 部分完成（partial，核心调度/TTFT/门禁/单测已通过；`local-stack.sh` 编排注册与真实数据库 Worker 轮询待全栈联调阶段接入）。
**完成标准：** `eval-runner` 支持默认 `3`（`1~5`）并发运行多 Graph 用例，验证流式 SSE 测 TTFT、Pause/Resume/Retry Failed、单题异常零连坐、同证据重评、矩阵打擂与 CLI 门禁退出码。
**涉及位置：** `apps/eval-runner/`、`scripts/local-stack.sh`、`scripts/local_stack_processes.py`。

- [x] 初始化 `apps/eval-runner` 包与 CLI（`worker` / `gate`）。
- [x] 实现信号量并发调度池（`1..5`）、SSE 流式 TTFT 探针（完整兼容 LangGraph v3 JSON-RPC 包格式与 delta 累加）、平台模型连接适配器与单题异常隔离。
- [x] 补齐并发故障恢复、门禁退出码与 7 维汇总单元测试（7 passed）。
- [x] 补全真实平台执行器（经 `platform-api` 内部 HMAC `/api/evaluation/internal/execute-turn` 代理驱动目标 Graph 流式 SSE 测 TTFT + `PlatformJudgeLLM` 直连平台目录模型打分）、`eval_runner.worker` 守护循环及 `scripts/local-stack.sh` 托管集成。

### Task 3.3：Agent 总耗时 / TTFT 分段拆解与 Token / 费用全链路透传（含巡检执行后置说明）
**状态：** 已完成（done，`platform-api` 单测 `1 passed` + `eval-runner` 单测 `8 passed`，并在本地真实跑通 `#77350f73`：`TTFT 15732 ms` / `生成耗时 2148 ms` / `Agent 总耗时 17880 ms` / `469 tok` / `$0.000717`）
**完成标准：**
1. `eval-runner` 单题与批次统计拆解并持久化四段真实耗时：`ttft_ms`（首字延迟）、`generation_ms`（首字后生成与工具耗时 = `agent_duration_ms - ttft_ms`）、`agent_duration_ms`（被测 Agent 端到端总耗时）与 `judge_ms`（L2 裁判打分耗时），并产出批次 P50 / P95 / 单题均耗汇总。
2. `platform-api` 新增内部 HMAC 只读接口 `/api/evaluation/internal/thread-usage`，由 `eval-runner` 在单题执行收口后拉取 `gateway.get_thread_usage` 实测 Token 与费用，连同 `PlatformJudgeLLM` 的裁判 Token 与费用写入 `eval_run_cases.token_usage_json`、`cost_usd` 及 `eval_runs.summary_metrics_json`。
3. `eval_patrol_schedules` 定时巡检后台 Cron 自动触发器确认尚未实施，经协商明确**后置至后续迭代实现**（当前仅保留表结构与占位 API）。
**涉及位置：** `apps/platform-api/src/platform_api/modules/evaluation/studio_router.py`、`apps/platform-api/src/platform_api/entrypoints/http/middleware/auth_context.py`、`apps/eval-runner/src/eval_runner/`。

- [x] 新增 `/api/evaluation/internal/thread-usage` HMAC 端点并开放鉴权白名单，按 `run_id` + `thread_id` 查询目标项目真实 Token 与已知费用。
- [x] 更新 `ConcurrentEvalRunner`、`PlatformJudgeLLM`、`metrics_summary.py` 与 `worker.py`：记录分段耗时 `timing_breakdown`（TTFT / 首字后生成 / Agent 总耗时 / 裁判耗时）、落库 `token_usage_json` 与 `cost_usd`，并汇总运行均值。
- [x] 在文档与状态中明确标注「定时巡检后台 Cron 执行器后置实现」。
