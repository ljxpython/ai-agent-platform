# MLflow 链路追踪与会话评测适配任务清单

## 任务执行规范
- 状态标记：`[ ]` 待办，`[/]` 进行中，`[x]` 已完成。
- 关键原则：在独立 Worktree 中开发，本地全套测试跑绿后方可合并。

---

## 阶段一：Worktree 环境建立与远端配置对齐
- [x] **T01：建立专用 Git Worktree**
  - 分支名：`feat/mlflow-tracing-adaptation`
  - 路径：`~/.codex/worktrees/mlflow-tracing-adaptation/ai-agent-platform`
  - 初始化本地栈并确认端口分配（Web: 25264, API: 27954, Runtime: 23714, Redis: 26257）
- [x] **T02：协同配置远端与本地 `mlflow-eval-platform`**
  - 在远端 `sshmy1` 上的 `/opt/mlflow-eval-platform/.env` 与本地 `.env` 注入 `MLFLOW_SERVER_X_FRAME_OPTIONS=NONE`
  - 注入 `MLFLOW_SERVER_CORS_ALLOWED_ORIGINS="*"`
  - 重启 `mlflow-eval.service` 并使用 curl 验证 `x-frame-options` 成功移除，CORS 生效

---

## 阶段二：Runtime Service 追踪适配器开发
- [x] **T03：配置与依赖定义**
  - 在 `apps/runtime-service` 添加 `mlflow>=2.18` 依赖锁定
  - 扩充环境变量配置：`TRACING_PROVIDER`、`MLFLOW_TRACKING_URI`、`MLFLOW_EXPERIMENT_NAME`
- [x] **T04：实现 `MLflowFailSoftCallback` 适配器**
  - 创建 `apps/runtime-service/src/runtime_service/observability/mlflow_tracer.py`
  - 绑定 `mlflow.session_id`（对应 `thread_id`）、`client_request_id`（对应 `platform_trace_id`）与 `user`
  - 实现 Fail-soft 异常降级，确保任何 MLflow 连接失败不影响模型与图执行
- [x] **T05：统一图装配入口**
  - 重构 `apps/runtime-service/src/runtime_service/observability/langfuse.py` 与 `__init__.py`
  - 根据 `TRACING_PROVIDER` 动态分发至 Langfuse、MLflow 或两者并存
  - 更新 `apps/runtime-service/src/runtime_service/observability/query.py` 动态返回 active provider

---

## 阶段三：Platform Web 与 Platform API 契约放开与前端诊断适配
- [x] **T06：新增 MLflow / 统一 Trace URL 构造服务**
  - 在 `apps/platform-web/src/services/observability/langfuse-url.ts` 扩展 `buildMlflowTraceUrl` 与 `buildTraceUrl`
  - 支持按 `session_id = '{thread_id}'` 生成多轮聚合直达链接
  - 编写 Vitest 单元测试，10 项测试全部通过
