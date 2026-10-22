# 分布式全链路追踪与日志关联可观测性工程 - 整体方案

## 背景
在大厂（如字节跳动火山引擎可观测、阿里 ARMS、美团 APM）的微服务架构中，线上故障排查的高效标准是：
> **“研发拿着一个 `trace_id` 贴进诊断框，系统能在一屏内同时展现微服务调用拓扑瀑布图（哪里慢、哪里报错），并且点开任何一个微服务的执行 Span，就能精准拉出该服务在那一瞬间打印出的全部上下文日志。”**

当前本平台的现状是：
1. **指标与监控已完成工业级升级**：Prometheus + Grafana 已就绪，且前端已实现沉浸式内嵌。
2. **大模型链路有 Langfuse 兜底**：单次 Run 内部的 Prompt、Node 拓扑与 Token 有据可查。
3. **但微服务层间的“Trace-to-Logs”排障链路尚未打通**：
   - 当遇到网关 500、跨服务认证失败或沙箱底层崩溃时，无法在一个界面同时看到“API 网关日志 + Runtime 引擎日志”的联合时间轴；
   - 开发者依然需要登录服务器分别敲 `journalctl grep`，效率低、割裂感严重。

因此，本项目旨在引入业界最成熟的轻量级工业方案，彻底闭环“单 trace_id 穿透微服务全链路与关联日志”的诊断能力。

---

## 目标
1. **W3C 规范透传**：在 `Platform API` 与 `Runtime Service` 之间推行 W3C `traceparent` 标准，确保全局 Trace ID 与 Span ID 严格父子递进。
2. **结构化日志统一打标**：三端服务的每一行日志自动包含 `[service, trace_id, span_id, level]`，杜绝无头日志。
3. **超轻量日志中心（Loki + Promtail）**：在 `sshmy1` 部署内存常驻 < 80MB 的日志汇聚引擎，按微服务标签打通时序。
4. **一键穿透联动（Trace-to-Logs）**：在 Grafana 控制台与 Platform Web 诊断弹窗中，输入或点击 `trace_id`，立即呈现跨服务的调用耗时阶梯与毫秒级对齐的详细日志流。

---

## 方案设计

### 整体架构

```
                     +---------------------------------------+
                     |  Platform Web 全链路排障诊断中心      |
                     |  (或内嵌 Grafana Trace/Logs Explorer)  |
                     +-------------------+-------------------+
                                         |
                       根据 trace_id 聚合检索
                                         |
          +------------------------------+------------------------------+
          |                                                             |
          v                                                             v
+-------------------+                                         +-------------------+
|  分布式链路追踪   |                                         |   轻量日志检索    |
|  (Tracing View)   |                                         |   (Logging View)  |
|                   |                                         |                   |
| 1. platform-api   | --[点击某服务 Span]---> 联动过滤 ------>| [API] 收到请求    |
|    (耗时 45ms)    |                                         | [API] 验签通过    |
| 2. runtime-engine |                                         | [RT]  开始执行图  |
|    (耗时 820ms)   |                                         | [RT]  LLM 调用异常|
| 3. langfuse trace |                                         | [API] 熔断并返回  |
+-------------------+                                         +-------------------+
          ^                                                             ^
          | 链路数据                                                    | 日志流
+---------+----------+                                       +----------+---------+
|     Langfuse       |                                       |   Grafana Loki     |
| (大模型与Agent拓扑)|                                       | (微服务结构化日志) |
+--------------------+                                       +----------+---------+
          ^                                                             ^
          |                                                             | 采集
    [Runtime回调]                                                +------+------+
                                                                 |  Promtail   |
                                                                 +------+------+
                                                                        |
                                                         +--------------+--------------+
                                                         |                             |
                                                platform-api.log              runtime-service.log
                                            (带 trace_id, span_id)         (带 trace_id, span_id)
```

---

### 关键改动点

#### 1. 协议规范化：引入 W3C TraceContext（traceparent）
- **涉及服务：** `platform-api` 与 `runtime-service`
- **改动说明：**
  - 网关进入时生成符合 W3C 规范的 `traceparent: 00-{trace_id}-{span_id}-01`。
  - 调下游 Runtime Service 或 MCP 时，通过 HTTP Header 标准透传 `traceparent`。
  - Runtime 接收解析该 Header，将当前调用的父 Span 绑定至自身上下文，保持分布式调用树的父子层级。

#### 2. 日志层统一规范化（MDC / ContextVar 注入）
- **涉及服务：**
  - `apps/platform-api/src/platform_api/core/observability/logging.py`
  - `apps/runtime-service/src/runtime_service/observability/logging.py`
