# LangGraph v3 默认消费与 DeltaChannel 评估 - 任务拆分

## Phase 1：基线冻结

### Task 1.1：冻结版本和 v3 入口清单
- **改动内容：** 记录 `langgraph==1.2.11`、GraphHarbor 版本、Platform API 当前 v2/v3 默认值；列出 web 的 Run 创建、流订阅、resume、join/replay 入口。
- **代码位置：** `apps/platform-web/src/`、`apps/platform-api/src/platform_api/modules/runtime_gateway/`、`apps/runtime-service/pyproject.toml`、`uv.lock`
- **预期结果：** 每个入口都有明确版本来源、消费者和回退方式。
- **验证项：** 静态检索、现有测试清单、v2/v3 原始事件样本。
- **状态：** `[x]` 已完成 2026-10-04 → 版本锁定和入口清单见 `frontend-handoff.md`

### Task 1.2：建立 checkpoint 体积基线
- **改动内容：** 只读统计真实 PostgreSQL checkpoint 的线程长度、字节量、图类型和增长趋势；补充离线合成基线。
- **代码位置：** `apps/runtime-service/scripts/` 或独立测量脚本；不得修改生产 checkpoint 格式。
- **预期结果：** 有可复跑的测量命令和原始结果，明确是否存在 O(N²) 写放大。
- **验证项：** 至少一个长会话、一个普通会话、一个含子图/工具调用的会话。
- **验证项：** `uv run python scripts/measure_delta_channel_postgres.py --rounds 200`，并只读汇总现有 checkpoint 表 → ✅ 已完成
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/02-delta-spike.md`

## Phase 2：P0 v3 默认消费与前端交接

### Task 2.1：后端默认 Run 版本统一为 v3
- **改动内容：** 将 Platform API 的新 Run、stream 和 resume 默认版本统一为 v3；保留显式 v2 和历史 v2 Run 兼容。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`、`apps/platform-api/tests/test_run_requests.py`
- **预期结果：** 缺省请求和缺省 resume 上送 `version: "v3"`，显式 v2/v3 原样保留。
- **验证项：** `uv run pytest -q tests/test_run_requests.py` → ✅ 27 passed, 2 subtests passed
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/01-backend-v3-defaults.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已登记项目
  - [ ] docs/FEATURES.md 已更新（跳过：既有运行能力的默认值修复）
  - [x] docs/CHANGELOG.md 已更新

### Task 2.2：前端 v3 消费交接
- **改动内容：** 输出 Run 创建、流订阅、resume、join/replay 的版本来源、v3 事件映射、终态和验收清单；不修改前端源码。
- **代码位置：** `docs/projects/20261004-langgraph-v3-delta-evaluation/frontend-handoff.md`
- **预期结果：** 前端同事可按文档逐入口完成 v3 消费和浏览器验收。
- **验证项：** 静态入口核对、既有 v3 样本和跨服务契约核对 → ✅ 已完成
- **状态：** `[x]` 已完成 2026-10-04 → 见 `frontend-handoff.md`
- **合规检查：**
  - [x] 交接文档完成
  - [x] 入口和验收项已覆盖
  - [x] tasks.md 状态已更新
  - [ ] docs/FEATURES.md 已更新（跳过：前端源码未改）
  - [x] docs/CHANGELOG.md 已更新

### Task 2.3：v3 入口收口和兼容门禁
- **改动内容：** 校验 resume 沿用原 Run 版本，清理默认值冲突，补齐 v2/v3 契约测试。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`、相关测试。
- **预期结果：** 不发生静默版本漂移；v2/v3 均可按契约工作。
- **验证项：** resume、join/replay、410/断线、错误 envelope 和审计事件。
- **验证项：** `tests/test_run_requests.py` 覆盖默认 v3、显式 v2/v3、历史 v2 resume 和缺失版本 fallback → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/01-backend-v3-defaults.md`

### Task 2.4：前端 v3 消费适配与防洪加固
- **改动内容：**
  1. 在 `run-actions.ts` 的 `platformCommand` 中增加 `version` 参数白名单，支持显式传递 `version: "v2"` 回滚；
  2. 在 `useTranscriptMessages.ts` 中对 `values` 事件高频与大包增加消息长度与标识比对防洪，避免每帧无脑深拷贝与响应式轰炸；
  3. 补齐与回归前端单测，通过 TypeScript 类型检查与全量构建。
