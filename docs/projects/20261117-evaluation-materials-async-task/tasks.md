# 实施任务清单（tasks.md）

> 状态标记统一遵循：`待开始`、`进行中`、`已完成（done）`、`部分完成（partial）`、`等待条件（blocked）`。

---

### Task 1：后端接口支持异步非阻塞模式（FastAPI BackgroundTasks）

**背景：** 解决大体量会话转换耗时长、同步请求极易超时及占用连接池的问题。
**状态：** 待开始。
**完成标准：** `POST /api/evaluation/materials/send` 支持 `async_mode`，返回 202 Accepted，耗时 < 300ms，后台异步执行完整快照、脱敏与 EvalFlow 推送链路。
**涉及位置：** `apps/platform-api/src/platform_api/modules/evaluation/materials.py`

- [ ] 在 `MaterialRequest` 中扩展 `async_mode: bool = True` 字段；
- [ ] 改造 `send_materials` 路由：注入 `BackgroundTasks`，在完成前置权限与参数校验后立即返回 `202 Accepted`；
- [ ] 封装后台异步执行函数 `_run_materials_conversion_background`，负责执行 `snapshot`、脱敏、`forward` 与用例生成；
- [ ] 增加后端单元测试与契约测试。

**开发与验证进度：** 尚未实施。
**下一步：** 用户确认方案后实施。

---

### Task 2：评测转换完成后的通知中心（Notification Center）自动触达

**背景：** 用户在提交后台任务后离开了弹窗，需要通过系统通知知道任务何时完成并一键直达 EvalFlow 详情页。
**状态：** 待开始。
**完成标准：** 后台任务执行完毕后，自动通过 `NotificationService` 给当前用户和项目创建站内通知；通知包含直达 EvalFlow 的 `action_url`；若失败则记录失败原因通知。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/evaluation/materials.py`
- `apps/platform-api/src/platform_api/modules/notifications/service.py`

- [ ] 后台任务成功结束时调用 `notification_service.create_notification` 生成成功通知与跳转链接；
- [ ] 捕获异常失败时生成 Warning/Error 级别通知，附带明确的排查原因；
- [ ] 验证站内信落库正确，未读计数增加。

**开发与验证进度：** 尚未实施。
**下一步：** 依赖 Task 1 完成。

---

### Task 3：前端弹窗交互重构与无感 Toast 反馈

**背景：** 废除弹窗内无休止的“正在转换，请稍候...”，实现点击即走、全局 Toast 提示与通知中心无缝联动。
**状态：** 待开始。
**完成标准：** 用户点击转换后弹窗在 500ms 内自动关闭，弹出全局 info Toast；收到站内信后红点提醒，点击卡片直接跳转 EvalFlow。
**涉及位置：**
- `apps/platform-web/src/modules/evaluation/components/SendSessionMaterials.vue`
- `apps/platform-web/src/modules/notifications/components/NotificationCenterDropdown.vue`

- [ ] `SendSessionMaterials.vue` 发起请求，处理 202 Accepted 状态，立即关闭 Dialog；
- [ ] 调用 `useUiStore().showToast` 弹出提示：“评测集转换任务已在后台启动，可在顶栏通知中心查看结果”；
- [ ] 检查并验证 `NotificationCenterDropdown.vue` 对带有 `action_url` 的通知卡片点击行为，支持新标签页打开外部系统链接；
- [ ] 运行 Vitest 单元测试与 `vue-tsc` 类型检查。

**开发与验证进度：** 尚未实施。
**下一步：** 依赖 Task 1 和 Task 2。

---

### Task 4：真实多轮长会话全链路集成与端到端验证

**背景：** 确保在包含 95 步工具调用的大体量会话下，后台异步机制稳健运行，通知精准推送，跳转链路通畅。
**状态：** 待开始。
**完成标准：** 触发真实转换，弹窗秒级关闭，后台无阻塞完成数据推送，通知中心成功接收卡片，点击直达 EvalFlow 页面。
**涉及位置：** 全链路联调。

- [ ] 执行真实长会话转换并核验接口耗时（< 500ms）；
- [ ] 查看 platform-api 日志与 evalflow 后端日志确认异步任务成功；
- [ ] 验证通知中心红点与卡片内容，验证跳转链接可访问性；
- [ ] 固化真实验证截图与测试报告。

**开发与验证进度：** 尚未实施。
**下一步：** 依赖 Task 1~3。
