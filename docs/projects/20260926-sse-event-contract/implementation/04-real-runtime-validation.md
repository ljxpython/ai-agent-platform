# 04 真实 Runtime 与前端容量验证

日期：2026-09-27

## 已执行

- 本地真实链路：`platform-web:3000 → platform-api:2142 → runtime-service:8123`。
- `PLATFORM_CHAIN_TEST=1 pnpm --dir apps/platform-web exec vitest run src/modules/chat/sdk-chain.test.ts`：1 passed，约 61 秒。覆盖普通 Run、断开后 state/history 水合、HITL interrupt/approve、终态读取和 checkpoint fork；命令计数与 Runtime 状态均来自真实服务。
- `RUN_SSE_REAL_E2E=1 SSE_CAPACITY_THREADS=1 SSE_CAPACITY_DURATION_MS=10000 ... playwright test e2e/sse-event-contract-real.spec.ts`：1 passed，30 次 state 访问，1 条流 ready。
- 同命令 `SSE_CAPACITY_THREADS=4`：1 passed，30 次 state 访问，4 条流 ready。
- 390px 真实浏览器视觉检查：`mobile-chat-refactor.spec.ts` 1 passed；修复会话头部窄屏两行布局后，Agent 选择器、对话/轨迹、操作按钮不再重叠，文案和交互保持不变，页面无横向溢出。

## 容量根因

- 容量页面和 8 条 SSE 都从 `http://127.0.0.1:3000` 发出，本地入口是 HTTP/1.1。Chromium 对同一 HTTP/1.1 origin 的长连接槽实测为约 6 条：`SSE_CAPACITY_THREADS=8` 时前 6 条占满连接，后 2 条无法完成 `handle.ready`，30 秒后报握手超时。
- 边界探针 `SSE_CAPACITY_THREADS=6` 没有握手失败，但 6 条长 SSE 占满连接后，后续同 origin 的 `/state` 请求无法发送，测试在 121 秒 Playwright 总超时；这与 HTTP/1.1 连接槽耗尽一致。
- Runtime 源码显示 `n-jobs-per-worker` 只创建 Run 执行 worker slot；`stream/events` 在 API 进程内注册 Redis-backed `thread_stream`，不占 Run worker slot。因此临时扩到 2/4 个同配置 worker 不会解决本次浏览器连接饥饿，临时 worker 已停止。
- `nextHopProtocol` 未提供 h2/h3 证据。容量门禁必须通过 HTTP/2 或 HTTP/3 origin 复测；30 分钟持续运行、8 活跃 Thread、堆增长和退出后资源归零仍未验证。

## 其他限制

- 未执行迁移、部署、Git 提交或分支操作。
- 未执行旧版本兼容矩阵；只验证新 Web、新 API 与当前锁定 Runtime 的组合。
