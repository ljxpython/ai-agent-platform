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

## 进度追踪
- [x] Phase 1: 协议标准化与结构化日志对齐完成
- [x] Phase 2: 基础设施套件 (Loki + Promtail) 编排完成
- [x] Phase 3: 诊断闭环与前端穿透完成
- [x] Phase 4: 全量回归与生产验证通过
