# 前端可观测性与端到端排障链路增强 - 整体方案 (V2 升级版)

> **设计背景与核心动因**：
> 针对用户在日常使用与联调过程中遇到的“执行出错，请刷新或重试”黑盒报错，以及“在哪个界面看排障”、“为什么没有弹窗/专属页面展示详情”的困惑，本项目深入借鉴参考了 `open-swe` 工业级 Agent 项目的设计与开发范式，去除其业务属性，深度融入当前平台的三层解耦架构（Web → API → Runtime），并严格遵循 LangGraph 官方最佳实践。

---

## 一、 核心痛点与心智模型澄清

### 1. 为什么“业务执行报错”不能直接触发“全屏崩溃卡片 (CrashScreen)”？
- **系统级崩溃 (Fatal Crash)**：Vue 组件生命周期异常、未捕获的语法错误、或缺少安全 API 导致的整站白屏。此时前端渲染树已被摧毁，必须由 `ErrorBoundary.vue` 接管渲染 `CrashScreen` 兜底。
- **运行级业务失败 (Run Execution Error)**：大模型提供商超时、Rate Limit、上下文超限、沙箱失联或工具调用失败。这是业务流程中的中断，**绝不能粗暴地卸载整个聊天页面**（否则用户的会话历史、输入框草稿与上下文被全部误杀）。
- **用户真正的诉求**：用户要的不是毁灭性的整屏白屏卡片，而是**“就地可交互的结构化排障可视化”**！以前界面只给一条简陋红条，还只能复制剪贴板，用户在屏幕上看不到结构化根因，并且不知道系统里其实早就在轨迹视图中存在 `RunDiagnostics`。

### 2. 借鉴 open-swe 的核心设计范式（去业务化）
1. **结构化错误原因码与下一步动作建议（Reason Code & Actionable Follow-up）**：
   - 错误不再是一句干瘪的“执行失败”，后端/前端统一维护分类字典（如 `provider_timeout`、`context_too_long`、`step_limit`、`sandbox_unreachable`），并为每种错误匹配人话解释与可执行动作建议（如 `context_too_long` → “建议开启新会话以重置上下文”；`step_limit` → “已达最大单轮步数上限，请精简任务目标”）。
2. **就地排障交互（In-place Diagnostic Inspection）**：
   - 对标 open-swe 在 `AgentThreadView` 错误态中直接暴露 `Open trace` / `Inspect` 操作：在聊天报错状态条中，提供 **【查看排障详情】** 按钮，点击直接弹出结构化排障模态窗/抽屉（`DiagnosticDetailModal.vue`），直观展示错误码、真实后端详情、关联 Request ID、Trace ID 与失败步骤。
3. **Trace 凭据全链路贯通（End-to-End Tracing）**：
   - Trace ID 与 Request ID 成为平台一级公民，在前端 Axios/SSE、API 网关日志、Runtime LangGraph 执行快照中严格对齐。

---

## 二、 三层职责边界划分

```mermaid
flowchart TD
    subgraph Platform_Web [前端: Platform Web]
        A1[ChatAgentStatusBar 报错态] --> A2[【查看排障详情】按钮]
        A2 --> A3[DiagnosticDetailModal 排障模态窗]
        A3 --> A4[展示: 错误码 / 人话建议 / Request ID / 堆栈]
        A3 --> A5[【前往完整轨迹诊断】一键联动]
        A5 --> A6[切换至 TrajectoryView / RunDiagnostics]
    end

    subgraph Platform_API [后端: Platform API]
        B1[Run 异常捕获与分类] --> B2[classify_run_error 错误分类器]
        B2 --> B3[生成结构化 Reason Code 与 Actionable Follow-up]
        B3 --> B4[注入 SSE 终态 error 事件帧与 Error Envelope]
        B3 --> B5[/threads/.../runs/.../diagnostics 接口吐出完整诊断快照]
    end

    subgraph Runtime_Service [运行时: Runtime Service]
        C1[LangGraph Graph 执行] --> C2[Pregel 节点级异常拦截]
        C2 --> C3[捕获 APITimeoutError / GraphRecursionError 等]
        C3 --> C4[写入 Run metadata 与平台 Trace 关联]
        C4 --> C5[流式传输在异常时 emit 结构化错误帧，杜绝静默断连]
    end

    Platform_Web <-->|HTTP / SSE 全链路携带 x-request-id / trace_id| Platform_API
    Platform_API <-->|gRPC / REST 内部调用透传 context| Runtime_Service
```

### 1. 哪些是前端做的？（Platform Web）
- **【必须做】**：
  1. **状态条排障动作升级**：在 `ChatAgentStatusBar.vue` 错误状态条右侧，增加【查看排障详情】按钮（与现有【复制排障包】并列，提供清晰图标与文案）。
  2. **新建排障模态窗组件 (`DiagnosticDetailModal.vue`)**：点击状态条按钮或全局错误 Toast 时就地弹出，展示：
     - 结构化错误状态与严重度徽章；
     - 错误机器码（如 `provider_timeout`、`runtime.execution_failed`）与人话根因；
     - **Actionable Follow-up（下一步恢复建议）**；
     - 全链路凭据：`Request ID`（点击一键复制）、`Trace ID`（若有）；
     - 详细报错上下文与堆栈折叠面板；
     - 【前往完整轨迹】快捷链接（联动切换 `activeView = 'trajectory'` 并激活 `diagnostics` 模式）。
  3. **错误原因与建议映射字典强化**：在 `diagnostic-packet.ts` 中移植并丰富 open-swe 的 `_REASON_TEXT` 和 `_REASON_FOLLOW_UP` 本地兜底映射。
