# MLflow 链路追踪与会话评测适配方案 (Traces & Sessions)

## 1. 架构总览与定位

本项目旨在将已部署在 `sshmy1:5000` 上的自研/定制化 MLflow 评测与链路追踪平台（`mlflow-eval-platform`）接入 `ai-agent-platform`，实现与现有 `Langfuse` 的双轨并存和动态切换机制。

```
                         [用户浏览器 / Platform Web]
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
    [前端诊断直达/内嵌]                             [普通平台聊天与调度]
    - Langfuse Trace 视图                           - 发送消息 / 轮询状态
    - MLflow Traces & Sessions 视图                            │
              │                                               ▼
              │                                      [Platform API 网关]
              │                                               │ 透传 W3C traceparent
              │                                               ▼
              │                                      [Runtime Service 引擎]
              │                                               │
              │                               ┌───────────────┴───────────────┐
              │                               ▼ (根据 TRACING_PROVIDER 路由)  ▼
              │                     [Langfuse Callback]            [MLflow Tracer Adapter]
              │                               │                               │
              ▼                               ▼                               ▼
     (查看 Traces/Sessions)          [Langfuse Server]          [sshmy1:5000 MLflow Server]
```

---

## 2. 当前项目 `ai-agent-platform` 改动点分析

### 2.1 后端改动（`apps/runtime-service`）
- **环境变量配置扩展**：
  - `TRACING_PROVIDER`：默认 `langfuse`，可选 `mlflow`、`both`（双写）、`none`。
  - `MLFLOW_TRACKING_URI`：指定 MLflow 服务端地址（如 `http://49.233.222.54:5000` 或集群内网地址）。
  - `MLFLOW_EXPERIMENT_NAME`：默认实验名称（如 `ai-agent-platform-traces`，或动态按 `project-{project_id}` 分桶）。
  - `MLFLOW_TRACKING_TOKEN` / `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD`：鉴权支持（如远端开启认证）。
- **可观测适配层（Observability Adapter）重构**：
  - 新增模块 `runtime_service/observability/mlflow.py`，实现 `MLflowTracer`。
  - 统一抽象 `with_tracing(graph, metadata)`，替代现有的硬编码 `with_langfuse_tracing`。
  - **核心字段映射协议**：
    - 平台的 `thread_id` 映射为 MLflow 的 Tag **`mlflow.session_id`**（MLflow 原生支持按 Session 聚合会话多轮历史）。
    - 平台的 `run_id` 映射为 MLflow Trace 的 Root Span 或关联 Run ID。
    - 平台的 W3C `trace_id` 映射为 Tag **`platform_trace_id`**，确保与 Loki 日志完全打通。
    - 注入 `project_id`、`user_id`、`graph_id`、`model_name` 等元数据 Tag。
- **Fail-Soft 故障隔离保护**：
  - 继承既有 Langfuse 的韧性原则：MLflow 网络超时、连接失败或序列化异常时，**捕获并记录 warning，绝对不能抛出异常阻断 Agent 执行**。

### 2.2 API 网关改动（`apps/platform-api`）
- **配置透出与路由元数据**：
  - 向前端暴露当前启用的追踪提供商（`tracing_provider: "langfuse" | "mlflow"`）及查看 Base URL。
  - 在会话详情与诊断接口响应中，返回针对当前 Provider 构造的 Trace 跳转链接。

### 2.3 前端改动（`apps/platform-web`）
- **大盘内嵌页面动态适配**：
  - 在 `workspace-observability` 导航区域，增加或动态切换 **「链路与会话评测 (MLflow)」** 入口。
  - 若 `VITE_TRACING_PROVIDER=mlflow`，内嵌或跳转至 MLflow 的 `#/experiments/{experiment_id}/traces` 页面。
- **会话诊断弹窗（TraceDiagnostics / RunDiagnostics）直达**：
  - 抽象 URL 生成器：`buildTraceExplorerUrl({ provider, traceId, threadId, runId })`。
  - 当 Provider 为 `mlflow` 时，点击直接跳转至 `http://<host>:5000/#/experiments/.../traces?search=session_id='{thread_id}'` 或定位具体 Trace。

---

## 3. 远端与本地项目 `mlflow-eval-platform` 改动点分析

经实地勘测与源码审计，`mlflow-eval-platform`（MLflow 3.18.dev）已在 `sshmy1:5000` 通过 systemd 服务（`mlflow-eval.service`）运行。为了与平台无缝集成，该项目需进行以下协同调整：

### 3.1 解除 Iframe 嵌套限制（Clickjacking Defense 调优）
- **当前现状**：`curl -sI http://127.0.0.1:5000` 返回 `x-frame-options: SAMEORIGIN`，前端直接 iframe 嵌入会触发浏览器跨域阻断。
- **改动方式**：
  - MLflow 源码已原生支持 `--x-frame-options` 与环境变量 `MLFLOW_SERVER_X_FRAME_OPTIONS`。
  - 在 `/opt/mlflow-eval-platform/.env` 中增加：
    ```bash
    MLFLOW_SERVER_X_FRAME_OPTIONS=NONE
    ```
    或配置反代允许平台前端域名（如 `ALLOW-FROM` 或 CSP `frame-ancestors`），随后重启 `mlflow-eval.service`。

### 3.2 跨域 CORS 支持（API 跨域读取）
- **当前现状**：前端如果需要异步查询 MLflow 内部的 Trace 统计或评测打分，需支持跨域 OPTIONS 预检。
- **改动方式**：
  - 配置 `MLFLOW_SERVER_CORS_ALLOWED_ORIGINS="*"`（或指定前端域名）。

### 3.3 Experiment 与会话结构规约
- 确保 MLflow Tracking Store 中预创建好 `ai-agent-platform-traces` 实验，或者允许 Runtime 客户端具有自动创建 Experiment 权限。
- 确认 MLflow UI 的 Traces & Sessions 视图能够正确响应 `mlflow.session_id` 过滤。

---

## 4. 关键决策记录 (ADR)

1. **为什么用统一适配器（TracerProvider）而不是直接替换 Langfuse？**
   - 保持平台架构开放性与向下兼容，部分团队习惯使用 Langfuse，部分团队更看重 MLflow 的 Evaluation 打分与本地私有化部署。环境变量一键切换最灵活（KISS & YAGNI）。
2. **Session 聚合的方案选型**：
   - 选用 MLflow 官方标准的 `tags["mlflow.session_id"] = thread_id`，这是 MLflow 3.x 界面原生的 Sessions 分组字段，不需要额外自定义 hack。
3. **隔离开发机制**：
   - 建立专用 Git Worktree 开发与独立本地栈验证，不污染现有主工作区代码。