- **代码位置：**
  `apps/platform-web/src/modules/chat/run-actions.ts`、
  `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`、
  `apps/platform-web/src/modules/chat/run-actions.test.ts`、
  `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`
- **预期结果：**
  前端支持显式传参；values 监听具备防洪屏障；前端单测与构建全绿。
- **验证项：** `pnpm test:run`、`pnpm typecheck`、`pnpm lint`、`pnpm build` → ✅ 48 passed, 0 errors, 生产构建全绿
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/03-frontend-v3-adaptation.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（Task 完成后同步更新）
  - [ ] docs/FEATURES.md 已更新（跳过：既有会话流式消费能力的加固与回退支持）
  - [x] docs/CHANGELOG.md 已更新（fix/perf 分组）

## Phase 3：P1 DeltaChannel Spike

### Task 3.1：实现隔离 Delta reducer Spike
- **改动内容：** 为显式 `StateGraph` 建立测试状态和 DeltaChannel reducer，覆盖批处理不变性、消息追加、删除/替换、工具调用和并行写入。
- **代码位置：** `apps/runtime-service/tests/` 或隔离 Spike 模块；不得改生产 AgentState。
- **预期结果：** Delta 与完整快照在所有固定夹具上的最终状态一致。
- **验证项：** reducer 单测、随机批次等价性、interrupt/resume、线程隔离。
- **验证项：** `uv run pytest -q tests/test_delta_channel_spike.py` → ✅ 2 passed
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/02-delta-spike.md`
- **合规检查：**
  - [x] Spike 实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] docs/FEATURES.md 已更新（跳过：隔离测试工具，不改变生产能力）
  - [ ] docs/CHANGELOG.md 已更新（跳过：test/tooling）

### Task 3.2：对比 checkpoint 写入与恢复成本
- **改动内容：** 对相同 200 轮和真实采样夹具分别运行完整快照、Delta 不同 `snapshot_frequency`，记录写入字节、恢复耗时和查询耗时。
- **代码位置：** Spike 脚本、测量结果和 `implementation/` 记录。
- **预期结果：** 得到可复跑的对比表，不引用官方数字替代本项目数据。
- **验证项：** 本地持久化后端；可用时补真实 Agent Server/PG。
- **验证项：** 离线脚本和本地 PostgreSQL 脚本均完成 200 轮对比 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/02-delta-spike.md`

### Task 3.3：兼容性和回滚门禁
- **改动内容：** 验证旧线程读取、worker 重启、checkpoint resume、`delta-channel-dump` 恢复和新线程迁移策略；升级锁定 `graphharbor==0.13.0.post38`。
- **代码位置：** `apps/runtime-service/tests/test_delta_channel_spike.py`、`apps/runtime-service/pyproject.toml`、`uv.lock`。
- **预期结果：** 明确 Adopt、Defer 或仅新线程启用；没有回滚证据不得生产采用。
- **验证项：** 升级/降级模拟、故障恢复、线程隔离、回滚产物检查。
- **验证项：** `uv run pytest -q tests/test_delta_channel_spike.py` 覆盖 worker 重启与 dump 回滚迁移 → ✅ 4 passed；门禁结论明确为 Defer
- **状态：** `[x]` 已完成 2026-10-04 → 见 `implementation/04-delta-rollback-gate.md`
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] docs/FEATURES.md 已更新（跳过：测试工具与门禁，不变更生产能力）
  - [ ] docs/CHANGELOG.md 已更新（跳过：test/tooling/dependency-patch）

## Phase 4：Final 验证

### Task 4.1：全范围验证和结论
- **改动内容：** 汇总 P0/P1 证据，更新项目状态和风险；不实施节点 timeout/error_handler/RunControl。
- **验证项：** platform-web 单测/typecheck/build、platform-api 定向测试、runtime-service 定向测试、浏览器 E2E、Delta 测量和回滚门禁。
- **验证项：** 后端定向测试、Spike、离线测量、前端防洪与回滚门禁已完成；浏览器真实链路验收待人工执行 → ⚠️ 进行中
- **状态：** `[ ]` 进行中 2026-10-04 → 见 `verification.md`

## 进度追踪

- [x] Phase 1 基线冻结
- [x] Phase 2 P0 后端默认 v3 与前端适配
- [x] Phase 3 P1 DeltaChannel Spike 与回滚门禁（完成，结论 Defer）
- [ ] Phase 4 Final 验证（等待人工浏览器真实链路验收）