- **改动说明：**
  - 为所有结构化输出统一格式化为：
    `{"ts": "...", "service": "platform-api", "trace_id": "...", "span_id": "...", "level": "INFO", "msg": "..."}`
  - 即使是非结构化文本控制台，也强制前缀 `[service][trace_id][span_id]`，确保日志收集器无论怎么切片都能抓到 TraceID。

#### 3. 部署轻量级日志采集体系（Loki + Promtail）
- **涉及文件：** `deploy/observability/docker-compose.yml`, `deploy/observability/loki.yml`, `promtail.yml`
- **改动说明：**
  - 引入 `grafana/loki:2.9.4`（内存限制 100MB）与 `grafana/promtail:2.9.4`（内存限制 30MB）。
  - Promtail 负责挂载主机上的 Systemd 日志或应用日志，打上标签 `service="platform-api"` 与 `service="runtime-service"`，实时推给 Loki。
  - 在 Grafana 中将 Loki 数据源配置好，并开启 `Derived Fields`（关联正则 `trace_id` 自动渲染跳向 Trace 视图）。

#### 4. 前端排障闭环体验增强
- **涉及服务：** `apps/platform-web`
- **改动说明：**
  - 在内嵌的【指标大盘】页面，预置“全链路追踪与日志诊断面板”。
  - 在【审计日志】详情抽屉与【会话报错弹窗 (DiagnosticDetailModal)】，增加“一键查关联日志”按钮，点击直接带出关联该 `trace_id` 的跨服务全量日志。

---

### 技术选型对比与决策

| 选型对比项 | 方案 A：ELK (Elasticsearch + Logstash + Kibana) | 方案 B：Apache SkyWalking | 方案 C：Grafana LGTM (Loki + Tempo + Grafana) [本次选用] |
| :--- | :--- | :--- | :--- |
| **内存开销** | 极重（ES 单实例至少 2G~4G 内存起步） | 中等（单实例 1G~2G，配置要求高） | **极轻（Loki ~40MB, Promtail ~15MB，总共 < 80MB）** |
| **现有架构融合度** | 差（需引入完全独立的一整套新体系） | 中（自成一体独立 UI，无法融入现有前端） | **完美（与已部署的 Grafana、Prometheus 原生无缝融合）** |
| **维护与运维成本** | 极高（索引轮转、分片、JVM GC 调优） | 较高（需管理存储底座与各服务探针） | **极低（单 Compose 编排，基于文件切片，免调优）** |
| **Trace 联动体验** | 需在 Kibana 自己配置索引模式关联 | 自带 APM 视图但日志检索不如专用工具灵活 | **原生支持 Trace-to-Logs 衍生字段一键跳转** |

**最终决策：** 选用 **方案 C（Grafana Loki + Promtail + 既有 Grafana/Langfuse）**，坚决不给云主机带来沉重负担，用最轻的硬件资源实现大厂同款体验。

---

## 链路影响

### 受影响的调用链路
```
Platform Web (捕获 trace_id)
      ↓
Platform API (生成 W3C traceparent，日志注入 trace_id/span_id)
      ↓ HTTP / SSE (携带 traceparent Header)
Runtime Service (解析 traceparent，日志注入 trace_id/span_id)
      ↓
Systemd 日志 / 文件输出
      ↓ (Promtail 实时收集打标)
Grafana Loki (时序日志存储)
      ↓
Grafana / Platform Web (根据 trace_id 聚合检索跨服务日志)
```

---

## 风险和依赖
- **资源限制风险：** 容器内存超标风险 → **应对：** 在 docker-compose 中对 Loki 和 Promtail 严格施加 100MB / 30MB 内存硬限，并配置内存熔断。
- **日志量膨胀风险：** 高并发下日志打爆磁盘 → **应对：** Loki 配置 `retention_period: 7d`（仅保留 7 天），同时限制单条日志大小与最大并发查询流数。
- **Fail-Soft 保护：** 日志采集或 Loki 离线绝不能影响主业务 API 的 HTTP 返回。

---

## 实施计划
1. **Phase 1（规范与数据协议）：** 确立 W3C TraceContext 与统一结构化日志打标规范，实现 API 与 Runtime 的日志与上下文字段对齐。
2. **Phase 2（日志基础设施部署）：** 在 `sshmy1` 部署轻量级 Loki + Promtail，接入微服务日志并完成数据源挂载。
3. **Phase 3（Trace-to-Logs 联动配置）：** 配置 Grafana Derived Fields 与 Explore 链路跳转，实现点击 TraceID 直达微服务日志。
4. **Phase 4（前端诊断闭环与全链路联调）：** 在 Platform Web 完善一键穿透排障交互，进行真实故障注入与全链路联合验收。
