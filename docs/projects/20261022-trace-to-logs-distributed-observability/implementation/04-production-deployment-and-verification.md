# 生产环境 Loki + Promtail 实装部署与全链路穿透验收

## 改动时间
2026-10-22

## 相关任务
- Task 4.1: 生产主机 sshmy1 部署与联调验证
- Task 4.2: 端到端故障注入与全链路穿透验收

## 部署环境
- **生产主机：** `sshmy1` (49.233.222.54)
- **部署目录：** `/opt/observability/`
- **组件阵容：** Prometheus 2.51 + Grafana 10.4 + Loki 2.9 + Promtail 2.9

## 实操记录

### 1. 四位一体容器编排启动
- 执行命令：`docker compose up -d`
- 容器状态：
  - `platform-prometheus`: 37.04 MiB (CPU: 0.00%)
  - `platform-grafana`: 45.14 MiB (CPU: 0.15%)
  - `platform-loki`: 65.96 MiB (CPU: 0.17%)
  - `platform-promtail`: 38.33 MiB (CPU: 0.52%)
- **四容器总常驻内存仅 186.47 MiB**，远低于 500MB 预算上限。

### 2. 日志流与数据源连通性
- Loki 端点 `http://127.0.0.1:3100/loki/api/v1/labels` 响应：
  `{"status":"success","data":["job","service","trace_id"]}`。
- Promtail 目标状态：`systemd-journal (1/1 ready)`，实时将 `agent-platform-api` 与 `agent-runtime-service` 的日志提取 Trace 标签推往 Loki。
- Grafana API 数据源列表：Loki 数据源已自动 Provisioning 加载完成。

### 3. W3C traceparent 协议验证
- 针对生产 Platform API (`127.0.0.1:2142`) 发起真实请求：
  响应 Header 严格包含：
  - `traceparent`: `00-f54556801b704f359567f54c7f23ead1-da093fbc7ceb4a54-01`
  - `x-trace-id`: `f54556801b704f359567f54c7f23ead1`
  - `x-request-id`: `f54556801b704f359567f54c7f23ead1`

### 4. Trace-to-Logs 穿透与前端闭环
- 在前端内嵌大盘页面访问 `/workspace/observability?traceId=f54556801b704f359567f54c7f23ead1`，系统自动进入诊断模式，内嵌的 Grafana Explore 自动带出 Loki 聚合日志流，并提供“在 Langfuse 查看大模型执行树”跳转。

## 验收结论
✅ **Phase 1 ~ Phase 4 全部达成并闭环验收通过！**
