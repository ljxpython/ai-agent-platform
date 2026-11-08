# MLflow 链路追踪与会话评测适配验证报告

## 验证环境
- **代码分支**：`feat/mlflow-tracing-adaptation` (Worktree: `~/.codex/worktrees/mlflow-tracing-adaptation/ai-agent-platform`)
- **平台环境**：Local Stack `wt_fd76619df570`（Web: `25264`, API: `27954`, Runtime: `23714`, Redis: `26257`）
- **追踪后端**：本地 `mlflow-eval-platform`（后端 API: `5001`, 前端 SPA: `9128`）及远端 `sshmy1:5000`

---

## 阶段结果汇总

| 阶段 | 验证目标 | 验证命令/手段 | 结果 |
|---|---|---|---|
| Phase 1 | CORS 与 X-Frame-Options 限制解除 | `curl -sI http://127.0.0.1:5001` / `sshmy1:5000` | ✅ PASS（`x-frame-options` 成功移除，`access-control-allow-origin: *`） |
| Phase 2 | Runtime MLflow Tracer 回调及 Fail-soft | `uv run pytest tests/observability/ -v` | ✅ PASS（153 项测试全部通过，含 3 项专属 MLflow Tracer 测试） |
| Phase 3 | Platform API 诊断协议放宽 | `uv run pytest tests/test_run_diagnostics.py -v` | ✅ PASS（28 项测试全部通过） |
| Phase 4 | Platform Web URL 构造与诊断页面 | `pnpm exec vitest run ...` | ✅ PASS（10 项单测全部通过） |
| Phase 5 | 端到端全链路真实浏览器流式交互与追踪上报 | `browser-skill` (`bsk`) 自动化操作 Chrome | ✅ PASS（真实发起对话、实时流式响应、轨迹排障渲染、EvalFlow 自动建立 `ai-agent-platform-traces` 产生 1 条 OK Trace） |
| Phase 6 | 前端类型安全加固与真实浏览器排障体验闭环 | `vue-tsc --noEmit` + `bsk` 真实验证与链接纠偏 | ✅ PASS（图标类型收敛至 `activity`/`graph`、Vite 环境变量热生效至前端 SPA `9128`、Loki 未连接优雅降级并直达 EvalFlow） |
| Phase 7 | 对话前端全场景 Trace 直达验证（方案一 + 二 + 三） | `browser-skill` (`bsk`) 对真实会话逐项核验 | ✅ PASS（Header 会话追踪、消息级链路直达、轨迹 Tab 链路树 3 处入口均 100% 渲染且链接指向 `9128` 与准确 `session_id`） |
| Phase 8 | 安全防御、项目隔离与 Session 详情穿透验证 | `browser-skill` (`bsk`) 深度攻防实测与真实调用 | ✅ PASS（场景一：`none` 模式下按钮和链接彻底从 DOM 消失且无任何报错；场景二：运行时自动在 EvalFlow 动态创建 `project-5a5b7239-43e3-40e6-bba3-e64d96057607`（实验 8）实现物理隔离；场景三：直达 URL 对齐为 `#/experiments/{exp}/chat-sessions/{sessionId}`，零心智负担直达单会话全景卡片） |

---

## 阶段八真实链路凭据（安全防御、项目隔离与会话详情穿透）

### 1. 场景一（安全防御与无追踪降级）
- **模拟机制**：通过 `sessionStorage` 或环境变量动态配置 `VITE_TRACING_PROVIDER=none`。
- **验证结果**：
  - 顶部 Header【EvalFlow 追踪 ↗】彻底从 DOM 中移除；
  - 消息卡片底部的【链路 ↗】与轨迹 Tab 工具栏的【EvalFlow 链路树 ↗】均彻底隐形；
  - 页面控制台与视图零任何报错，用户交互完全不受任何影响。
- **截图凭证**：`tracing_none_mode_proven.png` 与 `trajectory_none_mode_proven.png`。

### 2. 场景二（Project 维度项目物理隔离）
- **执行机制**：`MLflowFailSoftCallback` 初始化时自动根据上下文的 `project_id` 执行 `mlflow.set_experiment(f"project-{project_id}")`。
- **实测生成实验**：
  - 实验 ID：`8`
  - 实验名称：`project-5a5b7239-43e3-40e6-bba3-e64d96057607`
  - Artifacts 路径：`/Users/lijiaxin/PyCharmMiscProject/mlflow-eval-platform/data/artifacts/8`
  - 仅包含属于该项目的链路追踪（1 条真实 Trace，8.8s，OK）。
- **截图凭证**：`evalflow_project_experiment_8.png` 与 `evalflow_experiment_8_traces.png`。

### 3. 场景三（超级链接穿透直达线程 ID）
- **路由对齐**：MLflow 原生单会话详情路由为 `#/experiments/{experimentId}/chat-sessions/{sessionId}`。
- **直达呈现**：点击直达按钮后，EvalFlow 呈现完整的会话全景视图（会话总令牌 11169、延迟 7.35s、用户与 Agent 每一轮交互气泡、右侧完整跟踪调用树抽屉）。
- **截图凭证**：`evalflow_chat_sessions_view.png`。

---

## 真实链路执行凭据

### 1. 对话与会话凭据
- **用户 Prompt**：`你好，请输出 hello world`
- **Agent 输出**：`你好！hello world 如果需要，我可以给出不同语言（Python / JavaScript / C / Bash / SQL 等）的版本...`
- **耗时与 Token**：Duration: `3678 ms`，Tokens In: `11141` · Out: `74`
- **Thread ID (Session)**：`e8247577-95c6-4aad-9d3f-8b4cc3b44b44`

### 2. MLflow / EvalFlow 上报凭据
- **实验名称**：`ai-agent-platform-traces`
- **Trace ID**：`tr-e245eda13f6aa1f91f58b110f9b9014b`
- **关联 Session**：`e8247577-95c6-4aad-9d3f-8b4cc3b44b44`
- **上报 Tags**：`tenant_id: __default`、`skills`、`dear_skill_snapshot`、`dear_memory_source` 等平台治理上下文全部无损透传
- **Tracing 状态**：`OK`

---

## 判定结论
- **完成度判定**：✅ **Done (全部完成)**
- 满足工业级零破坏、平滑热切换要求，随时可通过 `TRACING_PROVIDER`（`mlflow`/`langfuse`/`both`/`none`）切换或双写。
