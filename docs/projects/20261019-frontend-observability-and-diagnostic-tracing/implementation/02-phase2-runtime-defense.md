# Phase 2 实施记录：运行时防御与防白屏

## 概述
- **完成时间：** 2026-10-19
- **状态：** `done`
- **主要工作：** 实现全局 `ErrorBoundary.vue` 与 CrashScreen 崩溃防御卡片，包裹 `App.vue` 的 `<RouterView />`；在 `main.ts` 中注册 `app.config.errorHandler` 与 `unhandledrejection` 监听；在 `router/index.ts` 中实现动态 chunk 加载 404 自愈与错误记录。

## 改动详情

### 1. `apps/platform-web/src/components/feedback/ErrorBoundary.vue`
- 基于 Vue 3 `onErrorCaptured` 拦截所有子组件生命周期与渲染期未捕获异常，阻止冒泡到根实例导致白屏。
- 渲染高颜值崩溃防御卡片（包含错误信息、堆栈展开/折叠、重新加载页面、复制排障信息及尝试恢复按钮）。
- 捕获到的异常自动推入 `errorRingBuffer`。
- 测试：`ErrorBoundary.spec.ts`（3 passed）。

### 2. `apps/platform-web/src/App.vue`
- 引入 `ErrorBoundary`，直接包裹 `<RouterView />`，确保任意页面崩掉时整站安全降级。

### 3. `apps/platform-web/src/main.ts`
- 挂载 `window.addEventListener("unhandledrejection")`，捕获异步 Promise 遗漏抛出异常并记入 `errorRingBuffer`。
- 配置 `app.config.errorHandler`，全局兜底拦截 Vue 运行时错误并推入缓冲区。

### 4. `apps/platform-web/src/router/index.ts`
- 注册 `router.onError`，识别 `Failed to fetch dynamically imported module` 及 `Loading chunk failed` 等资源丢失错误。
- 记入 `errorRingBuffer`，并在检测到发版引起的动态 chunk 丢失时，使用 `sessionStorage` 标识执行一次防死循环的平滑刷新自愈。
- 测试：`router` 套件 11 项全绿。
