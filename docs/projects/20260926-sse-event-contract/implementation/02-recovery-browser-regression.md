# 首次握手恢复与受控浏览器回归

## 改动时间
2026-09-26

## 相关任务
- S1、S4—S11

## 改动文件
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
- `apps/platform-web/src/modules/chat/sdk-stream-recovery.test.ts`
- `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.spec.ts`
- `apps/platform-web/src/layouts/WorkspaceLayout.spec.ts`
- `apps/platform-api/tests/fixtures/sse_contract_server.py`
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`
- `apps/platform-web/e2e/sse-event-contract.spec.ts`

## 具体改动

1. `useChatSession.ts` 的 `bindConnectionState` 监听增加 `hydrated` 触发。真实 ChatPage 首次 SSE 握手返回 410 时，ThreadStream 可能晚于初始 watcher 创建；水合完成后重新绑定，才能收到 paused 并进入单飞恢复。受控页面用例先复现订阅计数停在 1，修复后恢复订阅且无业务命令。
2. `useChatSession.spec.ts` 覆盖状态读取期间出现新 Run 时旧 410 快照作废、取消 ACK 后继续等待真实终态；`useSessionInterrupts.spec.ts` 验证审批 ID 变化时不提交。`sdk-stream-recovery.test.ts` 使用安装 SDK 覆盖 5 次重试、30 秒预算重置、45 秒无字节与心跳、双物理流选择恢复；真实 `ThreadStream` 的晚订阅回放、跨 namespace 同 event_id 及并集旋转 503 后手动恢复也通过（11 passed）。
3. 隔离夹具的 `advance` 可推进合法 Protocol 事件、原始分片或显式 EOF，`V13UI` 只让第一次订阅过期。浏览器测试覆盖真实 API/auth/router、安装 SDK、真实 ChatPage 的 A→B→A 保活、撤权清理、UI 登出后的作用域清理、EOF 重连和 410 恢复；同轮过程/思考/工具/正文、根命名空间重复事件、CRLF 分片及坏帧安全关闭有断言。所有命令计数均为零；受控上游不代表 Runtime。`WorkspaceLayout.spec.ts` 另验证项目路由变化清池。
4. `test_runtime_gateway_http_matrix.py` 的线程流旧样例改为合法 Protocol 外层，保留 Run 流原样例；路由矩阵重跑 1 passed、283 subtests passed。
5. 当前桌面与手机宽度截图由 Playwright `testInfo.outputPath()` 保存为测试产物，仅供本轮布局观察。实施前基线不存在，不能作前后视觉等价证明；390px 顶栏有文字/按钮重叠，本期未改受保护 UI。

## 验证与限制
- API SSE 定向：11 passed，110 subtests passed；Web 全量 Vitest：93 files / 396 passed、1 skipped；Web typecheck、文档检查及 production build 通过。
- 受控浏览器全文件 15 passed（新增覆盖见 `03-queue-and-fixture-isolation.md`）；API 全量 288 passed、14 skipped、5 failed（SSE 路由矩阵旧夹具已修正并定向通过，剩余失败属追踪/委托专项）。
- 全仓 Web lint 有未触及组件的 7 个错误；专项改动文件 lint 0 error。SDK patch 的生成文本使 `git diff --check` 报空格诊断。
- 真实三服务、HTTP/2 或 HTTP/3 容量、30 分钟稳定性及三段脱敏样例未验证。新 GraphHarbor 隔离库需要迁移初始化，超出本期授权。
