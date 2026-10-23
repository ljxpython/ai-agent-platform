# 工业级链路可视化与 Langfuse 多租户精准路由落地记录

## 1. 需求背景与痛点根因

在 Phase 5 实现了毫秒级直出代理后，用户在深度使用排障系统时提出了更高维度的工业级排障诉求与稳定性问题：

1. **Langfuse 链路树跳转 404/未找到追踪信息**：
   - **报错现象**：原前端跳转格式为 `https://jp.cloud.langfuse.com/trace/{traceId}`，用户点击后页面报：“未找到追踪信息，该追踪信息可能仍在处理中，也可能已被删除”。
   - **物理根因**：Langfuse Cloud 作为多租户 SaaS 架构，未公开共享（Public Share）的 Trace 数据被租户严格隔离在 `project/{projectId}` 命名空间下。全局 `/trace/{id}` 无法进行跨租户路由，必须定位到用户所属项目下：`https://jp.cloud.langfuse.com/project/{projectId}/traces?filter=isRootObservation%3Bboolean%3B%3B%3D%3Btrue&searchType=id&searchType=content&traceTab=attributes&search={traceId}`。
   - **诉求**：前端需全面兼容该项目级过滤查询格式，并支持在 `.env` 环境变量中灵活配置 `VITE_LANGFUSE_PROJECT_ID`、`VITE_LANGFUSE_BASE_URL` 与自定义模板。

2. **自回声日志污染（Echo Loops）**：
   - `platform-api` 代理向 Loki 发起查询时，底层 `httpx` 会产生 `[httpx] HTTP Request: GET http://127.0.0.1:3100/loki/...` 的 DEBUG/INFO 日志。
   - 这类日志若携带同一 Trace ID 被 Promtail 收集推入 Loki，会导致后续查询返回“自己查 Loki 的请求日志”，产生自回声污染并干扰耗时分析。

3. **大厂排障可视化与体验**：
   - 界面视觉死黑，缺乏明暗主题自适应；
   - 排障时需要直观了解调用全景（耗时分布甘特条、微服务涉及面、错误级别占比、毫秒级本地实时过滤）；
   - 需要在同一页面保留原生极速时间轴与 Grafana Explore 深度视角，便于开发与运维进行双重视角对比。

---

## 2. 核心架构与代码实现

### 2.1 Langfuse 动态 URL 构造器与环境变量配置

#### 2.1.1 环境变量 Schema 扩充
在 `apps/platform-web/src/config/env.ts` 中扩展 Zod 校验：
```typescript
VITE_LANGFUSE_BASE_URL: z.string().url().default('https://jp.cloud.langfuse.com'),
VITE_LANGFUSE_PROJECT_ID: z.string().default(''),
VITE_LANGFUSE_TRACE_URL_TEMPLATE: z.string().default(''),
```
并在 `env` 导出对象中透出 `langfuseBaseUrl`、`langfuseProjectId` 与 `langfuseTraceUrlTemplate`。

#### 2.1.2 工业级三级自适应 URL 构建函数
在 `apps/platform-web/src/services/observability/langfuse-url.ts` 中实现：
1. **最高优先级**：自定义模板 `template`（支持 `{traceId}` 占位符替换，采用 `split("{traceId}").join(...)` 保证 ES2020 兼容）；
2. **多租户推荐模式**：当存在 `projectId` 时，组装精准项目过滤直达 URL：
   `{baseUrl}/project/{projectId}/traces?filter=isRootObservation%3Bboolean%3B%3B%3D%3Btrue&searchType=id&searchType=content&traceTab=attributes&search={traceId}`；
3. **兜底模式**：无 `projectId` 时优雅回退至 `{baseUrl}/trace/{traceId}`。

在 `DiagnosticDetailModal.vue`（错误详情弹窗）与 `TraceDiagnosticsPage.vue`（诊断主页）中统一切换至 `buildLangfuseTraceUrl` 构造器。

### 2.2 彻底阻断 Loki 自回声污染与耗时解析

在 `apps/platform-api/src/platform_api/modules/observability/service.py` 中：
1. **LogQL 层过滤**：将查询过滤条件升级为：
   `{job=~"systemd-journal|app-file-logs"} |= "{clean_trace_id}" !~ "loki/api/v1/query"`，从源头消灭查询 Loki 自身产生的日志；
2. **代码层精准防护**：丢弃任何目标 URL 包含 `loki/api/v1/query` 的 `httpx` 日志行；
3. **耗时解析注入**：提取日志中的 `duration_ms`，注入结构化模型中供前端瀑布流渲染。

### 2.3 大厂工业级排障可视化面板

在 `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue` 中重构落地：
1. **双视角 Tab 切换**：
   - `极速时间轴 (毫秒直出)`：自研轻量代理 API，40ms 极速加载；
   - `Grafana Explore (深度透视)`：按需内嵌 iframe，支持 LogQL 查询构建、重载与全屏。
2. **四联指标概览卡片（Metrics Ribbon）**：
   - 链路总耗时（自动统计并标注 max duration）；
   - 结构化日志总条数；
   - 涉及微服务拓扑列表；
   - 最高错误级别标识。
3. **耗时瀑布流甘特条（Waterfall Gantt Bars）**：
   - 动态计算各节点耗时在全局总耗时中的百分比；
   - 针对超过 500ms 的慢调用以黄色/橙色警示条醒目标记。
4. **毫秒级纯前端瞬时过滤**：
   - 关键词即时搜索（匹配微服务名、摘要、Raw 文本）；
   - 级别过滤（全部、ERROR、WARN、INFO、DEBUG）；
   - 服务维度筛选（支持按具体微服务切片）。
5. **视觉主题对齐**：
   - 全面适配平台标准 `pw-card`、`pw-panel`，在亮色和暗色主题下均呈现自然现代的控制台风格，彻底告别“死黑”与生硬对比。

---

## 3. 验证与测试结果

1. **URL 构造器单元测试**：
   - `apps/platform-web/src/services/observability/langfuse-url.spec.ts` 4 项单测 100% 通过（涵盖精准项目 URL、兜底 URL、自定义模板及非法占位符安全处理）。
2. **弹窗与主页单测全绿**：
   - `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.spec.ts` 3 passed；
   - `apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.spec.ts` 7 passed。
3. **类型与构建双重保障**：
   - `vue-tsc --noEmit` 0 报错；
   - `npm run build` 成功完成。
4. **端到端实测**：
   - Playwright 模拟用户点击【Langfuse 链路树 ↗】，生成的 href 严格对齐用户的预期格式：
     `https://jp.cloud.langfuse.com/project/cmt2gj4cq001fad0dffy9vu9v/traces?filter=isRootObservation%3Bboolean%3B%3B%3D%3Btrue&searchType=id&searchType=content&traceTab=attributes&search=f878c122-0323-4828-a377-3a111b508f20`
