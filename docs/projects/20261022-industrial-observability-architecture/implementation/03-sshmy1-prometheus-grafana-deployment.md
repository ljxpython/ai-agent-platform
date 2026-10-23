# 远端服务器 sshmy1 生产级 Prometheus + Grafana 部署与联调

## 改动时间
2026-10-22

## 相关任务
- Task 2.1: 准备本地与远端通用 Compose 配置
- Task 2.2: 制作精选 Grafana Dashboard 模板
- Task 4.1: 在 sshmy1 部署轻量级 Prometheus 与 Grafana
- Task 4.2: 配置安全访问路径与端口联通性
- Task 4.3: 真实环境指标抓取联调与端到端回归验收

## 改动与部署内容

### 1. 部署架构与资源控制
- **宿主机：** `sshmy1` (49.233.222.54)
- **部署目录：** `/opt/observability/`
- **容器与内存限制：**
  - `platform-prometheus`: 镜像 `prom/prometheus:v2.51.0`，内存上限 250MB，实测常驻内存 **19.59 MiB** (CPU: 0.00%)。
  - `platform-grafana`: 镜像 `grafana/grafana-oss:10.4.0`，内存上限 200MB，实测常驻内存 **50.5 MiB** (CPU: 0.50%)。
  - **总内存增量仅 70.09 MiB**（远低于 500MB 预算上限）。

### 2. 时序拉取与数据源自动供应
- **抓取配置：** `/opt/observability/prometheus.yml` 采用 `network_mode: host`。
  - Target 1: `127.0.0.1:2142/metrics` (`platform-api`) -> **Status: UP**
  - Target 2: `127.0.0.1:8123/metrics` (`runtime-service`) -> **Status: UP**
- **Datasource 自动发现：** 通过 `provisioning/datasources/prometheus.yml` 自动挂载 `http://127.0.0.1:9090`，无需手工点界面配置。

### 3. 开箱即用仪表盘预置
- **仪表盘文件：** `/opt/observability/dashboards/platform-overview.json`
- **仪表盘名称：** `AI Agent Platform - 工业级基础设施总览`（UID: `ai-platform-overview`）
- **覆盖面板：**
  1. HTTP 实时吞吐量 (QPS)
  2. 网关响应延迟分位 (P95 / P99)
  3. HTTP 状态码分布 (2xx, 4xx, 5xx)
  4. 并发协程与沙箱容器水位
  5. PostgreSQL 连接池状态 (Pool Size, Checked In/Out)
  6. Redis 队列深度与 Agent 运行完成态

### 4. Platform API 热升级与权限豁免
- 在 `sshmy1` 的 Platform API 虚拟环境中安装 `prometheus-client==0.26.0`。
- 同步 metrics 收集器与无鉴权端点 (`GET /metrics` 与 `GET /_system/prometheus`)。
- 重启 `agent-platform-api.service`，实测 2 Workers 并发平滑重载。

## 验证结果
1. `http://49.233.222.54:3000/api/health` → 返回 `200 OK` (`database: ok, version: 10.4.0`)
2. `http://127.0.0.1:9090/api/v1/targets` → `platform-api` 与 `runtime-service` 双目标 100% `health: up`
3. 宿主机可用内存剩余 1790MB，系统 Load Average 0.30，系统运行极其平稳。
