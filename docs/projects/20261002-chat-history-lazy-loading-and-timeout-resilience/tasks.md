# 长会话断流恢复解耦与历史快照按需懒加载治理 - 任务拆分

## Phase 1: 前端断流恢复解耦与错误隔离

### Task 1.1: 重构 useChatSession.ts 断流恢复逻辑
- **改动内容：** 从 `recoverExpiredStream()` 中移除对 `service.history(id)` 的强制阻塞等待，改为仅阻塞拉取轻量级的 `service.state(id)`；history 作为非阻塞后台异步预热，错误静默软降级，绝不进入 `fail(cause)`。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts` → `recoverExpiredStream()`
- **预期结果：** 当发生流断开（410 / cursor_expired）重连时，以毫秒级恢复当前最新状态并重连事件流，不再受 3.4 MB 巨型 history 超时拖累。
- **验证项：** `pnpm test:run src/modules/chat/composables/useChatSession.spec.ts` → ✅ 24/24 passed（含新增 504 容错单测）
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-chat-history-lazy-loading-and-resilience.md](implementation/01-chat-history-lazy-loading-and-resilience.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### Task 1.2: 审查与加固 ChatSession.vue 时间旅行懒加载与错误隔离
- **改动内容：** 移除 `loadHistory` 中将错误赋值给全局 `localError.value` 导致顶部弹大红条的行为；增加抽屉展开守卫（`if (drawerOpen.value)`），未展开抽屉时绝不发无效的巨型 history 请求。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue` → `loadHistory()` & watch
- **预期结果：** 用户不点时间旅行时不产生任何 3.4 MB 巨型快照网络流量；发生异常时主界面依然平稳可用，零红色断线报错横幅。
- **验证项：** `pnpm test:run src/modules/chat/components/`（19 套/67 passed）与 `pnpm build`（打包成功） → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-chat-history-lazy-loading-and-resilience.md](implementation/01-chat-history-lazy-loading-and-resilience.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

---

## Phase 2: 后端网关超时保护与单测防护

### Task 2.1: Platform API 历史查询网关超时裕量与异常映射加固
- **改动内容：** 审查 `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` 与 `service.py`，确保针对 history 等重快照操作具备合理的超时容错，脱敏函数不发生深层递归异常。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `get_thread_history()`
- **预期结果：** 在并发或重载场景下网关具备自我保护，错误 Envelope 格式严格规范。
- **验证项：** `apps/platform-api/.venv/bin/pytest apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py` → ✅ 21 passed in 3.62s
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-chat-history-lazy-loading-and-resilience.md](implementation/01-chat-history-lazy-loading-and-resilience.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

---

## Phase 3: 全链路回归与长步骤压测

### Task 3.1: 100+ 步长会话断流与重连真实环境回归
- **改动内容：** 针对会话 `6f2d84e1-3ecd-4ce2-b732-f5981996d161`（101 步），在前端模拟断流重连，验证页面瞬时恢复无任何 504 报错，打开时间旅行抽屉可平滑加载。
- **预期结果：** 前端生产打包 `pnpm build` 无报错，页面丝滑恢复，零红色假性报错弹窗。
- **验证项：** 前端全量单测与构建检查全绿，真实会话请求测试通过。
- **状态：** `[x]` 已完成 2026-10-02
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## 进度追踪
- [x] Phase 1 前端断流恢复解耦与错误隔离
- [x] Phase 2 后端网关超时保护与单测防护
- [x] Phase 3 全链路回归与长步骤压测
