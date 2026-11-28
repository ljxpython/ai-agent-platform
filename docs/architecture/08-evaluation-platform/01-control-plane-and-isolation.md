# 08-01 控制面数据建模、环境隔离与零信任内部代理桥

> **三承三启导航**
> - **承前**：前端「评测中心」发起的建库、编辑、冻结、开考与 PK 请求均以用户 Bearer JWT 抵达 `platform-api`。
> - **居中**：本篇拆解 `apps/platform-api/src/platform_api/modules/evaluation/` 如何通过 8 张 PostgreSQL 表管理资产生命周期、通过 Readiness 守卫校验靶场与图能力，并通过 `/api/evaluation/internal/*` HMAC 内部桥安全衔接 `eval-runner` 与 `runtime-service`。
> - **启后**：`eval-runner` 基于本层持久化的 `eval_runs` / `eval_run_cases` 领任务，并通过内部桥完成沙箱初始化、轮次执行与取证（详见 [02-execution-simulation-and-evidence.md](02-execution-simulation-and-evidence.md)）。

---

## 一、 痛点与设计对比（Naive vs. Production）

- **简易原型（Naive Demo）**：把评测集存成几个 JSON 文件，点一下“开始评测”直接在 FastAPI HTTP 请求里开个 `for` 循环调被测 Agent，拿不到就超时 504，服务一重启运行记录全丢。
- **工业级实现（Production Reality）**：
  1. **读写与执行分离**：`POST /api/evaluation/studio/runs` 仅在事务内把 `eval_runs` 和 `eval_run_cases`（按 `repeat_k` 展开）写为 `queued`/`pending` 状态并秒级返回 `201`，长耗时执行交给独立的 `eval-runner` Worker 轮询认领；
  2. **不可变版本冻结**：编辑在 `eval_cases` 草稿区进行，发起评测前必须冻结为 `eval_suite_versions` 快照，保证历史上任何一场打擂都可以精确回溯当时的考题与断言；
  3. **专用靶场防污染机制**：评测会写入会话历史、沙箱文件与模型账单，`eval_sandbox_projects` 显式区分专用靶场与普通业务项目，避免误把线上项目记忆跑脏。

---

## 二、 PostgreSQL 8 张核心业务表全景

表结构定义于 [models.py](../../apps/platform-api/src/platform_api/modules/evaluation/models.py)：

| 表名 | 主键 / 唯一键 | 核心字段 | 架构职责 |
|---|---|---|---|
| `eval_suites` | `id` (UUID) | `name`, `suite_type` (`curated`/`session_converted`/`imported`), `owner_project_id`, `source_project_id`, `default_graph_id`, `archived_at` | 题库资产主表；记录来源血缘与归属项目 |
| `eval_cases` | `id`；唯一键 `(suite_id, case_key)` | `split` (`dev`/`holdout`), `schema_version`, `required_capabilities_json`, `turns_json`, `simulation_json`, `expectations_json`, `metrics_json` | 可编辑草稿态考题；支持内联编辑与高级断言配置 |
| `eval_suite_versions` | `id`；唯一键 `(suite_id, version_num)` | `content_hash` (SHA-256), `frozen_cases_json`, `published_by`, `published_at` | 冻结版本快照；PK 对比的基准锚点 |
| `eval_runs` | `id` | `suite_id`, `version_id`, `owner_project_id`, `target_project_id`, `target_graph_id`, `target_agent_id`, `target_model_id`, `judge_model_id`, `matrix_group_id`, `concurrency` (1~5), `repeat_k`, `status`, `gate_exit_code`, `summary_metrics_json` | 一次打擂任务主记录；支持并发、重复采样与矩阵对比分组 |
| `eval_run_cases` | `id`；唯一键 `(run_id, case_key, attempt_idx)` | `status`, `thread_id`, `trace_ids_json`, `rule_passed`, `overall_score`, `duration_ms`, `ttft_ms`, `token_usage_json`, `cost_usd`, `error_category`, `evidence_path`, `results_json` | 细粒度到单题第 `k` 次尝试的断点检查点与成绩明细 |
| `eval_human_reviews` | `id` | `run_case_id`, `reviewer_id`, `human_verdict`, `reason`, `aligned_with_judge` | L3 人工专家抽检标定记录，用于计算人机一致率与 Kappa |
| `eval_patrol_schedules` | `id` | `suite_id`, `version_id`, `cron_expr`, `enabled`, `notify_channels_json`, `last_run_id` | 定时自动巡检规则表（当前阶段调度器处于后置状态） |
| `eval_sandbox_projects` | `project_id` | `is_sandbox`, `updated_by`, `updated_at` | 靶场白名单标记；非白名单项目开考触发二次确认守卫 |

---

## 三、 Readiness 开考就绪度守卫与专家 Graph

