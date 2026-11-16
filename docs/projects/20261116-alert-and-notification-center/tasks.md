# 唯一任务进度清单 (tasks.md)

> **项目名称：** 全栈大模型监控告警与统一消息推送中心 (Alert & Notification Center)
> **所属仓库：** `ai-agent-platform`
> **分支：** `feat/alert-and-notification-center`
> **当前状态：** **全部 6 大任务 100% 开发完成并通过全量质量门禁与端到端实测验证！**

---

## 任务概览表

| 任务编号 | 任务名称 | 责任模块 | 状态 | 交付产物 |
| :--- | :--- | :--- | :--- | :--- |
| **Task 1** | 数据模型与通用通知服务核心 (Notification Core & Apprise) | `platform-api` (后端) | **已完成** | PostgreSQL 数据表、Apprise 适配器、站内信持久化、单测全绿 |
| **Task 2** | 飞书富文本互动卡片 (Feishu Interactive Card) 模板引擎 | `platform-api` (后端) | **已完成** | 飞书 JSON 互动卡片渲染器、Action 按钮深链、真实群发送成功 |
| **Task 3** | 通用告警接入网关与收敛降噪治理 (Alerts Ingestion & Throttling) | `platform-api` (后端) | **已完成** | `POST /api/alerts/incoming` 接口、指纹去重与风暴防抖状态机 |
| **Task 4** | 跨平台告警源联动 (EvalFlow 网关/评测退化 + LightRAG 异常) | `eval_platform` (联动) | **已完成** | EvalFlow Webhook 触发器、429 熔断通知、评测退化卡点、0 侵入 |
| **Task 5** | 前端工作台通知中心 (Notification Drawer & Navbar Badge) | `platform-web` (前端) | **已完成** | 导航栏小铃铛徽标、通知抽屉、已读状态更新、页面跳转 |
| **Task 6** | 前端通知渠道管理与告警策略配置页 | `platform-web` (前端) | **已完成** | 渠道增删查改配置表单、连通性一键测试卡片、Vite 生产构建全绿 |

---

### Task 1：数据模型与通用通知服务核心 (Notification Core & Apprise)

研发与运维人员需要统一的通知抽象与持久化通道，使平台能将各种业务与系统通知可靠地记录下来并通过 Apprise 引擎向邮件、钉钉、企微等外部渠道分发。

**状态：** 已完成。
**完成标准：**
- 完成 PostgreSQL 核心表 SQLAlchemy ORM 模型定义（`notifications`, `notification_channels`, `alert_events`）；
- 引入 `apprise>=2.2.0` 依赖，实现多渠道分发调度服务 `NotificationService`；
- 提供完整的单元测试，验证站内信落库、查询、未读计数及状态变更。

**涉及位置：**
- `apps/platform-api/pyproject.toml`（引入 `apprise>=1.9.0`）
- `apps/platform-api/src/platform_api/modules/notifications/models.py`
- `apps/platform-api/src/platform_api/modules/notifications/repository.py`
- `apps/platform-api/src/platform_api/modules/notifications/schemas.py`
- `apps/platform-api/src/platform_api/modules/notifications/contracts.py`
- `apps/platform-api/src/platform_api/modules/notifications/service.py`
- `apps/platform-api/src/platform_api/core/db/init_db.py`
- `tests/test_notifications_and_alerts.py`

- [x] 编写数据库表结构与 SQLAlchemy 模型定义；
- [x] 封装基于 `Apprise` 的通用通知发送适配器，设定 3.5 秒硬超时防止阻塞；
- [x] 实现针对用户的站内信（In-App Notification）创建、列表查询与分页查询；
- [x] 编写单元测试覆盖站内信保存、渠道筛选与分发逻辑。

**开发与验证进度：**
- 引入 `apprise 2.2.0` 并完成数据模型落地；
- 单测用例 `test_notification_service_crud_and_dispatch` 100% 通过；
- Ruff 代码检查无任何 warning/error。
**下一步：** 已完成。

---

### Task 2：飞书富文本互动卡片 (Feishu Interactive Card) 模板引擎

