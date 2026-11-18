# 实施任务清单（tasks.md）

> 状态标记统一遵循：`待开始`、`进行中`、`已完成（done）`、`部分完成（partial）`、`等待条件（blocked）`。

---

### Task 1：后端接口支持异步非阻塞模式（FastAPI BackgroundTasks）

**背景：** 解决大体量会话转换耗时长、同步请求极易超时（前端 30s timeout）及长时间占用连接池的问题。
**状态：** 已完成（done）。
**完成标准：** `POST /api/evaluation/materials/send` 支持 `async_mode`，返回 202 Accepted，耗时 < 500ms，后台异步执行完整快照、脱敏与 EvalFlow 推送链路。
**涉及位置：** `apps/platform-api/src/platform_api/modules/evaluation/materials.py`

- [x] 在 `MaterialRequest` 中扩展 `async_mode: bool = True` 字段；
- [x] 改造 `send_materials` 路由：注入 `BackgroundTasks`，在完成前置权限与参数校验后立即返回 `202 Accepted`；
- [x] 封装后台异步执行函数 `process_materials_background`，负责执行 `snapshot`、脱敏、`forward` 与用例生成；
- [x] 增加后端单元测试与契约测试（`test_async_mode_returns_202_accepted_and_dispatches_background_task`、`test_background_task_processes_and_notifies`）。

**开发与验证证据：**
- 真实执行耗时：`POST /api/evaluation/materials/send` 在 0.357 秒内返回 HTTP 202 Accepted；
- 单元测试：`apps/platform-api/tests/test_evaluation_materials.py` 15 项测试全部通过（1.28s）。

---

### Task 2：评测转换完成后的通知中心（Notification Center）自动触达

**背景：** 用户在提交后台任务后离开了弹窗，需要通过系统通知知道任务何时完成并一键直达 EvalFlow 详情页。
**状态：** 已完成（done）。
**完成标准：** 后台任务执行完毕后，自动通过 `NotificationService` 给当前用户和项目创建站内通知；通知包含直达 EvalFlow 的 `action_url`；若失败则记录失败原因通知。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/evaluation/materials.py`
- `apps/platform-api/src/platform_api/modules/notifications/service.py`

- [x] 后台任务成功结束时调用 `notify_conversion_result` 生成成功通知与直达跳转链接（`http://127.0.0.1:9128/#/authoring/<item_id>`）；
- [x] 捕获异常失败时生成 Warning/Error 级别通知，附带明确的排查原因（如密钥拦截提示）；
- [x] 验证站内信落库正确，未读计数增加，接口 `/api/notifications` 正确查出通知卡片。

**开发与验证证据：**
- 端到端脚本轮询验证：后台完成处理后，成功在 `/api/notifications` 检索到 `NotificationCategory.SYSTEM` 级别卡片，通知标题与排查说明精准交付。

---

### Task 3：前端弹窗交互重构与无感 Toast 反馈

**背景：** 废除弹窗内无休止的“正在转换，请稍候...”，实现点击即走、全局 Toast 提示与通知中心无缝联动。
**状态：** 已完成（done）。
**完成标准：** 用户点击转换后弹窗在 500ms 内自动关闭，弹出全局 info Toast；收到站内信后红点提醒，点击卡片直接跳转 EvalFlow。
**涉及位置：**
- `apps/platform-web/src/modules/evaluation/components/SendSessionMaterials.vue`
- `apps/platform-web/src/modules/notifications/components/NotificationCenterDropdown.vue`

- [x] `SendSessionMaterials.vue` 发起请求携带 `async_mode: true`，处理 202 Accepted 状态，立即触发 `emit("close")`；
- [x] 调用 `useUiStore().pushToast` 弹出轻量全局提示：“评测集【...】转换任务已在后台启动，可在顶栏通知中心查看结果”；
- [x] 前端已在组件卸载及 Pinia 隔离环境下增加容错保护；
- [x] 运行 Vitest 单元测试（3 项通过）与 `vue-tsc --noEmit`（0 报错）。

**开发与验证证据：**
- 单测验证：`SendSessionMaterials.spec.ts` 3 项测试全部通过（1.95s）；
- 类型验证：`pnpm --dir apps/platform-web exec vue-tsc --noEmit` 0 错误退出。

---

### Task 4：真实多轮长会话全链路集成与端到端验证

**背景：** 确保在真实会话与长耗时计算下，后台异步机制稳健运行，通知精准推送，跳转链路通畅。
**状态：** 已完成（done）。
**完成标准：** 触发真实转换，弹窗秒级关闭，后台无阻塞完成数据推送，通知中心成功接收卡片，点击直达 EvalFlow 页面。
**涉及位置：** 全链路联调。

- [x] 执行真实长会话转换并核验接口耗时（0.357s 即返回 202 Accepted）；
- [x] 查看 platform-api 日志，确认后台异步任务稳定执行约 39s，无线程锁死与请求超时；
- [x] 验证通知中心成功接收任务处理卡片，包含直达链接与错误排查指南；
- [x] platform-api 生产服务已重启加载最新代码（PID 2142 端口正常监听）。

**开发与验证证据：**
- 真实脚本自动化全链路测试（端到端轮询）一次性成功跑通。
