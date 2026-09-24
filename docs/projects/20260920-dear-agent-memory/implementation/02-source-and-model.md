# 多来源提取、边界验证与模型验收

2026-09-24；对应 R01/R03/R05/R06/R07、B01/B03。具体进度以 [tasks.md](../tasks.md) 为准。

## 代码与理由

- `apps/runtime-service/src/runtime_service/messaging/inbox.py:MessageInbox.memory_sources`：按 thread、target run、真实 sender、消息 ID 和交付状态查询来源。队列消息外形不能证明其作者，来源必须回到持久 inbox 核对。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py:MemoryContextMiddleware.aafter_agent`：主用户消息与本人队列消息最多合并 20 条/6000 字；同 run 两次尝试共用 180 秒。每条候选携带源消息 ID，模型只建议候选。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:MemoryStorage.begin_extraction/propose/finish_extraction`：批量来源按 run 认领，逐条校验来源 ID 与原文 quote，旧 run 不能覆盖新 run 展示状态。旧 JSON 投影补默认字段，候选、sources 和墓碑满额时暂停自动提取，人工管理继续。
- `apps/platform-api/src/platform_api/core/runtime_contract.py:reject_private_runtime_state` 与 `modules/runtime_gateway/application/service.py:_normalize_payload/RuntimeGatewayService.update_thread_state`：递归拒绝客户端伪造私有记忆来源、队列 claim 和技能快照；`adapters/langgraph/sdk_client.py` 不把私有来源发进公开 state/SSE。
- `apps/platform-api/tests/test_runtime_gateway_memory.py:MemoryGatewayTest.setUp`：简化 HTTP 夹具补充合成 request ID，使错误响应断言与正式请求中间件一致；未改正式错误处理逻辑。

## 验证

`test_memory_contract.py` 15 passed；`test_p6_governance.py`、`test_memory_access.py`、`test_context.py` 共 28 passed；Runtime 授权三模块 20 passed、5 skipped。Platform 六模块 50 OK。独立 MAOMAO 模型用合成资料验证候选原文、人工采纳和事实问答 1 passed。编译检查和 `git diff --check` 通过；详细命令与限制见 [verification.md](../verification.md)。

真实模型用例先前把同一异步客户端放在两个 `asyncio.run()` 中，第二次触发已关闭事件循环；改成一个事件循环后通过。该用例直接调用中间件与模型，尚未证明平台完整 run/SSE、部署性能或浏览器页面。
