# 工业级可观测性与指标大盘架构工程 (Industrial Observability & Metrics Dashboard)

## 项目概述
- **时间：** 2026-10-22
- **目标：** 建立生产级可观测体系，实行“双轨制”策略（Langfuse 负责 Agent/LLM 行为深度追踪，Prometheus + Grafana 负责高并发/系统心跳/宏观指标）；彻底铲除 Platform API 内部基于内存锁的玩具级计数器，向外暴露标准 `/metrics` 规范接口；打通自前端状态栏、网关审计至 Runtime/Langfuse 的端到端 `trace_id` 穿透能力；在云主机 `sshmy1` 规划落地轻量级时序监控与可视化大盘。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** 已完成（`done`；全栈代码门禁 100% 绿灯，远端生产主机 `sshmy1` 实装部署，Prometheus + Grafana 常驻内存仅 70.09MB，双 Targets 100% UP，Grafana 大盘开箱即用生效）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划](verification.md)
- [现行链路追踪契约](../../standards/trace-propagation.md)

## 改动范围
- **影响服务：**
  - `platform-api`：淘汰 `core/observability/metrics.py` 内存锁计数器，引入标准 Prometheus/OpenMetrics 指标收集与 `/metrics` 端点；对齐全局请求耗时与错误直方图。
  - `runtime-service`：挂载指标收集中间件，暴露 `/metrics` 端点，采集 LangGraph 执行步数、大模型延迟、沙箱容器池水位与死循环触发统计；确保 `with_langfuse_tracing` 强绑定 `platform_trace_id`。
  - `platform-web`：实装方案 B 内嵌大盘 `ObservabilityDashboardPage.vue`，支持 Kiosk 沉浸模式、深浅色模式自动联动、全屏看板及一键跳转原生控制台，左侧「平台管理」挂载【指标大盘】菜单项，系统探测页顶部增设直达快捷入口。
  - `运维与部署（sshmy1 / sshmy2）`：在 `sshmy1` 规划轻量级 Prometheus（时序采集）与 Grafana（大盘呈现）守护进程配置，资源预算控制在 500MB RAM 以内。
- **改动级别：** 治理改动
- **所属专属 Worktree：** `.worktree/ai-agent-platform-observability`（分支：`feat/industrial-observability-explore`）

## 核心设计决策
1. **指标与追踪职责双轨分离（Langfuse vs Prometheus）**：
   - 绝不搞“大包大揽”，各司其职。
   - Langfuse 专司大模型、Prompt、LangGraph Node、Tool Call 拓扑树与 Token 成本明细，作为单次 Run 执行细节与排障的第一事实源。
   - Prometheus 专司系统的生命体征监控（QPS、P99 延时、活跃 Worker 并发数、HTTP 状态码分布、Docker 沙箱存活池水位）与 SRE 秒级告警。
2. **拒绝加塞重型中间件（No Heavy OTel Collector）**：
   - 在两台服务器架构下，坚决不上重型的 OpenTelemetry Collector 代理中继，杜绝过度设计。
   - 代码层采用 SDK 直出模式（Direct Pull Mode），通过 Python 标准库直接在 FastAPI 应用上暴露 `/metrics`，零额外进程开销。
3. **Trace 穿透与安全隔离原则**：
   - 沿用 `docs/standards/trace-propagation.md` 规范，前端 `x-request-id` = 网关 `platform_trace_id` = Langfuse `trace_id`。
   - 实现运维/研发输入一个 `trace_id`，即可串联“网关审计日志 + Runtime 服务日志 + Langfuse 深度执行树”的完整上下文。
