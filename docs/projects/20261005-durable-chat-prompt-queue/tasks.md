# Chat 持久消息队列 - 任务拆分

## Phase 1：现状与评审
- [x] T1 提交现有平台修复：`b85e00f`；hooks 通过，远程 refs hash 一致，提交后工作区干净。
- [x] T2 核对前端本地队列、API 幂等/透传、Worker claim/审批/取消、模型引用兑换并建立方案。
- [x] T3 人工评审：2026-10-05 用户回复“同意,开始实施”，批准 plan.md 全部治理范围。

## Phase 2：服务端
### T4 持久队列调度与操作
- [x] **改动内容：** queue_position 兼容迁移、Thread 锁下严格 FIFO、审批暂停与 resume 优先、pending 条件取消/调序、取消 running 的执行隔离。
- **代码位置：** GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/{models.py,run_store.py,production_worker.py,migrations/versions/}`；`libs/langhost/src/langhost/core_api.py`。
- **预期结果：** 多 Worker 不同 Thread 并行、同 Thread 不抢跑；pending 删除不污染当前状态；恢复审批不被队列堵住。
- **验证项：** 隔离 PostgreSQL 并发、审批、多 interrupt、取消/领取竞态、重试队首、迁移/回退门禁。

### T5 平台授权和队列契约
- [x] **改动内容：** 新队列操作受控网关、服务端预览脱敏、执行前权限复核及临时故障有界重试；复用既有 enqueue 和幂等。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/{application/service.py,presentation/http.py}`；Runtime 受信执行入口及 `auth/platform.py`；相应标准和测试。
- **预期结果：** 关页不影响执行；真实撤权不启动下一轮；网络故障不是 403；无模型图也受保护。
- **验证项：** 跨项目/Thread/用户拒绝、过期引用受信兑换、重复请求同 Run、丢响应重试、授权查询故障、模型/工具策略收回。

## Phase 3：前端
### T6 服务端队列接入
- [x] **改动内容：** enqueue 立即提交、服务端恢复列表、unknown 原 key/body 对账、删除/清空/调序/恢复草稿确认；旧本地项保留为未提交草稿。
- **代码位置：** `apps/platform-web/src/modules/chat/{run-actions.ts,composables/usePromptQueue.ts,composables/useChatSession.ts,components/ChatSession.vue,components/QueuedMessagesBanner.vue}`；`src/services/threads/session.service.ts`。
- **预期结果：** 页面没有 drain 消费职责；ACK 后任意离开都可执行；不按文本误去重，不覆盖草稿，不因取消未知重复发送。
- **验证项：** 同文本不同 message_id、分页恢复、账号/项目隔离、unknown/失败保留输入、审批 UI、取消冲突、两浏览器同步、后台 SSE 数量。

## Phase 4：交付
### T7 全链路验收与本地升级
- [ ] **改动内容：** 完成 GraphHarbor 双包门禁、迁移验证和本地升级；更新 lock、标准、CONTEXT/FEATURES/CHANGELOG 和实现记录。
- **代码位置：** GraphHarbor 发布配置；`apps/runtime-service/pyproject.toml`、`uv.lock`；`apps/platform-web/e2e/`、`apps/runtime-service/scripts/q5_message_acceptance.py`。
- **预期结果：** 实际安装版本具备修复，关闭所有测试页面后后台依旧按序终态。
- **验证项：** 见 verification.md；Final 在前述任务全完成后运行。远端生产环境未指定，不擅自部署。

## 进度
当前进行中：T3 已批准，T4 开始实施；其余任务持续推进。
