# 分布式全链路追踪与日志关联可观测性工程 - 任务拆分

## 任务执行原则
- 所有代码改动与本地测试在专属 Worktree 内闭环验证；
- 遵循 Fail-Soft 原则：任何链路追踪或日志打标异常，绝不向上抛出阻断业务；
- 严格控制资源上限：新增组件 Loki + Promtail 生产内存增量合计控制在 100MB 以内。

---

## Phase 1: 协议标准化与结构化日志对齐 (本地代码层)

### Task 1.1: W3C TraceContext 标准透传实现
- **改动内容：**
  - 在 `Platform API` 的 `request_context.py` 中，生成标准的 W3C `traceparent`（`00-{trace_id}-{span_id}-01`）；
  - 在调用下游 `Runtime Service` 的 HTTP/SSE client 请求中，通过请求头自动注入 `traceparent`、`x-request-id`、`x-trace-id`；
  - 在 `Runtime Service` 的中间件中，解析 incoming `traceparent`，并建立父子 Span 关系与响应头回显。
- **代码位置：**
  - `apps/platform-api/src/platform_api/core/context/models.py`
  - `apps/platform-api/src/platform_api/core/context/runtime.py`
  - `apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py`
  - `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`
  - `apps/runtime-service/src/runtime_service/observability/context.py`
  - `apps/runtime-service/src/runtime_service/webapp.py`
- **预期结果：** Platform API 发出的跨服务请求携带符合规范的 `traceparent`，Runtime Service 能正确继承该 TraceID 并派生子 SpanID。
- **验证项：** `uv run pytest apps/platform-api/tests/test_trace_propagation.py apps/runtime-service/tests/test_trace_propagation.py` → ✅ 9 项单测全部通过 (100% 绿灯)
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/01-w3c-traceparent-and-structured-logging.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（跳过，待整个阶段 1 聚合完成）
  - [ ] docs/FEATURES.md 已更新（跳过，内部治理改动）
  - [ ] docs/CHANGELOG.md 已更新（跳过，治理与协议改动）

### Task 1.2: API 与 Runtime 结构化日志打标对齐
- **改动内容：**
  - 改造两端服务的 `logging.py`，实现 `PlatformTraceLogFilter` 与 `RuntimeTraceLogFilter`，强制所有日志输出携带 `[service] [trace_id] [span_id]` 标识；
  - 强绑定 `trace_id_for` 优先继承 `platform_trace_id` 与 HTTP 上下文，彻底消灭 TraceID 割裂。
- **代码位置：**
  - `apps/platform-api/src/platform_api/core/observability/logging.py`
  - `apps/runtime-service/src/runtime_service/observability/logging.py`
  - `apps/runtime-service/src/runtime_service/observability/diagnostics.py`
- **预期结果：** 日志单行输出严格包含统一标识，便于正则和 Promtail 提取。
- **验证项：** 运行单元测试验证 LogRecord 字段注入与 format_log_line 格式 → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/01-w3c-traceparent-and-structured-logging.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（跳过，待整个阶段 1 聚合完成）
  - [ ] docs/FEATURES.md 已更新（跳过，内部治理改动）
  - [ ] docs/CHANGELOG.md 已更新（跳过，治理与协议改动）

---

## Phase 2: 基础设施套件（Loki + Promtail 极简编排）

### Task 2.1: 准备 Loki 与 Promtail 配置文件
- **改动内容：**
  - 编写极简的 `loki.yml` 配置（单机 TSDB 索引 + 本地文件对象存储，配置 7 天保留策略）；
  - 编写 `promtail.yml` 配置（自动读取 Systemd journald 与应用日志，以正则 `(?P<trace_id>[0-9a-f]{32})` 提取标签并推往 Loki）；
  - 更新 `deploy/observability/docker-compose.yml`，将 Loki 与 Promtail 加入编排。
- **代码位置：**
  - `deploy/observability/loki.yml`
  - `deploy/observability/promtail.yml`
  - `deploy/observability/docker-compose.yml`
- **预期结果：** 单条 `docker compose up -d` 命令即可一键拉起 Prometheus、Grafana、Loki、Promtail 四位一体监控矩阵。
- **验证项：** `docker compose config` 验证语法 100% 正确 → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/02-loki-promtail-infrastructure-setup.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 2.2: 在 Grafana 挂载 Loki 数据源并配置 Derived Fields
- **改动内容：**
  - 在 `deploy/observability/provisioning/datasources/` 下新增 `loki.yml` 数据源定义；
  - 配置 `derivedFields`：当日志行中出现 `trace_id` 时，自动将其渲染为高亮蓝色外链按钮“Open Trace in Langfuse”，实现日志秒跳追踪树。
