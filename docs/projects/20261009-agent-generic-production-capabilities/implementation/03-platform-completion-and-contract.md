# Platform 完成续接、网关与契约

## 改动时间

2026-10-09

## 相关任务

- T05：平台完成交付、开始前授权与失响应对账
- T07：查询/日志/取消网关和审计
- T08：真实发布构建、回退、后端契约交接

## 改动文件

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/{background_tasks,background_completion}.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/{presentation/http.py,application/ports.py}`
- `apps/platform-api/src/platform_api/adapters/langgraph/{runtime_gateway_upstream,sdk_client}.py`
- `apps/platform-api/src/platform_api/core/{security/tokens.py,runtime_contract.py}`
- `apps/platform-api/src/platform_api/modules/{runtime_catalog/presentation/http.py,audit/http_resolution.py}`
- `apps/runtime-service/src/runtime_service/http/background_tasks.py`
- `apps/runtime-service/src/runtime_service/auth/platform.py`
- `docs/projects/20261009-agent-generic-production-capabilities/{frontend-handoff,engine-handoff}.md`

## 具体改动

### 1. 完成通知与开始前授权

Runtime 用固定 event/key 发送 HMAC delivery/authorization 请求。Platform 复用已有 `RunRequestsRepository` 与 `launch_runtime_run()`，在创建完成 Run 前重查项目、Thread、Agent、模型、工具和当前 actor；通知 Run 的 marker 在 graph factory 前验证，禁止模型/MCP/Workspace 初始化前绕过 Stop tombstone。HITL/Thread busy 返回 pending，不自动 approve 或 interrupt 活动 Run。

### 2. lost-ACK 降级

当本地没有完成 Run 回执时，`reconcile_only` 只读检查本地持久记录和已绑定事件，返回 `unknown`/`inflight`，绝不换 key 或再次 POST。post43 没有按幂等 key 查询原生 queued Run 的公开接口，因此 Worker 尚未进入 guard 的窗口仍无法确认 `run_id`；具体引擎接续和解除条件见 `engine-handoff.md`。

### 3. 公开任务网关

Runtime 和 Platform 各自校验 DTO、Thread/graph/scope 归属和当前 ACL。四个公开入口分别读取列表、详情、有界纯文本输出和持久取消意图；三个 delegation operation 互不替代，响应 `no-store`，私有 command/container/lease/fence/JWT/model 字段递归剥离。取消 202 只表示意图受理，cleanup 仍以 Task 查询为准。

### 4. 审计和安全错误

HTTP action 记录 `runtime.background_task.read`、`runtime.background_task.logs.read`、`runtime.background_task.cancel.requested`，内部 HMAC 回调记录 `runtime.background_task.delivery.checked` 与 `runtime.background_task.authorization.checked`。审计只保留受信 ID、scope、状态和安全 reason；存储/控制 503 对外固定为安全消息 `Background task unavailable`。

## 验证

- Platform 后台定向测试：21 passed、63 subtests，覆盖 operation 精确匹配、DTO/私有字段、HMAC 时间窗与正文、审计、拒绝/撤权/跨项目、reconcile-only 和当前 ACL。
- 独立 API/Worker、真实受管模型和 usage 链路通过；完成 Run 只创建一次并与源 Run 分开计量。
- 旧 foreground、HITL、Stop、inbox、Usage 和公开错误投影按专项 Phase 记录回归。
- 后端 Final 尚未写入：B01 缺失时不能宣称所有接受回执都可回查，也不能宣称生产拓扑已启用。

## 注意事项

前端只消费 `frontend-handoff.md` 中冻结的 v1 DTO 和状态语义。页面不得把 delivery accepted 当作模型 Run success，也不得在 unknown 后自动创建新任务或新通知 Run。
