# Phase 4 实现记录: 三层端到端排障体系与就地排障模态窗

## 概述
针对用户在普通会话报错时“在哪个界面看”、“为何不能弹窗查看详情”的痛点，深入借鉴参考了 `open-swe` 工业级 Agent 项目的设计思想（去业务化），实现了全链路就地排障与轨迹诊断联动。

## 详细改动

### 1. 前端组件与交互升级 (Platform Web)
- **新建组件：** `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
  - 居中半透明遮罩卡片，结构化展示原因机器码（`reason_code`）、根因解析、Actionable 下一步恢复建议（`follow_up`）、对账凭据 `request_id`（带点击一键复制）；
  - 折叠面板展示原始错误文本与堆栈；
  - 底部提供【前往完整轨迹诊断 (Trajectory)】跳转按钮，实现轻量弹窗到深度轨迹图的无缝穿透。
- **状态栏改造：** `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue`
  - 在报错状态下，右侧并列显式提供红色【查看排障详情】按钮与描边【复制排障信息】按钮；
  - 点击【查看排障详情】触发 `inspectDiagnostic` 事件。
- **会话联动：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
  - 挂载 `DiagnosticDetailModal`，接收状态栏事件唤起弹窗；
  - 响应弹窗内【前往完整轨迹诊断】，平滑将 `activeView` 切换至 `'trajectory'` 并将 `trajectoryInspectorMode` 设为 `'diagnostics'`。
- **字典扩充：** `apps/platform-web/src/services/observability/diagnostic-packet.ts`
  - 植入 `REASON_CODE_TEXT`、`REASON_CODE_FOLLOW_UP` 与 `resolveReasonDetails` 解析器。

### 2. 后端分类器 (Platform API)
- **新建模块：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_error_classifier.py`
  - 标准化分类异常类名、HTTP 状态码及错误信息，映射为统一机器码与可执行动作建议。

### 3. 验证与门禁
- **Web 单元测试：**
  - `DiagnosticDetailModal.spec.ts` (5 passed)
  - `ChatAgentStatusBar.spec.ts` (17 passed)
  - `diagnostic-packet.spec.ts` (8 passed)
- **API 单元测试：**
  - `test_run_error_classifier.py` (4 passed)
- **Runtime 单元测试：**
  - `test_diagnostics.py` (35 passed)
- **类型门禁：** `vue-tsc --noEmit` 0 errors
- **构建门禁：** `vite build` 17.51s 打包成功
- **Playwright + Chromium 自动化端到端测试：**
  - `e2e/observability-and-diagnostic-tracing.spec.ts` 3 passed (4.1s)
  - 全景截图固化：
    - `01-crash-screen-captured.png`
    - `02-chat-error-diagnostic-button.png`
    - `03-diagnostic-modal-open.png`
    - `04-trajectory-diagnostics-linked.png`