- **代码位置：**
  - `deploy/observability/provisioning/datasources/loki.yml`
- **预期结果：** Grafana 自动加载 Loki 数据源，在 Explore 页面查日志时，每行日志的 trace_id 都可以直接点击跳转。
- **验证项：** 配置文件生成且结构符合 Grafana Datasource V1 契约 → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/02-loki-promtail-infrastructure-setup.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## Phase 3: 诊断闭环与前端穿透（Trace-to-Logs 联动）

### Task 3.1: Platform Web 诊断弹窗与审计日志增加一键查日志跳转
- **改动内容：**
  - 在 `DiagnosticDetailModal.vue`（错误排障弹窗）中，增加【微服务全链路日志】按钮，直接带 `trace_id` 跳转至内嵌 Grafana 的 Explore 界面；
  - 升级 `ObservabilityDashboardPage.vue` 为全链路可观测诊断中心，支持根据 URL 或顶部输入框中的 `traceId` 自动切换 Loki 跨服务日志 Explore 视角与 Langfuse 链路外链。
- **代码位置：**
  - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
  - `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`
- **预期结果：** 运维人员在前端界面遇到报错或审计记录，点击按钮即可一键在内嵌大盘中查看该 `trace_id` 对应的全量跨服务微服务日志。
- **验证项：** `ObservabilityDashboardPage.spec.ts` 4 项测试通过，`pnpm typecheck` 0 报错 → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-frontend-trace-to-logs-explorer.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## Phase 4: 全量回归与生产验证

### Task 4.1: 生产主机 sshmy1 部署与联调验证
- **改动内容：** 在云主机 `sshmy1` 平滑更新 `docker-compose.yml`，启动 Loki 与 Promtail，同步更新 Platform API 核心文件并平滑重启。
- **验证项：** `docker stats` 实测四容器常驻总内存仅 **186.47 MiB**，Loki 成功索引 `job`、`service`、`trace_id` 标签 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/04-production-deployment-and-verification.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 4.2: 端到端故障注入与全链路穿透验收
- **改动内容：** 在生产主机发送真实请求验证 Header（`00-f54556801b704f359567f54c7f23ead1-da093fbc7ceb4a54-01`），验证前端诊断中心根据 `traceId` 动态切换 Explore 视角并带出微服务日志。
- **验证项：** 生产真实端到端验证通过，落于 `verification.md` → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/04-production-deployment-and-verification.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## Phase 5: 毫秒级直出架构重构（方案 A：自研轻量代理 API + 前端原生时间轴）

### Task 5.1: 后端 Loki 轻量代理检索 API 实现与鉴权放行
- **改动内容：**
  - 在 `platform-api` 增加 Loki 代理查询服务，异步检索 LogQL `{job=~"systemd-journal|app-file-logs"} |= "{trace_id}"`；
  - 自动提炼微服务执行时序、Span 标签、结构化元数据与可读摘要（Fail-soft 容灾）；
  - 暴露 `GET /api/v1/observability/traces/{trace_id}/logs`，并在 `auth_context.py` 中配置免密放行。
- **代码位置：**
  - `apps/platform-api/src/platform_api/config.py`
  - `apps/platform-api/src/platform_api/modules/observability/`
  - `apps/platform-api/src/platform_api/entrypoints/http/middleware/auth_context.py`
  - `apps/platform-api/src/platform_api/entrypoints/http/router.py`
  - `apps/platform-api/tests/test_observability_api.py`
- **验证项：** 后端单元测试 2 项全部通过，生产环境 curl 请求仅耗时 46ms → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/05-native-timeline-and-loki-proxy-api.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 5.2: 前端原生毫秒级极速时间轴组件与生产环境验证
- **改动内容：**
  - 彻底剔除 `iframe` 容器与 5MB 前端加载开销，改用 Vue 原生微服务时序时间轴列表；
  - 接入 `platformHttpClient` 发起代理检索，支持错误提示卡片、一键载入生产样例、微服务 Tag、全量包复制与 JSON 详情展开；
  - 保留外部 Grafana Explore 外链供 SRE 逃生；
  - 同步打包产物至生产环境 Nginx，通过 Playwright 完成真实端到端秒开与渲染验证。