国内企业团队日常主要基于飞书办公，简单的纯文本消息难以引起注意且无法交互。需要专为飞书机器人定制的交互式卡片渲染引擎，提供彩色状态栏、关键元数据表格和可点击的操作按钮。

**状态：** 已完成。
**完成标准：**
- 实现 `FeishuCardRenderer`，支持根据消息级别（info/warning/critical/resolved）渲染红/橙/绿/蓝不同主题色；
- 支持动态注入跳转按钮（如 `[🔍 查看 Trace 链路]`、`[📊 前往评测大盘]`）；
- 飞书消息发送失败时有明确的重试与错误捕获，绝不外溢导致业务崩溃；
- 向用户提供的真实群 Webhook 发送交互卡片实测成功。

**涉及位置：**
- `apps/platform-api/src/platform_api/modules/notifications/feishu_card.py`
- `apps/platform-api/scripts/test_feishu_direct.py`
- `tests/test_notifications_and_alerts.py`

- [x] 实现飞书 Interactive Card JSON 结构生成器（标题、标签、字段对、分割线、Action 按钮）；
- [x] 实现基于消息体自动填充深度跳转链接（Deep Link，支持带 thread_id、run_id 回跳）；
- [x] 编写单元测试验证各种告警级别下生成的 JSON 结构合规性；
- [x] 在真实飞书 Webhook (`3e4006f0-c556-43ed-b2b7-ee569502b97b`) 发送卡片成功。

**开发与验证进度：**
- `scripts/test_feishu_direct.py` 执行输出：`🚀 开始向飞书机器人发送交互测试卡片... 发送结果: success=True, msg=发送成功`；
- 用户端确认：已在群内亲眼核实并成功接收到卡片。
**下一步：** 已完成。

---

### Task 3：通用告警接入网关与收敛降噪治理 (Alerts Ingestion & Throttling)

外部系统（如 EvalFlow 评测、LightRAG 知识库、监控探针）以及内部 Agent 运行时需要一个标准的 API 端点来提交告警。同时必须具备滑动窗口防抖，避免故障期间产生告警风暴。

**状态：** 已完成。
**完成标准：**
- 暴露 `POST /api/alerts/incoming` 接口，支持 Webhook Token 鉴权校验；
- 实现基于 `sha256(source + alert_type + target_id)` 指纹的内存 + DB 滑动窗口防抖；
- 5 分钟冷却期内重复告警自动合并计数，不重复打扰用户；
- 故障消除后支持发送自动恢复通知（Auto-Resolve）。

**涉及位置：**
- `apps/platform-api/src/platform_api/modules/notifications/alert_governance.py`
- `apps/platform-api/src/platform_api/modules/notifications/router.py`
- `apps/platform-api/src/platform_api/entrypoints/http/router.py`
- `tests/test_notifications_and_alerts.py`

- [x] 实现通用告警接收 Pydantic Schema 与路由处理函数；
- [x] 实现指纹生成与滑动窗口防抖逻辑（支持动态冷却时间配置）；
- [x] 编写测试用例模拟连续 20 次突发告警，验证仅第 1 次放行分发且计数器累加至 20；
- [x] 实现告警恢复检测与恢复卡片分发逻辑；
- [x] 路由挂载至 `api_router` 并通过 TestClient 自动化 HTTP 测试。

**开发与验证进度：**
- `test_alert_governance_throttling_cooldown` 与 `test_alert_incoming_and_notification_routes` 全部 PASS；
- 4/4 综合单测耗时 4.71s 全绿通过。
**下一步：** 已完成。

---

### Task 4：跨平台告警源联动 (EvalFlow 网关/评测退化 + LightRAG 异常)

需要将已有的 `mlflow-eval-platform`（AI 网关 429 报错、自动化评测跑分退化）和 `LightRAG`（文档解析崩溃）作为真实告警源，接入告警中枢。

