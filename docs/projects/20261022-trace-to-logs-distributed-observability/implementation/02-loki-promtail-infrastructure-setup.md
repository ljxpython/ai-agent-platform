# Loki + Promtail 极简日志编排与 Grafana Derived Fields 联动

## 改动时间
2026-10-22

## 相关任务
- Task 2.1: 准备 Loki 与 Promtail 配置文件
- Task 2.2: 在 Grafana 挂载 Loki 数据源并配置 Derived Fields

## 改动文件
- `deploy/observability/loki.yml`
- `deploy/observability/promtail.yml`
- `deploy/observability/provisioning/datasources/loki.yml`
- `deploy/observability/docker-compose.yml`

## 具体改动

### 1. 部署单节点极简 Loki 配置
- **位置：** `deploy/observability/loki.yml`
- **核心选型：** 单机单进程 TSDB 索引 + 本地文件系统对象存储，7 天自动保留与压缩（`retention_period: 7d`）。
- **资源限制：** 内存限制 120MB，不依赖 Consul/Etcd/S3 等任何外部重型组件。

### 2. 部署 Promtail 自动提取 Trace 标签
- **位置：** `deploy/observability/promtail.yml`
- **采集目标：** 自动挂载 Host 的 Systemd Journal (`agent-platform-api.service`, `agent-runtime-service.service`) 与应用日志。
- **动态标签注入：** Pipeline Stage 自动以正则 `(?P<trace_id>[0-9a-f]{32})` 抓取日志中的 32 位 Hex ID 并作为 Loki 标签索引。

### 3. Grafana 挂载 Loki 与 Derived Fields 衍生字段联动
- **位置：** `deploy/observability/provisioning/datasources/loki.yml`
- **核心联动：** 当在 Grafana 中检索任何微服务日志时，日志行内出现的 `trace_id` 自动渲染为高亮蓝色外链按钮“Open Trace in Langfuse”，实现点击日志直接打开调用树。

## 验证结果
1. `docker compose config` 语法验证：**VALID_COMPOSE**。
2. 资源硬限：Loki 限制 120MB，Promtail 限制 40MB，完全符合极轻量标准。