- **代码位置：**
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue`
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.spec.ts`
- **验证项：** 前端单测 7 项全过，`vue-tsc` 0 报错，生产打包成功（gzip 仅 5KB），Playwright 实测秒开截图留痕 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/05-native-timeline-and-loki-proxy-api.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## Phase 6: 工业级可视化升级与 Langfuse 多租户 URL 兼容

### Task 6.1: Langfuse 动态 URL 构造器与环境变量集成
- **改动内容：**
  - 扩充 `apps/platform-web/src/config/env.ts` Zod schema，支持 `VITE_LANGFUSE_BASE_URL`、`VITE_LANGFUSE_PROJECT_ID`、`VITE_LANGFUSE_TRACE_URL_TEMPLATE` 环境变量；
  - 编写 `buildLangfuseTraceUrl` 工具函数，支持三级自适应路由（自定义模板 > 项目级精准搜索过滤直达 > 全局兜底）；
  - 在 `DiagnosticDetailModal.vue` 与 `TraceDiagnosticsPage.vue` 统一接入；
  - 覆盖高密度单测（含合法/非法模板兼容性验证）。
- **代码位置：**
  - `apps/platform-web/src/config/env.ts`
  - `apps/platform-web/src/services/observability/langfuse-url.ts`
  - `apps/platform-web/src/services/observability/langfuse-url.spec.ts`
  - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
  - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.spec.ts`
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue`
- **预期结果：** 点击链路追踪跳转按钮直达项目精准过滤视图，彻底消灭 Langfuse Cloud 404 报错。
- **验证项：** `langfuse-url.spec.ts` 4 passed，`DiagnosticDetailModal.spec.ts` 3 passed → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-23 → 见 `implementation/06-industrial-observability-visualization-and-langfuse-integration.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 6.2: 自回声日志过滤与耗时字段提取
- **改动内容：**
  - 在 `platform-api` 代理服务中，LogQL 追加 `!~ "loki/api/v1/query"` 过滤；
  - 在代码处理层拦截并丢弃自身访问 Loki 的 `httpx` 查询日志，防止循环回声污染；
  - 提取并计算单步 `duration_ms` 字段注入响应模型。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/observability/service.py`
  - `apps/platform-api/src/platform_api/modules/observability/models.py`
  - `apps/platform-api/tests/test_observability_api.py`
- **预期结果：** 排除 Loki 自回声日志，准确透出各步执行耗时。
- **验证项：** `pytest tests/test_observability_api.py` 2 passed → ✅ 通过
- **预计：** 0.2 天
- **状态：** `[x]` 已完成 2026-10-23 → 见 `implementation/06-industrial-observability-visualization-and-langfuse-integration.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 6.3: 大厂排障大屏升级（甘特瀑布流 + 毫秒瞬时搜索 + 双 Tab 对比）
- **改动内容：**
  - 实现四联指标概览 Ribbon（耗时/日志总数/微服务拓扑/级别）；
  - 实现节点耗时瀑布流甘特条（相对总耗时占比 + >500ms 慢调用警醒）；
  - 实现纯前端瞬时过滤（关键词、级别、服务切片）；
  - 实现同页双 Tab 切换对比（极速时间轴 vs Grafana Explore）；
  - 适配标准 `pw-card` / `pw-panel`，解决界面死黑问题。
- **代码位置：**
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue`
  - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.spec.ts`
- **预期结果：** 界面视觉符合平台标准，具备大厂排障全景洞察能力。
- **验证项：** `TraceDiagnosticsPage.spec.ts` 7 passed，`vue-tsc` 0 报错，Playwright 端到端验证通过 → ✅ 通过
- **预计：** 0.5 天
- **状态：** `[x]` 已完成 2026-10-23 → 见 `implementation/06-industrial-observability-visualization-and-langfuse-integration.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## 进度追踪
- [x] Phase 1: 协议标准化与结构化日志对齐完成
- [x] Phase 2: 基础设施套件 (Loki + Promtail) 编排完成
- [x] Phase 3: 诊断闭环与前端穿透完成
- [x] Phase 4: 全量回归与生产验证通过
- [x] Phase 5: 毫秒级直出架构重构（方案 A）完成
- [x] Phase 6: 工业级可视化升级与 Langfuse 多租户 URL 兼容完成
