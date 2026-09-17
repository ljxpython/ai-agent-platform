# Platform API 与 Runtime 实施

## 改动时间
2026-09-17

## 相关任务
- 02 可信契约与审计
- 03 Runtime 执行

## 改动文件
- `apps/platform-api/src/platform_api/adapters/langgraph/threads_sdk_adapter.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- `apps/runtime-service/src/runtime_service/runtime/access_policy.py`
- `apps/runtime-service/src/runtime_service/runtime/contracts.py`
- `apps/runtime-service/src/runtime_service/runtime/resolver.py`
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/subagents.py`

## 具体改动

- Gateway 新增受控策略接口与 LangGraph SDK metadata 更新适配；创建线程默认 `review`。
- Gateway 在启动每个新 run 前从线程 metadata 读取策略，覆盖浏览器提供的值，计算 v3 Context hash 后再签发 delegation。
- Runtime 只在 delegation/hash 验证成功后使用 `access_policy` 构造 Deep Agents `interrupt_on`。`workspace_write` 仅移除 `write_file`、`edit_file`、`execute` 的审批项，其余审批保持不变。
- Showcase 主 agent 与 general-purpose 子 agent 使用同一策略，避免子任务仍重复弹窗。

## 验证
- Platform API 路由矩阵、SDK adapter 与策略单元测试：通过。
- Runtime Context/策略单元测试及 Showcase 写文件免审 graph 测试：通过。
- Docker 命令真实执行用例：Docker daemon 启动后通过。
