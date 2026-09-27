# 后台队列与隔离夹具补验

## 改动时间
2026-09-26

## 相关任务
- S8、S9、S10、S11

## 改动文件
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/e2e/sse-event-contract.spec.ts`
- `apps/platform-api/tests/fixtures/sse_contract_server.py`

## 具体改动

1. 排队草稿持久化键加入当前用户 ID，同项目共享 Thread 的不同账号不再读取同一个未发送队列。现有同用户恢复方式保留。
2. 受控夹具新增每 Thread 的 Run 状态控制和查询；`reset` 释放旧 SSE 队列，以 generation 隔离上一用例的迟到关闭计数。全文件首次运行时旧队列造成 `open` 假阳性、事件投递给旧连接，修正后重跑通过。
3. 真实 ChatPage 测试覆盖 A 的 Run 结束时 B 可见，A 的排队消息不发送且 B 草稿不变；回到 A 后只发送一次。同轮两个同名工具分别失败、成功，两个结果可单独展开。
4. 浏览器通过真实 API 订阅发送同一 `event_id`、不同 namespace 且 sequence 2→1 的两帧；SDK 传输层按到达次序返回两条事件，未发业务命令。
5. ChatPage 会轮询真实消息列表路由；夹具补齐 `list_thread_messages` 只读响应。此前缺方法导致页面捕获 AttributeError 并显示收据读取失败，补齐后全文件重跑通过，服务日志仅有坏帧用例预期的 `invalid_json`。

## Phase 验证与限制
- 受控浏览器全文件：15 passed；新增队列、350ms 隐藏窗口与 namespace 用例均单独复跑通过。
- `ChatSession.vue` 与浏览器测试 ESLint：0 error，原组件 14 warnings；Web typecheck、夹具 Python 语法检查通过。
- 仍无实施前视觉基线、真实 Runtime 环境、HTTP/2 容量与三段脱敏样例。受控链路不计入真实三服务验收。
