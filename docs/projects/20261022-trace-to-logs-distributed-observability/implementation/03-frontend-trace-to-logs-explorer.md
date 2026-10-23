# 前端全链路可观测诊断中心与 Trace-to-Logs 穿透联动

## 改动时间
2026-10-22

## 相关任务
- Task 3.1: Platform Web 诊断弹窗与审计日志增加一键查日志跳转

## 改动文件
- `apps/platform-web/src/modules/chat/components/DiagnosticDetailModal.vue`
- `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`
- `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.spec.ts`

## 具体改动

### 1. 错误排障弹窗增加微服务全链路日志跳转
- **位置：** `DiagnosticDetailModal.vue`
- **体验提升：** 在原有“Langfuse 追踪”按钮旁增设“微服务全链路日志”按钮。当 Agent 对话或执行发生异常时，操作人员直接点击即可在新窗口打开携带该 `traceId` 的诊断中心，直接调取两端微服务实时日志。

### 2. 内嵌大盘升级为全链路可观测诊断中心
- **位置：** `ObservabilityDashboardPage.vue`
- **功能特性：**
  - **动态诊断模式识别：** 监听 URL 中的 `traceId` 参数。若带有 `traceId`，自动切换至 Grafana Explore 视角，预填 Loki 聚合 LogQL 查询表达式 `{service=~"platform-api|runtime-service"} |= "${traceId}"`；若无 `traceId`，展示基础设施总览。
  - **顶部检索与快速清除：** 页面顶部提供专用的 Trace ID 诊断搜索栏，支持实时输入 ID 进行穿透诊断，并带有高亮诊断横幅和返回总览快捷动作。
  - **大模型拓扑无缝跳转：** 诊断横幅提供“在 Langfuse 查看大模型执行树 ↗”直达链接，彻底把 Trace 拓扑与微服务日志融为一体。

## 验证结果
1. `ObservabilityDashboardPage.spec.ts`：4 项测试 100% 绿灯。
2. `pnpm typecheck`：**TypeScript: No errors found**。
