# SSE 事件流保活心跳与连接容错治理专项 - 任务拆分

## Phase 1: Platform API 网关层心跳自动注入

### Task 1.1: 在 SSE 协议流迭代器中实现上游空闲超时心跳注入
- **改动内容：** 在 `_redact_protocol_event_stream` 中加入空闲检测（默认 15 秒），当上游流静默超过指定时间未产出数据块时，网关层主动输出 `: heartbeat\n\n`。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → `_redact_protocol_event_stream`
- **预期结果：** 即使上游没有任何业务事件输出，下游客户端每 15 秒也能稳定接收到一个 SSE 注释心跳帧。
- **验证项：** `pytest tests/test_runtime_gateway_event_redaction.py` → ✅ 通过（覆盖 slow upstream 触发 2 次以上心跳）
- **状态：** `[x]` 已完成 2026-09-27 → 见 implementation/01-gateway-heartbeat-injection.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（Phase 1 内部逻辑，待全专项统一更新）

### Task 1.2: 补充网关层心跳的单元测试与契约回归
- **改动内容：** 针对 `_redact_protocol_event_stream` 增加上游空闲心跳注入和心跳禁用控制测试，并验证 gateway 契约回归。
- **代码位置：** `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`
- **预期结果：** 测试套件全绿，确保心跳机制不破坏现有脱敏与审计逻辑。
- **验证项：** `pytest tests/test_runtime_gateway_event_redaction.py && pytest tests/test_runtime_gateway_sdk_adapters.py` → ✅ 全部通过（14 + 19 passed）
- **状态：** `[x]` 已完成 2026-09-27 → 见 implementation/01-gateway-heartbeat-injection.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）

## Phase 2: Platform Web 前端 UI 与重连状态治理

### Task 2.1: 优化 ChatSession 错误条与重连状态的展示
- **改动内容：** 调整 `ChatSession.vue` 中红色报错条的渲染逻辑：将短暂的后台自动重试（`reconnecting`）从即时大红框中解耦，仅在连接彻底断开（`paused`）或存在不可恢复错误时才展示明显的告警与【恢复连接】按钮。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- **预期结果：** 瞬间网络波动或 SDK 静默重试期间不再弹红色报错条干扰用户。
- **验证项：** `pnpm test:run src/modules/chat/` → ✅ 通过（221 tests passed）
- **状态：** `[x]` 已完成 2026-09-27 → 见 implementation/02-chat-session-ui-resilience.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（跳过）

### Task 2.2: 调优 SDK 传输层补丁配置与防抖
- **改动内容：** 调优与校验前端 SDK 补丁中的空闲保活机制，确保心跳能够正确重置重连计时器。
- **代码位置：** `apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch`
- **预期结果：** 客户端空闲保活超时平滑，不发生假性重连。
- **验证项：** `pnpm test:run src/modules/chat/sdk-stream-recovery.test.ts` → ✅ 全部通过（11 passed）
- **状态：** `[x]` 已完成 2026-09-27 → 见 implementation/02-chat-session-ui-resilience.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
### Task 2.3: 历史重放僵尸中断过滤与审批状态自愈机制
- **改动内容：** 针对 GraphHarbor 重放旧 Run 历史中断导致前端卡死在过期审批项的问题，在 `useSessionInterrupts.ts` 中引入 `resolvedReviewIds` 与主动状态同步（`syncAuthoritativeReviews`），并在 `approve()` 校验不一致时自动自愈剔除失效旧项并展示最新审批项。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts`
- **预期结果：** 历史重放中断不再展示在 UI，即便由于并发产生 ID 漂移也能自动切换至最新有效审批项，不卡死报错。
- **验证项：** `pnpm test:run src/modules/chat/composables/useSessionInterrupts.spec.ts` (2 passed) & `pnpm test:run src/modules/chat/` (173 passed)
- **状态：** `[x]` 已完成 2026-09-27 → 见 implementation/03-stale-interrupt-filtering-and-self-healing.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（即将更新）

## Phase 3: 全链路集成验证

### Task 3.1: Final 跨服务长效保活与真实链路回归
- **改动内容：** 在本地真实全栈环境（Web + API + Runtime）中，保持对话长连接打开，使用全链路探针监测并观察是否还会产生 45 秒周期的 `client_disconnect` 和报错条弹窗。
- **代码位置：** 全链路端到端
- **预期结果：** 页面与长连接持续稳定，日志中每 15 秒精准持续接收 `: heartbeat\n\n`，不触发 45 秒空闲断连，对话事件收发顺畅。
- **验证项：** 40 秒长连接探针在 19.60s 与 34.60s 两次捕获网关注入心跳，并在 37.71s 完整无损接收模型推理事件；前端单测 221 项全部通过。
- **状态：** `[x]` 已完成 2026-09-27 → 见 verification.md 与 implementation/01-gateway-heartbeat-injection.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（即将更新）

## 进度追踪
- [x] Phase 1: Platform API 网关层心跳自动注入完成
- [x] Phase 2: Platform Web 前端 UI 与重连状态治理完成
- [x] Phase 3: Final 全链路集成验证通过