- [x] **T07：页面入口与诊断弹窗联动**
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` 放宽 `TraceReference.provider`
  - `apps/platform-web/src/modules/chat/diagnostics/types.ts` 放宽 `traceInfoSchema` 校验
  - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue` 接入自适应按钮
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue` 增加 MLflow 链路树直达

---

## 阶段四：联合验证与测试闭环
- [x] **T08：单元测试与全套回归**
  - Runtime Service Observability 单测 153 项全绿（含 `test_mlflow_tracer.py`）
  - Platform API Diagnostics 单测 28 项全绿
  - Platform Web 诊断与 URL 构造单测全绿
- [x] **T09：端到端真实链路验证**
  - 在 Worktree 中全量拉起本地栈（Web 25264, API 27954, Runtime 23714）
  - 调用 `browser-skill` (`bsk`) 打开 Chrome 访问前端，完成登录与发消息测试
  - 验证消息流式生成，轨迹排障页面渲染完整
  - 验证 EvalFlow (端口 9128/5001) 成功接收并生成 `ai-agent-platform-traces` 实验、Trace 详情与 Session 聚合

---

## 阶段五：对话前端全场景 Trace 直达落地（方案一 + 二 + 三）
- [x] **T10：Header 级会话直达（方案一）**
  - 在 `ChatSession.vue` 顶部线程 ID 旁常驻新增【`EvalFlow 追踪 ↗`】徽章，直达 `session_id = '{thread_id}'` 全量链路
- [x] **T11：消息级单轮直达（方案二）**
  - 在 `ChatMessageList.vue` Agent 回复操作栏中新增【`链路 ↗`】按钮，单轮快速直达
- [x] **T12：轨迹 Tab 工具栏直达（方案三）**
  - 在 `TrajectoryView.vue` 工具栏常驻新增【`EvalFlow 链路树 ↗`】徽章
- [x] **T13：真实浏览器全链路一一验证（browser-skill）**
  - 对用户真实对话（Thread `363dafeb-c686-4a95-adb0-3ed744eb9e61`）逐项核验 DOM 与链接，截屏留凭据

---

## 阶段六：安全防御、项目隔离与 Session 详情穿透
- [x] **T14：前端安全防御守护（场景一）**
  - 在 `langfuse-url.ts` 导出 `isTracingEnabled()`，当 `tracingProvider === 'none'` 时隐藏所有追踪按钮与链接
  - `ChatSession.vue`、`ChatMessageList.vue`、`TrajectoryView.vue`、`ObservabilityDashboardPage.vue` 统一加装 `v-if="isTracingActive"` 守护
  - 在 `env.ts` 中支持动态配置覆盖，通过 `browser-skill` 真实模拟 `none` 模式，核验 DOM 中无任何失效 UI，截图 `tracing_none_mode_proven.png` 留存
- [x] **T15：按 Project 划分专属实验（场景二）**
  - 在 `mlflow_tracer.py` 中根据请求或会话上下文的 `project_id` 动态执行 `mlflow.set_experiment(f"project-{project_id}")`
  - 自动创建并绑定项目专属实验，端到端测试验证自动生成了 `project-5a5b7239-43e3-40e6-bba3-e64d96057607`（实验 ID 8）
  - 核验项目物理隔离，截图 `evalflow_project_experiment_8.png` 与 `evalflow_experiment_8_traces.png` 留存
- [x] **T16：超级链接穿透到线程 ID（场景三）**
  - 对齐 MLflow 原生路由，单会话全景详情页路径为 `#/experiments/{experimentId}/chat-sessions/{sessionId}`
  - 更新 `buildMlflowTraceUrl`，点击直接直达该 Thread ID 的会话卡片与完整对话流，截图 `evalflow_chat_sessions_view.png` 留存

---

## 阶段七：会话内原生 Trace ID 精准映射与详情瀑布图秒级直达
- [x] **T17：剔除客户端临时虚拟 ID**
  - 在 `trajectory-adapter.ts` 中过滤 `lc_run--` 开头的 LangChain 客户端内部 ID，防止伪 ID 污染
- [x] **T18：会话级原生 Trace ID 动态映射**
  - 接入 `fetchSessionTraces` API，根据 Experiment ID 和 Thread ID 异步拉取真实的 `tr-xxxx` Trace ID 序列
  - 动态注入到 `TrajectoryView.vue`、`TrajectoryInspector.vue` 和 `TrajectoryLedger.vue`
- [x] **T19：单条 Trace 详情抽屉秒开**
  - 详情面板 Trace ID 点击「直达 ↗」直接定位到单条 Trace 详细页面（`#/experiments/{expId}/traces/{tr-xxxx}`），展示完整 Span 树与调用参数
- [x] **T20：端到端真实浏览器验证与全量回归**
  - 使用 `browser-skill` 真实截屏证明：`trajectory_with_real_trace_id.png` 与 `trace_detail_page_verified_live.png`
  - 前端 161 套测试、979 个用例 100% 绿色通过，TypeScript 类型检查零报错
