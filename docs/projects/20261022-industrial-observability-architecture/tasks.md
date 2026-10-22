# 工业级可观测性与指标大盘 - 任务拆分

## 任务执行原则
- 所有改动先在专属 Worktree（`feat/industrial-observability-explore`）内完成开发与单测闭环。
- 绝不在探索阶段影响主工作区运行中的开发环境。
- 遵循 Fail-Soft 原则：可观测性代码的任何报错严禁抛出到业务主链路。

---

## 阶段 1：指标源头改造（Worktree 本地代码层）

### Task 1.1: Platform API 指标基础设施改造
- **改动内容：** 淘汰原有 `threading.Lock` + `defaultdict` 玩具实现，引入标准 `prometheus_client` 收集器（Counter/Histogram/Gauge），增加路径动态 ID 正则收敛（防止基数爆炸），保留 `snapshot_http_metrics` 兼容已有管理 JSON，并在 `GET /metrics` 与 `GET /_system/prometheus` 暴露 OpenMetrics 纯文本端点。
- **代码位置：**
  - `apps/platform-api/src/platform_api/core/observability/metrics.py` → `MetricsRegistry`
  - `apps/platform-api/src/platform_api/entrypoints/http/router.py` → `root_metrics()`
  - `apps/platform-api/src/platform_api/entrypoints/http/system.py` → `prometheus_metrics()`
  - `apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py`
  - `apps/platform-api/src/platform_api/entrypoints/http/middleware/auth_context.py`
- **预期结果：** `GET /metrics` 吐出标准 OpenMetrics 格式；既有 `/_system/metrics` JSON 依然正常；耗时 < 0.05ms。
- **验证项：** `uv run pytest tests/test_prometheus_metrics.py tests/test_phase4_observability_and_service_accounts.py` → ✅ 9 项全过（耗时 5.99s，微基准测试单次指标记录 < 0.005ms）
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/01-platform-api-prometheus-metrics.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（9 项单测 100% 绿灯，基准测试通过）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（已作为活跃治理项目纳入）
  - [ ] docs/FEATURES.md 已更新（跳过，待整个阶段 1 聚合完成）
  - [ ] docs/CHANGELOG.md 已更新（跳过，当前在探索性 Worktree 中）

