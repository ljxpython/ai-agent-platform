# 工业级可观测性与指标大盘 - 整体方案

> **设计背景与核心动因**：
> 现有平台在 Agent 场景特有的微观可观测（Langfuse 轨迹追踪、前端就地排障弹窗、结构化原因码）已初具雏形，但宏观指标（Metrics）系统仍停留于进程内内存锁计数器的脆弱状态，无法应对多 Worker 并发、服务重启丢数据、缺乏标准时序拉取端点与自动化告警的问题。
> 本方案旨在建立一套轻量、可靠、生产就绪的工业级可观测体系，严格遵循 KISS 与 YAGNI 原则，不引入沉重包袱。

---

## 一、 顶层架构拓扑与双轨制分工

```mermaid
flowchart TD
    subgraph Client_Layer ["前端客户端 (Platform Web)"]
        UI[用户界面 / 就地排障弹窗]
        TraceBtn[【在 Langfuse 中打开链路】直达按钮]
    end

    subgraph Gateway_Layer ["管理与网关层 (Platform API @ sshmy1)"]
        API[FastAPI 接口服务]
        Audit[PostgreSQL 审计存储]
        ApiMetrics[标准 /metrics 端点]
        API_Classifier[Run 错误分类器与建议]
    end

    subgraph Runtime_Layer ["执行与运行时 (Runtime Service @ sshmy1/sshmy2)"]
        Graph[LangGraph 智能体引擎]
        RuntimeMetrics[标准 /metrics 端点]
        LF_Callback[Langfuse 异步安全 Callback]
        Sandbox[Docker 沙箱容器池]
    end

    subgraph Observability_Plane ["监控与可视化大盘 (部署于 sshmy1)"]
        Prometheus[Prometheus 时序数据库 (Scraper)]
        Grafana[Grafana 统一监控大盘]
        LangfuseCloud[Langfuse 服务端]
    end

    %% 数据与调用流
    UI -->|HTTP / SSE 携带统一 request_id| API
    API -->|JWT 透传 platform_trace_id| Graph
    Graph -->|Fail-Soft 异步上报 Execution Tree| LangfuseCloud
    TraceBtn -.->|根据 trace_id 直达| LangfuseCloud

    %% 指标抓取流 (Pull 模式)
    Prometheus -->|定时拉取 GET /metrics (15s)| ApiMetrics
    Prometheus -->|定时拉取 GET /metrics (15s)| RuntimeMetrics
    Grafana -->|查询 PromQL 绘制大盘| Prometheus
```

---

## 二、 核心关键问题解答与设计规范

### 1. 为什么“双轨并行（Langfuse + Prometheus）”是唯一正解？
* **Langfuse 专攻深层语义追踪（Traces）**：
  * **解决什么问题**：一次具体的 Agent Run 经历了什么？调用了什么大模型？返回了什么思维链？调用了哪些 Tool？用了多少 Token？为什么卡死在第 5 步？
  * **局限性**：高频、轻量的数据它处理不了，也没有时序指标聚合与动态报警引擎。
* **Prometheus 专攻宏观生命体征（Metrics）**：
  * **解决什么问题**：现在每秒并发多少（QPS）？P99 延时多少？5xx 错误率有没有超 1%？沙箱容器池还剩几个名额？内存有没有暴涨？
  * **工作机制**：纯粹拉取文本计数器，开销几乎为零，直接喂给 Grafana 画折线图与触发钉钉/邮件告警。

### 2. 服务器资源预算与选址规划（sshmy1 vs sshmy2）

两台服务器角色与资源现状：
* **`sshmy1`（生产管理主机）**：运行 Platform API、Web (Nginx)、PostgreSQL、Redis。架构上是平台的管控中枢。
* **`sshmy2`（计算与数据节点）**：4核 3.6GiB 内存，运行 Docker 沙箱与 LightRAG 向量图谱服务，内存资源较为宝贵。

**部署落点建议**：
* **坚决部署在 `sshmy1`**！
  * 作为管理中心，`sshmy1` 本身已有 Nginx 反向代理，可无缝代理 Grafana 端口并配置身份鉴权；
  * `sshmy2` 内存仅 3.6G，严禁在上面塞多余的监控持久化服务，让其专注承担沙箱与向量计算；
  * 资源开销预算表：

| 组件 | CPU 开销 | 内存开销 (RAM) | 磁盘占用 | 部署方式推荐 |
|---|---|---|---|---|
| **Prometheus** | 0.05 ~ 0.1 核 | 150MB ~ 250MB | ~ 30MB/天 (15天约 500MB) | Systemd 原生服务 或 独立轻量 Docker |
| **Grafana** | 0.01 ~ 0.05 核 | 100MB ~ 180MB | ~ 50MB (仅元数据) | Systemd 原生服务 或 独立轻量 Docker |
| **合计** | **< 0.2 核** | **< 450MB** | **预留 3GB 足够** | **极度低开销，对 sshmy1 无任何压力** |

### 3. OpenTelemetry 到底要不要部署？（彻底破除迷信）
* **结论**：**生产服务器上 0 额外中间件部署！坚决不部署 OTel Collector 守护进程！**
* **理由**：
  * OTel Collector 是超大型微服务集群用来清洗、分发遥测流的网关。对于 2~3 个服务的紧凑架构，引入 Collector 属于典型的过度设计（违背 YAGNI 原则）。
  * 我们采用 **SDK 直出模式（Direct Mode）**：代码里使用标准 Python 库，FastAPI 内存中维护原子计数，直接开放一个 `/metrics` 端点即可，极简、抗造、无运维负担。

### 4. 全链路端到端 Trace 穿透原理（一个 `trace_id` 查穿全链路）

```text
[前端触发错误/日志]
       │
       ▼ (携带 x-request-id: 9f8a3c...)
[Platform API 网关] ──> 结构化日志写入 stdout / PostgreSQL:
       │                event="http_request", trace_id="9f8a3c...", duration_ms=1240
       ▼ (JWT / Header 透传 platform_trace_id="9f8a3c...")
[Runtime Service]   ──> LangGraph 执行, with_langfuse_tracing 绑定:
       │                Trace(id="9f8a3c...", name="agent_run", session_id=thread_id)
       ▼
[Langfuse / 审计]   ──> 输入 9f8a3c... 即可同时查到:
                        1. 外部谁调用的、状态码多少 (API 审计)
                        2. 内部模型思考过程、Tool 传参、Token 用量 (Langfuse)
                        3. 服务器当时的原始 stdout 日志上下文 (Grep)
```

---

## 三、 实施阶段划分

1. **Phase 1：专属 Worktree 内原型与核心代码改造（零外部依赖）**
   - 在 `apps/platform-api` 与 `apps/runtime-service` 内完成指标替换。
   - 编写 Pytest 单元测试，断言 `/metrics` 输出满足标准格式与 Label 分组。
2. **Phase 2：本地栈联调与 Grafana 仪表盘模板制作**
   - 编写用于快速本地验证的单机 Docker Compose（Prometheus + Grafana）。
   - 导出平台专属的 JSON 仪表盘（HTTP 延迟分布、QPS、Agent 任务量、错误分类堆叠）。
3. **Phase 3：远端生产服务器 `sshmy1` 部署与接入**
   - 在 `sshmy1` 部署并配置 Prometheus 与 Grafana，添加 Nginx 代理与账号保护。
   - 配置拉取目标（`sshmy1` 内部 Platform API 与 `sshmy2` 远端 Runtime）。
   - 全链路验证与真实告警测试。
