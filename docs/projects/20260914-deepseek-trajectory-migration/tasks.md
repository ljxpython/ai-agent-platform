# DeepSeek Harness 轨迹视图迁移 - 任务拆分

## Phase 1: 数据适配层与单测
- [x] 定义 `TrajectoryRecord` 及其关联类型契约。**状态：** 已完成
- [x] 实现 `trajectory-adapter.ts`，支持消息、工具、思考链适配与缺字段安全降级。**状态：** 已完成
- [x] 编写 `trajectory-adapter.spec.ts` 并通过全部单元测试。**状态：** 已完成

## Phase 2: Vue 3 轨迹视图组件
- [x] 实现 `TrajectoryInspector.vue`（Overview, Input, Output, Reasoning, Raw JSON 多 Tab 检查器）。**状态：** 已完成
- [x] 实现 `TrajectoryLedger.vue`（按轮次与步骤分组的流水账，带状态灯、徽章与选中联动）。**状态：** 已完成
- [x] 实现 `TrajectoryView.vue`（Master-Detail 工作台容器，支持过滤与响应式排版）。**状态：** 已完成

## Phase 3: 视图集成与端到端验收
- [x] 在 `ChatSession.vue` 顶栏增加对话/轨迹视图切换开关，集成 `TrajectoryView`。**状态：** 已完成
- [x] 运行平台前端全量类型检查 `vue-tsc` 与测试套件。**状态：** 已完成
- [x] 验证包含工具调用、思考过程、异常失败等多场景下的轨迹渲染与检查器交互。**状态：** 已完成

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成

