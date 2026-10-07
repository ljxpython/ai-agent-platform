# GraphHarbor 取消停止确认联验

## 时间与任务

2026-10-07；V01/V01-C、前端 H01 交接同步。进度看 [tasks.md](../tasks.md)，GraphHarbor 实现细节看其仓库 `docs/projects/20261007-worker-cancel-propagation/implementation/01-worker-cancel-propagation.md`。

## 相关改动

- `apps/runtime-service/tests/integration/test_model_resilience_worker.py`：默认 heartbeat 真实 HTTP adapter 取消，同时核对 ACK、wait=true、terminal.execution_stopped、lease 与 provider calls。
- `apps/runtime-service/tests/services/test_model_resilience_composition.py`：实际 DearFlow/Showcase 子图增加受控清理 barrier；wait 必须等待子图 finally 结束，确认后候选次数保持。Middleware 浅复制 model，测试由直接模型身份比较改为共享 `seen` 列表身份，精确计数不变。
- 本项目 README/plan/tasks/verification/frontend-handoff 与 CONTEXT/FEATURES/CHANGELOG、gateway/SSE 标准同步：post42 已验证但现役仍 post41，受理/确认/503 展示与混合版本边界明确。

## 结果与边界

默认配置仅 primary，ACK→lease 释放 0.123 秒；实际子图 provider/backoff/cooldown 9 项通过，普通组合回归 12 passed/9 opt-in skipped。证据见 [验证记录](../verification.md)。没有 Anthropic 真实 API、前端实装、现役升级或平台完整回退证据，整项仍 blocked。

## 前端任务书与经验补充

2026-10-07 用户要求详细说明并交同事实装，明确同意写经验库。继续扩展 `../frontend-handoff.md`，不新建重复接口事实源：核对编辑页 fill/load/save、模型 policy、两处 false/interrupt cancel、SDK 会话恢复、推荐问题触发与轨迹 completed；补齐对应 F01/F02 改动和测试落点。

额外记录真实网关表面：GraphHarbor ACK 经 Python SDK/`_normalize_ack()` 为平台 200/ok，503 经 `create_runtime_upstream_error()` 为 502，HTTP timeout 为 504；前端须结合请求 wait=true、同版本能力和权威 Run/lifecycle 确认。提前 interrupted 后未确认仍应可重试停止，不能被现有 !active 分支跳过。

平台 `docs/lessons/cross-service.md` 和 GraphHarbor `docs/lessons/runtime-persistence.md` 分别沉淀网关确认与 Worker 清理/租约经验，更新两仓库索引和上下文。仅做文档/源码映射检查，结果记录在 `../verification.md` 的交接 Phase；本轮没有前端代码、服务升级或新的功能测试。