- **【不需要做】**：
  - 严禁将普通的 Agent 业务 Run 失败重定向或劫持为全屏 `CrashScreen`，严禁销毁正在进行的聊天上下文。

### 2. 哪些是后端做的？（Platform API）
- **【必须做】**：
  1. **Run 错误分类器（`run_error_classifier.py`）**：借鉴 open-swe `completion.py` 与 `errors.py`，建立后端统一的错误映射体系，将来自 Runtime 的各类异常（超时、模型拒绝、沙箱失联、循环递归）转换为平台标准机器码，并附带可操作恢复建议。
  2. **诊断快照接口增强**：确保 `/api/v1/threads/{thread_id}/runs/{run_id}/diagnostics` 接口在发生错误时，能返回包含准确分类、失败节点与上下文的完整快照，且必须包含全局 `request_id`。
  3. **SSE 流式传输终态错误帧规范化**：在流式中断或遇到错误时，确保推送符合标准的 `event: error` 帧，携带 `trace_id` 与标准 Envelope，不发生静默 Socket 重置。
- **【不需要做】**：
  - 不需要新建独立的数据库表，充分复用现有的 PostgreSQL `runs` 记录与 Redis 状态缓存。

### 3. 哪些是 Runtime Service 层做的事情？
- **【必须做】**：
  1. **LangGraph 节点异常优雅捕获**：在 LangGraph Node 与 Tool 执行边界，严格按照官方规范使用 `RunnableConfig` 传递并记录 `platform_trace_id`；
  2. **标准异常映射**：捕获常见异常类型（如 `GraphRecursionError` 映射为 `step_limit`，大模型超时映射为 `provider_timeout`），封装进 Run 执行元数据；
  3. **流式安全收尾**：确保在流式输出中捕获到未处理异常时，流式生成器在退出前发出结构化错误事件帧，杜绝前端假死。
- **【不需要做】**：
  - 严禁自行造轮子重写 LangGraph 的 Pregel 运行时或调度引擎，严格基于官方 `astream_events` / `stream` 机制。

---

## 三、 代码改造清单与文件落点

| 服务 / 模块 | 文件路径 | 改造性质 | 详细工作内容 |
|---|---|---|---|
| **Platform Web** | `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue` | **新增** | 排障详情模态窗：就地呈现结构化错误、根因、Actionable 建议、Request ID、详细上下文，支持一键复制与切换至轨迹视角。 |
| **Platform Web** | `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue` | **修改** | 在错误态下并列渲染【查看排障详情】与【复制排障包】，绑定唤起模态窗事件。 |
| **Platform Web** | `apps/platform-web/src/modules/chat/components/ChatSession.vue` | **修改** | 挂载 `DiagnosticDetailModal`，提供从状态条唤起弹窗及从弹窗跳转到 `TrajectoryView` 诊断面板的联动。 |
| **Platform Web** | `apps/platform-web/src/services/observability/diagnostic-packet.ts` | **修改** | 注入 open-swe 风格的 `_REASON_TEXT` 和 `_REASON_FOLLOW_UP` 字典，输出更友好的建议。 |
| **Platform API** | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_error_classifier.py` | **新增** | 实现标准错误机器码分类器与建议生成器（对齐 open-swe）。 |
| **Platform API** | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` | **修改** | 确保诊断快照中始终包含 `reason_code`、`follow_up` 和全链路 `request_id`。 |
| **Runtime Service** | `apps/runtime-service/src/runtime_service/agents/executor.py` (或对应 graph 运行层) | **修改** | 校验 LangGraph Node 级异常捕获，确保异常转换为结构化终态与 SSE 错误帧。 |

---

## 四、 实施计划与验证闭环

### Phase 4.1: 前端就地排障交互与模态窗落地 (Web)
1. 实现 `DiagnosticDetailModal.vue`，具备友好的错误徽章、根因反解、建议卡片、Request ID 复制、以及【前往轨迹视图】跳转。
2. 改造 `ChatAgentStatusBar.vue`，支持点击【查看排障详情】打开模态窗。
3. 改造 `ChatSession.vue`，实现跨组件事件联动。
4. 编写 `DiagnosticDetailModal.spec.ts` 单元测试，确保渲染与复制功能 100% 覆盖。

### Phase 4.2: 后端与运行时错误分类与契约强化 (API & Runtime)
1. 编写 `run_error_classifier.py`，实现多维异常映射与 Actionable 建议生成。
2. 确保 API 诊断快照接口与 SSE 错误事件帧包含完整分类字段。
3. 编写 `test_run_error_classifier.py` 单元测试。

### Phase 4.3: Playwright + Chromium 自动化端到端闭环验证 (E2E)
1. 编写 Playwright E2E 测试脚本，模拟触发 Agent 运行错误（如模型超时或无效请求）。
2. 断言验证：
   - 聊天界面底部状态条显示错误，并正确展示【查看排障详情】按钮；
   - 点击按钮，`DiagnosticDetailModal` 成功弹出；
   - 弹窗内正确显示 Request ID、错误机器码与可操作建议；
   - 点击【前往轨迹诊断】按钮，视角自动无缝平滑切换到 `TrajectoryView` 的运行诊断面板；
3. 截图留痕至项目文档目录，形成严密的验收证据链。