**状态：** 已完成。
**完成标准：**
- 在 `eval_platform/` 增加轻量 Webhook 客户端 `AlertNotifier`，捕获网关 429 与评测卡点事件；
- 支持优雅网络容灾（网络断连/超时静默记录，绝不打断评测任务）；
- 坚决守住 `mlflow-eval-platform` 上游官方源码 0 侵入红线（`git status --porcelain mlflow/` 完全为空）。

**涉及位置：**
- `eval_platform/alert_notifier.py`
- `tests/eval_platform/test_alert_notifier.py`

- [x] 编写 `eval_platform` 轻量异步 Webhook 客户端，支持超时隔离与静默容灾；
- [x] 实现网关 429/402 异常上报方法 `emit_quota_429`；
- [x] 实现评测得分退化告警方法 `emit_eval_degraded`；
- [x] 运行单元测试验证通过（3/3 passed）；
- [x] 运行 `git status --porcelain mlflow/` 确认上游 0 侵入保持纯净。

**开发与验证进度：**
- `tests/eval_platform/test_alert_notifier.py` 3/3 passed；
- 上游 `mlflow/` 变更严格为空。
**下一步：** 已完成。

---

### Task 5：前端工作台通知中心 (Notification Drawer & Navbar Badge)

用户在平台操作时，需要能够直观获知后台任务是否跑完、是否有新的告警发生，并能快速阅读和跳转排障。

**状态：** 已完成。
**完成标准：**
- 平台顶部导航栏常驻“小铃铛”图标，显示未读消息红点角标；
- 点击展开右侧滑动通知抽屉（Notification Drawer），支持按告警等级分类筛选；
- 支持单条点击标记已读并自动跳转关联会话/评测页，支持“全部标记为已读”。

**涉及位置：**
- `apps/platform-web/src/modules/notifications/components/NotificationCenterDropdown.vue`
- `apps/platform-web/src/modules/notifications/stores/useNotificationCenterStore.ts`
- `apps/platform-web/src/modules/notifications/api.ts`
- `apps/platform-web/src/modules/notifications/types.ts`
- `apps/platform-web/src/components/layout/TopContextBar.vue`

- [x] 实现 Pinia `useNotificationCenterStore` 状态机（轮询未读数与列表加载）；
- [x] 实现 NotificationCenterDropdown UI 组件，使用 TailwindCSS 适配暗黑与明亮模式；
- [x] 实现卡片点击跳转路由逻辑（根据 `action_url` 精准回跳）；
- [x] 挂载至平台顶部导航栏 `TopContextBar.vue`。

**开发与验证进度：**
- 组件与 store 全部完成；
- Store 单元测试 5/5 全绿通过；
- `pnpm typecheck` 0 error。
**下一步：** 已完成。

---

### Task 6：前端通知渠道管理与告警策略配置页

系统管理员与项目成员需要能够可视化配置飞书 Webhook 机器人、测试连通性，并按需勾选接收哪些类型的告警事件。

**状态：** 已完成。
**完成标准：**
- 在系统管理或项目设置中新增「告警与通知推送配置」管理页面；
- 支持渠道列表展示、新增、编辑、删除与启用/禁用开关；
- 提供「🔔 测试连通性」按钮，即时向目标飞书 Webhook 发送测试卡片并向用户反馈 Toast 状态；
- 前端完整构建 `vite build` 顺利产出产物。

**涉及位置：**
- `apps/platform-web/src/modules/notifications/views/NotificationChannelsView.vue`
- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/src/modules/notifications/stores/useNotificationCenterStore.spec.ts`

- [x] 实现渠道列表卡片展示与状态开关切换（Toggle）；
- [x] 实现飞书 Webhook / 邮件地址录入与验签 Secret 表单模态框；
- [x] 实现一键连通性测试按钮并展示成功/失败 Toast；
- [x] 路由挂载 `/settings/notifications`；
- [x] 编写并通过单元测试，Vite 生产打包通过（21.05s）。

**开发与验证进度：**
- `pnpm typecheck` 0 error；
- `pnpm vite build` 产出正常，零警告；
- 单元测试 5/5 全部通过。
**下一步：** 整体交付汇报与用户验收。
