# Runtime/API Plan Mode 实施记录

## 改动时间

2026-10-09

## 相关任务

- T01/T02：锁版本 Spike 与契约冻结
- T10-T14：Runtime 公共能力
- T20-T23：Platform API 安全契约
- T40：Runtime/API 定向验证

## 改动文件

Runtime：

- `apps/runtime-service/src/runtime_service/runtime/planning.py`
- `apps/runtime-service/src/runtime_service/middlewares/plan_mode.py`
- `apps/runtime-service/src/runtime_service/tools/plan_mode.py`
- `apps/runtime-service/src/runtime_service/runtime/contracts.py`
- `apps/runtime-service/src/runtime_service/runtime/resolver.py`
- `apps/runtime-service/src/runtime_service/runtime/capabilities.py`
- 四个 Agent 组合根、DearFlow memory middleware、Runtime auth/scheduled 导出

Platform API：

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/planning.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py`
- `apps/platform-api/src/platform_api/core/runtime_contract.py`
- `apps/platform-api/src/platform_api/core/security/tokens.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/thread_access.py`
- `apps/platform-api/src/platform_api/modules/scheduled_tasks/service.py`

测试：

- Runtime 计划契约、中间件、DearFlow 和四图组合测试
- Platform API 计划网关和 fork/bootstrap 测试
- 隔离 HTTP/Worker 计划审批 E2E fixture

## 关键改动

### 1. Runtime 状态与工具门禁

`RuntimeContext` 增加严格布尔 `plan_mode` 和服务端绑定的 `plan_execution_id`，Context hash 升为 v6。`PlanSnapshot` 只保存当前 Markdown 草稿和 revision/hash；`PlanModeMiddleware` 在模型工具列表和实际 ToolCall 两侧同时拒绝越权，状态工具必须独占批次，子图不暴露计划控制工具。

三个公共工具为 `enter_plan_mode`、`save_plan`、`submit_plan`。审批使用原生 `interrupt(agent_plan_review)` 与人工 `input.respond`；没有模型可调用的 `approve_plan`。批准只解除规划附加限制，原 `execution_mode`、`access_policy` 和工具 HITL 保持不变。

### 2. 四图接线与隐式副作用

DearFlow、Showcase、Reference、Workflow 均接入公共能力并声明 `plan_mode` capability。规划期间自动记忆候选写入跳过；受控 checkpoint、审计、usage 和既有缓存边界保持不变。Workflow 组合根复用共享模型 builder/checkpointer，避免恢复时重新生成模型引用。

### 3. Platform API 审批与公开投影

入口只接受公开 `plan_mode`，客户端不能提交 `runtime_plan`、`agent_plan`、批准人或 `plan_execution_id`。API 服务端生成执行链 ID，RunRequests 保存 context/config 快照并用于 resume 幂等。审批校验当前 interrupt、plan ID、revision、hash、decision、ACL 和原 Run interrupted 状态；fork 建立新规划周期，cron 规划请求拒绝。

`runtime_plan` 只投影为有限 `agent_plan`，剥离执行 ID、绑定签名和私有字段；普通消息中同名用户内容不被误删。待审期间 `update_thread_state` 和受限 metadata 更新 fail closed。

## 验证

- Runtime 定向计划与四图组合：`58 passed`。
- Platform API 计划网关：`7 passed`。
- Platform API fork/bootstrap：`4 passed`。
- 隔离 HTTP/Worker、四图、Worker 重启、审批幂等：`1 passed`（受控 FakeChatModel）。
- Runtime/API Ruff：通过。
- 两服务 `src/` 与 `tests/` Python `compileall`：通过。
- `git diff --check`：通过。

## 交付时限制与后续结果

- 本记录对应首轮实现，后续真实外部模型、性能与封锁恢复已补齐，见 [后端验证收口](03-backend-validation.md) 和 `../verification.md`；Platform Web 浏览器仍由同事完成。
- `platform-api/tests/test_run_requests.py` 的旧 `project-1` fixture 已补齐模型恢复策略 mock 并通过回归，生产 UUID 校验没有放宽。
- 既有 Runtime Showcase wrapup 和 HEAD monkeypatch 基线问题未在本次范围修复。
