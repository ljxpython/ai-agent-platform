# 06-05 Trace-to-Logs 毫秒级分布式排障日志穿透时序深度解密

> **场景定位与核心价值**：解析对标大厂（阿里 ARMS、字节排障）体验的**分布式微服务排障全链路贯穿时序**。
> 解决微服务排障中“前端报错、后端日志如大海捞针”的痛点；凭借单一 `trace_id`，在前端一屏内同时展现微服务调用拓扑瀑布图与各服务毫秒级对齐的详细上下文日志，并无缝直达 Langfuse 链路树。

---

## 零、 场景拓扑与核心时序

```mermaid
sequenceDiagram
    autonumber
    participant Web as 前端工作台 (DiagnosticDetailModal.vue)
    participant API as Platform API (2142)
    participant Loki as Grafana Loki (端口: 3100)
    participant Langfuse as Langfuse APM (端口: 3000)

    %% 用户触发排障
    Note over Web: 运行报错或用户点击轨迹排障<br>获取到当前 trace_id = 4bf92f35...
    Web->>API: 1. GET /api/v1/diagnostics/traces/{trace_id}/logs

    %% API 网关向 Loki 查询
    Note over API: 激活自回声拦截器：<br>禁用本次查询的自动日志记录<br>组装 LogQL: {service=~"platform-api|runtime-service", trace_id="4bf92f35..."}
    API->>Loki: 2. POST /loki/api/v1/query_range (LogQL)
    Loki->>Loki: 3. TSDB 毫秒级标签检索与流式解压过滤
    Loki-->>API: 4. 返回排序后的结构化原始日志流

    %% API 对齐与格式化
    Note over API: 解析时间戳与微服务来源<br>计算每个 Span 的跨度耗时与起止偏移<br>生成结构化排障包 (Diagnostic Packet)
    API-->>Web: 5. 返回格式化排障 JSON 报文

    %% 前端大屏渲染与穿透
    Note over Web: 渲染四联核心指标卡片<br>渲染跨服务毫秒甘特瀑布流<br>提供即时搜索与日志级别过滤
    Web->>Web: 6. 构造自适应三级 Langfuse URL
    Web->>Langfuse: 7. 用户点击外链，新窗口直达大模型调用 Trace 树
```

---

## 一、 关键阶段与源码坐标映射

| 阶段步骤 | 关键代码路径 | 职责与防御细节 |
|---|---|---|
| **1. 诊断接口与自回声阻断** | `apps/platform-api/src/platform_api/modules/diagnostics/router.py` | `query_trace_logs()`，向 Loki 发起 LogQL，排除自污染路径 |
| **2. Loki TSDB 标签聚合** | `deploy/docker-compose.observability.yml` | 依托 TSDB 索引对 `trace_id` 毫秒直查，无全文倒排索引开销 |
| **3. 前端甘特瀑布流呈现** | `apps/platform-web/src/modules/diagnostics/components/DiagnosticDetailModal.vue` | 耗时瀑布流渲染、微服务调用分层、深浅主题自适应 |
| **4. Langfuse 三级自适应跳转** | `apps/platform-web/src/modules/diagnostics/utils/langfuseUrl.ts` | `resolveLangfuseTraceUrl()`，基于环境变量与项目元数据防 404 |
