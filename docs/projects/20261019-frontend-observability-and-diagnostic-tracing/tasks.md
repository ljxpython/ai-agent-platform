# 前端可观测性与端到端排障链路增强 - 任务拆分 (V2)

## Phase 1: 基础设施与契约对齐 (已完成)

- [x] **Task 1.1: 实现有界内存错误缓冲区 (error-buffer)** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/services/observability/error-buffer.ts`
  - 产出：容量为 10 的 FIFO 队列，捕获 HTTP/SSE/JS 异常。
- [x] **Task 1.2: 实现排障诊断数据包生成器与复制工具 (diagnostic-packet)** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/services/observability/diagnostic-packet.ts`
  - 产出：脱敏数据聚合、双模剪贴板降级复制。
- [x] **Task 1.3: 改造 Axios 拦截器与 SSE 错误捕获，关联 Request ID 与 Envelope** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/services/http/client.ts`
  - 产出：全链路提取 `x-request-id` 与 `error.code/message/details`。

---

## Phase 2: 运行时防御与防白屏 (已完成)

- [x] **Task 2.1: 实现全局 ErrorBoundary 与 CrashScreen 崩溃卡片** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/components/feedback/ErrorBoundary.vue`
  - 产出：捕获致命 Vue 渲染崩溃，杜绝白屏。
- [x] **Task 2.2: 挂载全局异常监听与路由 404 自愈** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/main.ts` & `src/router/index.ts`
  - 产出：捕获未处理 Promise rejection 与动态 chunk 加载 404 自愈。

---

## Phase 3: 基础业务呈现与交付 (已完成)

- [x] **Task 3.1: 改造 Chat 状态栏，支持后端错误反解与一键复制排障包** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue`
  - 产出：错误状态条显式提供【复制排障包】按钮与人话反解。
- [x] **Task 3.2: 基础全量验证与自动化门禁** `[x]` (2026-10-19)
  - 产出：34 项单测全绿、vue-tsc 0 错误、Vite 打包成功、初始 E2E 通过。

---

## Phase 4: 三层端到端排障体系强化 (借鉴 open-swe 去业务化设计)

- [x] **Task 4.1: [Web] 实现就地排障模态窗组件 (DiagnosticDetailModal.vue)** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
  - 产出：结构化展示原因码、Actionable 恢复建议、Request ID 复制、折叠堆栈与轨迹视图联动跳转。
  - 验证：`DiagnosticDetailModal.spec.ts` 5 passed。
- [x] **Task 4.2: [Web] 改造 Chat 状态栏与会话联动 (ChatAgentStatusBar & ChatSession)** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue` & `ChatSession.vue`
  - 产出：状态栏显式增加【查看排障详情】按钮，点击就地唤起弹窗，支持一键切换至 `TrajectoryView`。
  - 验证：`ChatAgentStatusBar.spec.ts` 17 passed。
- [x] **Task 4.3: [Web] 强化错误分类与 Actionable 恢复建议字典** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/services/observability/diagnostic-packet.ts`
  - 产出：移植 open-swe 的 `REASON_CODE_TEXT`、`REASON_CODE_FOLLOW_UP` 与 `resolveReasonDetails`。
  - 验证：`diagnostic-packet.spec.ts` 8 passed。
- [x] **Task 4.4: [API] 建立后端 Run 错误分类器与诊断增强** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_error_classifier.py`
  - 产出：对标 open-swe 实现异常分类器与 Actionable 建议生成。
  - 验证：`test_run_error_classifier.py` 4 passed。
- [x] **Task 4.5: [Runtime] LangGraph 异常捕获与流式收尾校验** `[x]` (2026-10-19)
  - 代码位置：`apps/runtime-service/src/runtime_service/observability/errors.py`
  - 产出：契约一致的分类与诊断快照透传。
  - 验证：`test_diagnostics.py` 35 passed。
- [x] **Task 4.6: [E2E] Playwright + Chromium 自动化端到端测试闭环** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/e2e/observability-and-diagnostic-tracing.spec.ts`
  - 产出：Playwright 真实浏览器运行，3 项测试全部绿灯通过；生成 4 张全景截图固化到 `assets/` 目录。

---

## Phase 5: 深度攻坚链路追踪 (Langfuse Open Trace)、原始报错还原与轨迹视图错误节点闭环

- [x] **Task 5.1: [Web] 修复 useChatSession 错误状态被清空的竞态 Bug** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/composables/useChatSession.ts`
  - 产出：修复在 `verify()` 中盲目执行 `else { error.value = ""; }` 的致命 Bug，保留流异常与真实报错。
- [x] **Task 5.2: [Web] 模态窗异步拉取后端安全诊断与 Langfuse Open Trace 直通外链** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
  - 产出：打开时主动异步调用 `getRunDiagnostics`，回填 `execution_request_id`，渲染 Langfuse Trace ID 与 **【在 Langfuse 中打开追踪 (Open Trace ↗)】** 按钮；兜底提取 `model_errors` 与 `graph_executions` 错误，彻底消灭“无可用原始堆栈信息”。
  - 验证：`DiagnosticDetailModal.spec.ts` 6 passed。
- [x] **Task 5.3: [Web] 轨迹视图错误状态计算与兜底错误节点注入** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/modules/chat/components/ChatSession.vue` & `trajectory-adapter.ts`
  - 产出：对齐 `:has-error` 计算包含 `turnState === 'error'` 与 `run.status === 'error'`；在 `buildTrajectoryRecords` 中，若整轮执行报错但无单一节点标红，自动追加明确的“执行异常中断”红色错误记录，支持过滤并联动展开诊断。
  - 验证：`trajectory-adapter.spec.ts` 11 passed。
- [x] **Task 5.4: [Web] 排障诊断数据包整合分布式链路追踪 (Diagnostic Packet)** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/src/services/observability/diagnostic-packet.ts`
  - 产出：一键复制的 Markdown 诊断报告包含 Langfuse Trace URL、Trace ID、Execution Request ID 与服务端模型调用失败详情。
  - 验证：`diagnostic-packet.spec.ts` 9 passed。
- [x] **Task 5.5: [E2E] Playwright 端到端全链路闭环重新验证与截图** `[x]` (2026-10-19)
  - 代码位置：`apps/platform-web/e2e/observability-and-diagnostic-tracing.spec.ts`
  - 产出：Mock 真实安全诊断与 Trace，验证 Open Trace 按钮、Request ID 回填、复制诊断包与轨迹切换，3 项 E2E 测试全部通过，刷新 4 张截图。

---

## 进度概览
- [x] Phase 1 基础设施与契约对齐完成
- [x] Phase 2 运行时防御与防白屏完成
- [x] Phase 3 基础业务呈现与交付完成
- [x] Phase 4 三层端到端排障体系强化完成
- [x] Phase 5 链路追踪与报错堆栈深度攻坚完成
- [x] Final 全量门禁与自动化 E2E 验收通过