### 3.1 能力分级与 Readiness 检查（[targets.py](../../apps/platform-api/src/platform_api/modules/evaluation/targets.py)）
平台首批放开 `dearflow_agent`、`showcase_demo`、`reference_agent`、`workflow_demo` 四大图用于评测（排除 `platform_assistant`）。开考前前端调用 `POST /api/evaluation/studio/readiness`：
- 校验 `target_project_id` 是否在 `eval_sandbox_projects` 登记（未登记返回非阻塞风险确认提示，防止误污染业务项目）；
- 核对所选 `target_graph_id` 具备的能力（如是否支持工作区文件 `workspace`、工具执行 `execute`、人机中断 `hitl`）与考题 `required_capabilities` 是否兼容；
- 校验裁判模型与 Embedding 模型在平台模型目录中可用且具备对应项目访问授权。

### 3.2 内置专家智能体（`eval_copilot` & `eval_diagnosis`）
两个专家不再寄生在独立进程，而是作为标准 LangGraph 迁入 `apps/runtime-service/src/runtime_service/services/`，由 [studio_router.py](../../apps/platform-api/src/platform_api/modules/evaluation/studio_router.py) 代理流式对话：
- **`eval_copilot`（出题专家）**：读取题库草稿或转化后的脱敏会话资料，辅助生成/修订多轮用例、断言与模拟人设；
- **`eval_diagnosis`（诊断专家）**：读取 `eval_runs` / `eval_run_cases` 及分片证据快照，对失败题目按白皮书**三层 Gap** 给出结构化归因：
  - `data_gap`（数据源缺失）→ 建议补夹具或知识库文档；
  - `retrieval_gap`（检索召回残缺）→ 建议调 Top-K/切片/Rerank；
  - `reasoning_gap`（推理与规划偏离）→ 建议改 Prompt、修工具文档或调整模型。

---

## 四、 跨进程零信任交互：HMAC 内部桥全接口协议

由于 `eval-runner` 是独立运行进程，无法直接信任外部入参，[studio_router.py](../../apps/platform-api/src/platform_api/modules/evaluation/studio_router.py#L76-L90) 通过 `_verify_internal_hmac` 对所有 `/api/evaluation/internal/*` 接口强制验签：

### 4.1 真实签名报文规范
```text
HTTP Headers:
  x-eval-time: "1795848000"                  # Unix 秒级时间戳，允许 ±60s 时钟漂移
  x-eval-signature: "<hex sha256>"           # HMAC-SHA256(runtime_delegation_secret, message)

签名原文构造:
  message = purpose.encode() + b"\n" + stamp.encode() + b"\n" + raw_body
```

### 4.2 五大内部端点与真实职责

| 内部端点 | `purpose` 标识 | 核心作用与高保真逻辑 |
|---|---|---|
| `POST /api/evaluation/internal/thread-setup` | `thread_setup` | 在 `target_project_id` 创建/复用隔离线程；遍历 `fixtures` 调用 `gateway.upload_thread_file` 注入测试文件，扫描工作区初始文件返回 `fixture_paths`（用于替换提示词中 `{{文件名}}`）与 `initial_artifacts` 基线。 |
| `POST /api/evaluation/internal/execute-turn` | `execute_turn` | 1) 普通提问：构造 `input` 调 `gateway.stream_thread_run` 透传 SSE 给探针；<br>2) **中断续跑（`command` 非空）**：**严禁再走新建 Run**（否则触发 `resume_configuration_override` HTTP 400），必须改调 `gateway.send_thread_command(method="input.respond", payload=command)` 后接 `gateway.join_thread_run_stream(...)` 原路恢复 SSE 流！ |
| `POST /api/evaluation/internal/thread-evidence` | `thread_evidence` | 一次拉回白盒评判所需的全部事实：线程 `state`（含 `messages` 与 `interrupts`）、`runs` 列表、`diagnostics`（循环与异常事件）、`workspace_tree` 与按 `artifact_paths` 读取的真实文件内容及 `artifact_read_errors`。 |
| `POST /api/evaluation/internal/cross-project-probe` | `cross_project_probe` | 发起受控跨项目读取探测，验证目标线程/上下文无法越权触及非 `target_project_id` 资源，返回 `status_code` 供 `cross_project_denied` 判定。 |
| `POST /api/evaluation/internal/resolve-model` & `thread-usage` | `resolve_model` / `thread_usage` | 解析平台目录授权模型的真实端点、加密凭据与单价，以及拉取被测线程累计 `known_tokens` 与 `estimated_cost_usd`。 |

---

## 五、 架构不变量清单（本层红线）

1. **内部接口必须双重校验**：除 HMAC 签名与 60 秒窗口外，所有涉及线程、工作区与模型解析的内部调用均以数据库 `eval_runs.target_project_id` 和 `created_by` 作为授权上下文，禁止外部自由指定任意线上项目。
2. **中断续跑不可覆盖运行配置**：带 `command={"resume": ...}` 恢复线程时绝不透传启动型 `configurable` 覆盖项，统一走 `input.respond` 指令通道。
3. **版本冻结即快照**：一旦 `eval_suite_versions` 生成，后续修改 `eval_cases` 绝不影响已冻结版本与历史 `eval_runs` 的可复现性。
