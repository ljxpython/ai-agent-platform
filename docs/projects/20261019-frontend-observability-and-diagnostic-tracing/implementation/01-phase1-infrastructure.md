# Phase 1 实施记录：基础设施与契约对齐

## 概述
- **完成时间：** 2026-10-19
- **状态：** `done`
- **主要工作：** 落地有界内存错误环形缓冲区 (Cap=10)、排障诊断数据包生成与双模复制工具、以及 Axios / SSE 异常拦截提取 `x-request-id` 与标准 Error Envelope。

## 改动详情

### 1. `apps/platform-web/src/services/observability/error-buffer.ts`
- 实现 `ErrorRingBuffer` 类，定义 `DiagnosticErrorRecord` 接口（含 `id`, `timestamp`, `type`, `status`, `requestId`, `url`, `method`, `code`, `message`, `detail`, `stack`）。
- 严格限制容量（默认 10），超出容量按 FIFO 自动淘汰最旧项，提供全局单例 `errorRingBuffer`。
- 测试：`error-buffer.spec.ts`（4 passed）。

### 2. `apps/platform-web/src/services/observability/diagnostic-packet.ts`
- 实现 `generateDiagnosticMarkdown(context)`，聚合环境上下文、安全上下文、活跃 Project/Thread/Run/Request ID、最近 3 条错误记录与堆栈。
- 实现 `sanitizeDiagnosticText` 严格脱敏 Bearer Token、密码与敏感参数。
- 实现 `copyToClipboard` 双模复制：现代 `navigator.clipboard` 优先，纯 HTTP / 裸 IP 非安全上下文降级使用 `textarea` + `document.execCommand('copy')`。
- 测试：`diagnostic-packet.spec.ts`（6 passed）。

### 3. `apps/platform-web/src/services/http/client.ts` 与 `useChatSession.ts`
- `client.ts` 响应拦截器在请求失败（HTTP 4xx/5xx）时，调用 `extractPlatformHttpError` 提取机器码、message 与详情，并从响应头 `x-request-id` 或 Envelope 中提取 `requestId`，自动记入 `errorRingBuffer`。
- `useChatSession.ts` 在流式异常 `fail(cause)` 时，提取 `requestId`、`code`、message 并自动记入 `errorRingBuffer`。
- 测试：`client.spec.ts`（5 passed）、`composables` 套件（155 passed）。
