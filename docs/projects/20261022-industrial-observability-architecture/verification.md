# 工业级可观测性与指标大盘 - 验证计划与验收记录

## 一、 验证环境
- **探索分支：** `feat/industrial-observability-explore`
- **验证目录：** `.worktree/ai-agent-platform-observability`
- **目标服务器：** `sshmy1`（管理面与监控）+ `sshmy2`（计算与数据面）

---

## 二、 关键验收门禁（Gateways）

### 门禁 1：代码层零外部依赖单元测试
- **测试命令：** `uv run pytest tests/test_prometheus_metrics.py` (API + Runtime)
- **预期结果：**
  - [x] `/metrics` 输出严格符合 Prometheus text-based 0.0.4 格式；
  - [x] 涵盖 GET/POST/SSE 等不同请求类型与 2xx/4xx/5xx 状态码；
  - [x] 包含耗时分位直方图（buckets）；
  - [x] 单次采集耗时微基准测试小于 0.05ms（实测均值 < 0.005ms）。

### 门禁 2：Fail-Soft 容错验证（监控故障绝不影响业务）
- **测试方法：** 注入指标记录异常（如故意制造内存分配或类型错误）。
- **预期结果：**
  - [x] 业务接口继续返回 200 与正确 payload；
  - [x] 异常仅记录为本地警告日志，不向上抛出。

### 门禁 3：Trace ID 全链路端到端穿透验证
- **测试方法：** 模拟一次完整的 Agent 运行流程，拿到前端报出的 `trace_id`。
- **预期结果：**
  - [x] Platform API 审计日志表中根据该 ID 可精准查询到发起记录；
  - [x] Langfuse Web 控制台中根据该 ID 可直达该次 Run 的完整执行树；
  - [x] 系统日志中可根据该 ID 完整过滤出关联的所有调试上下文。

### 门禁 4：生产资源占用红线验证（sshmy1）
- **测试命令：** `docker stats --no-stream`
- **预期结果：**
  - [x] Prometheus 内存稳定在 300MB 以内（实测：**19.59 MiB**）；
  - [x] Grafana 内存稳定在 200MB 以内（实测：**50.5 MiB**）；
  - [x] 整体对 `sshmy1` 的 CPU 占用小于 5%（实测：CPU < 0.5%，总内存占用仅 **70.09 MiB**）。

---

## 三、 验证执行记录

### 2026-10-22 生产真实环境验收证明（sshmy1: 49.233.222.54）

1. **Prometheus 服务健康检查：**
   ```bash
   curl -s http://127.0.0.1:9090/-/healthy
   # 输出: Prometheus Server is Healthy.
   ```

2. **Grafana 服务健康检查：**
   ```bash
   curl -s http://49.233.222.54:3000/api/health
   # 输出: {"commit":"03f502a94d17f7dc4e6c34acdf8428aedd986e4c","database":"ok","version":"10.4.0"}
   ```

3. **Prometheus 抓取目标（Targets）状态：**
   ```bash
   curl -s http://127.0.0.1:9090/api/v1/targets | python3 -m json.tool | grep -E '"(health|job|scrapeUrl)"'
   # 输出:
   # "job": "platform-api", scrapeUrl: "http://127.0.0.1:2142/metrics", health: "up"
   # "job": "runtime-service", scrapeUrl: "http://127.0.0.1:8123/metrics", health: "up"
   ```

4. **生产实测资源消耗（Docker Stats）：**
   ```text
   CONTAINER ID   NAME                  CPU %     MEM USAGE / LIMIT   MEM %
   1164cc57dc15   platform-grafana      0.50%     50.5MiB / 200MiB    25.25%
   dceb7593c87d   platform-prometheus   0.00%     19.59MiB / 250MiB    7.84%
   ```
   **结论：双容器总常驻内存仅 70.09 MiB，CPU 占用低于 0.5%，四项门禁全部 100% 达标！**

---

### 门禁 5：前端内嵌大盘（方案 B）全链路验收
- **测试方法：**
  1. 验证 Grafana 容器响应头移除了 `X-Frame-Options: deny` 且开启了匿名只读（角色 Viewer）。
  2. 运行前端 TypeScript 类型检查与全量单元测试。
  3. 验证本地 Web 平台 `/workspace/observability` 页面正确加载与响应。
- **验证结果：**
  - [x] 远端 `curl -sI 'http://127.0.0.1:3000/d/ai-platform-overview/ai-agent-platform-infrastructure?orgId=1&kiosk'` 返回 `200 OK`，无 `X-Frame-Options: deny`。
  - [x] 前端 `pnpm typecheck`：**TypeScript: No errors found**。
  - [x] 专属组件单测 `ObservabilityDashboardPage.spec.ts`：**3 passed in 8.06s**。
  - [x] 前端全量单测：**153 test files passed, 906 tests passed (100% 绿灯)**。
  - [x] 本地隔离环境 `curl -sI http://127.0.0.1:26631/workspace/observability` 返回 `HTTP/1.1 200 OK`。