### Task 1.2: Runtime Service 指标基础设施改造
- **改动内容：** 创建 `RuntimeMetricsRegistry`，定义 Agent Run 总数与执行耗时直方图、模型调用成功/失败计数、循环保护触发计数、沙箱活跃容器水位 Gauge；在 `langfuse.py` 的回调与诊断事件中挂接指标采集，并在 `webapp.py` 暴露无鉴权 `GET /metrics` 端点。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/observability/metrics.py` → `RuntimeMetricsRegistry`
  - `apps/runtime-service/src/runtime_service/observability/langfuse.py` → `_finish()`, `on_llm_end()`, `record_diagnostic_event()`
  - `apps/runtime-service/src/runtime_service/webapp.py` → `@app.get("/metrics")`
- **预期结果：** `GET /metrics` 返回标准 OpenMetrics 指标流；所有记录均为 Fail-Soft；Langfuse 未启用时指标依然正常工作。
- **验证项：** `uv run pytest tests/test_prometheus_metrics.py tests/observability/test_langfuse.py` → ✅ 33 项全过（耗时 13.35s）
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/02-runtime-service-prometheus-metrics.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（33 项单测 100% 绿灯）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（已作为活跃治理项目纳入）
  - [ ] docs/FEATURES.md 已更新（跳过，待整个阶段 1 聚合完成）
  - [ ] docs/CHANGELOG.md 已更新（跳过，当前在探索性 Worktree 中）

### Task 1.3: 单元测试覆盖与性能压力基准
- **改动内容：** 针对 `platform-api` 与 `runtime-service` 分别编写独立的 Prometheus 指标单测与性能微基准测试；验证 1000 次高频并发指标记录开销；验证极端非法类型输入下的 Fail-Soft 熔断。
- **代码位置：**
  - `apps/platform-api/tests/test_prometheus_metrics.py`
  - `apps/runtime-service/tests/test_prometheus_metrics.py`
- **预期结果：** 所有指标端点正常响应；单次指标记录耗时 < 0.05ms；Fail-Soft 100% 捕获异常不中断业务。
- **验证项：**
  - Platform API: 9 项测试通过，单次采集均值 < 0.005ms → ✅ 通过
  - Runtime Service: 8 项测试通过，单次采集均值 < 0.005ms → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/01-platform-api-prometheus-metrics.md` 与 `02-runtime-service-prometheus-metrics.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（微基准耗时 < 0.005ms，断言全部通过）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（已作为活跃治理项目纳入）
  - [ ] docs/FEATURES.md 已更新（跳过，待整个阶段 1 聚合完成）
  - [ ] docs/CHANGELOG.md 已更新（跳过，当前在探索性 Worktree 中）

---

## 阶段 2：开箱即用套件（Docker Compose 与大盘模板）

### Task 2.1: 准备通用 Compose 配置
- **改动内容：** 编写适用于本地与远端部署的极简编排文件（Prometheus 2.51 + Grafana 10.4），采用 `network_mode: host` 直接打通本地与回环端口抓取，分别配置 250MB / 200MB 内存上限保护。
- **代码位置：** `deploy/observability/docker-compose.yml`, `deploy/observability/prometheus.yml`, `deploy/observability/provisioning/`
- **预期结果：** 单条命令即拉起双容器，自动加载配置与数据源。
- **验证项：** 远端 `sshmy1` 实测 `docker compose up -d` 成功启动双容器 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-sshmy1-prometheus-grafana-deployment.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 2.2: 制作精选 Grafana Dashboard 模板
- **改动内容：** 制作并导出包含 QPS、P95/P99 延迟分位、HTTP 状态码堆叠、并发活跃请求、沙箱活跃容器水位、PostgreSQL 连接池容量与 Redis 运行队列深度的工业级大盘模板。
- **代码位置：** `deploy/observability/dashboards/platform-overview.json`
- **预期结果：** Grafana 启动后自动导入该大盘，无需人工配置。
- **验证项：** Grafana 自动加载并注册至 `AI Platform` 目录，UID `ai-platform-overview` 成功渲染 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-sshmy1-prometheus-grafana-deployment.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

---

## 阶段 3：全链路 Trace 穿透加固（端到端对齐）

- [x] **Task 3.1: 核验前端 -> 网关 -> Runtime -> Langfuse 凭据链**
  - **核对位置：**
    - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
    - `apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py`
    - `apps/runtime-service/src/runtime_service/observability/langfuse.py`
  - **完成情况：** 平台统一沿用 32 位 Hex `request_id` / `platform_trace_id` 契约，响应 Header 回显 `x-request-id` 与 `x-trace-id`；前端排障模态窗直接展示并提供 Langfuse 外链；Runtime 强绑定 root trace。

---

## 阶段 4：远端服务器 `sshmy1` 落地实施（已获明确批准）

### Task 4.1: 在 `sshmy1` 部署轻量级 Prometheus 与 Grafana
- **改动内容：** 在 `sshmy1` 建立 `/opt/observability/`，通过 Docker Compose 启动 Prometheus (19.59MB) 与 Grafana (50.5MB)，总内存增量仅 70.09MB。
- **代码位置：** `sshmy1:/opt/observability/`
- **预期结果：** 容器稳定常驻，CPU 占用 < 1%，内存 < 500MB。
- **验证项：** `docker stats --no-stream` 实测总内存 70.09 MiB (Prometheus: 19.59MB, Grafana: 50.5MB) → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-sshmy1-prometheus-grafana-deployment.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 4.2: 配置安全访问路径与端口联通性
- **改动内容：** Prometheus 监听 `127.0.0.1:9090`（不公网暴露，安全回环）；Grafana 监听 `0.0.0.0:3000`（防火墙已开通 3000，设置强管理员口令）。
- **代码位置：** `sshmy1` iptables & docker-compose
- **预期结果：** 公网直达 Grafana 控制台，Prometheus 仅限内网访问。
- **验证项：** 公网 `http://49.233.222.54:3000/api/health` 实测返回 200 OK → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-sshmy1-prometheus-grafana-deployment.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 4.3: 真实环境指标抓取联调与端到端回归验收
- **改动内容：** 同步 Platform API 核心指标更新至 `sshmy1`，平滑重启 `agent-platform-api.service`，在 Prometheus 抓取 `platform-api` (2142) 与 `runtime-service` (8123)。
- **代码位置：** `sshmy1:/opt/ai-agent-platform/apps/platform-api/`
- **预期结果：** 两个抓取目标在 Prometheus 均处于 `UP` 状态；大盘实时渲染数据。
- **验证项：** `http://127.0.0.1:9090/api/v1/targets` 双目标 100% `health: up` → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/03-sshmy1-prometheus-grafana-deployment.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

---

## 阶段 5：前端无缝内嵌工业指标大盘（方案 B）

### Task 5.1: 远端 Grafana 安全嵌入与免密配置
- **改动内容：** 修改 `deploy/observability/docker-compose.yml`，为 Grafana 增加 `GF_SECURITY_ALLOW_EMBEDDING=true`、`GF_AUTH_ANONYMOUS_ENABLED=true`、`GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer`；同步远端 `sshmy1` 并平滑热重启容器。
- **预期结果：** 容器允许跨域 iframe 嵌入，匿名只读，且无登录阻断。
- **验证项：** 远端 `curl -sI 'http://127.0.0.1:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1&kiosk'` 返回 `200 OK`，`X-Frame-Options: deny` 响应头已清除。
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/04-platform-web-grafana-embedding.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 5.2: Platform Web 指标大盘内嵌组件与导航
- **改动内容：**
  - 新增 `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`，实现带 `kiosk` 沉浸模式、跟随暗黑/浅色模式切换、加载骨架遮罩、刷新、全屏与独立新窗口直达功能。
  - 在 `apps/platform-web/src/router/routes.ts` 注册 `/workspace/observability` 路由，并在「平台管理」左侧菜单栏添加【指标大盘】导航项。
  - 在 `SystemGovernancePage.vue`（系统探测）顶部添加快速直达「指标大盘」的快捷按钮。
- **预期结果：** 用户在 Web 平台内部即可直接查看 Grafana 工业级指标大盘，视觉一致无割裂。
- **验证项：**
  - `pnpm typecheck` 0 报错；
  - `ObservabilityDashboardPage.spec.ts` 3 项测试 100% 绿灯；
  - 前端全量单测 906 项 100% 绿灯；
  - 本地 Web（`http://127.0.0.1:26631/workspace/observability`）返回 200 OK。
- **状态：** `[x]` 已完成 2026-10-22 → 见 `implementation/04-platform-web-grafana-embedding.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
