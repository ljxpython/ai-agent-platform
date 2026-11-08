# workflow_demo

确定流程与模型 Agent 组合的教学例。已注册到正式与 demo 配置；从 [开发指南](../../../../../docs/standards/runtime-agent-development-guide.md) 进入，按 [schemas.py](schemas.py) → [workflow.py](workflow.py) → [agent.py](agent.py) 阅读。

## 流程与职责

外层 StateGraph 为 prepare → 可选 confirm → route → approve/reject → respond → END。批准和拒绝分支都会继续到模型回答；这里的确认演示业务路由，**不能把 reject 分支当成外部写工具已被阻止的安全模板**。

输入支持 `message` 和标准 Chat `messages`，每轮提取最新 user/human 消息。显式 `requires_confirmation=True`，或 Chat 中包含“需要人工确认”，进入教学确认点。Resume 接受 approve/reject 或平台 HITL decisions envelope。使用当前返回的 interrupt ID 和同一 thread_id；非法决定返回 `workflow.invalid_resume` 并再次确认。

State 的验证字段是 `prepared_count`，用于证明恢复没有重复已完成的准备节点。

## 模型与恢复

`get_agent(config)` 绑定受信运行事实，模型连接在 respond 节点才获取，等待人工确认前不请求模型。正式运行使用受管 opaque reference；恢复时的私有引用由平台注入，浏览器不能自行构造。

当前 `workflow.py:build_graph()` 显式使用 `InMemorySaver()`，内层 Agent 使用 `checkpointer=True`。这是源码中保留的教学实现，不能据此宣称跨进程持久化或 Worker 重启恢复。新生产 Workflow 应遵循平台 checkpointer 生命周期，并补真实服务验证；本轮只修正文档，没有迁移此例的 saver。

## 如何验证

在应用目录运行：

```bash
uv run pytest tests/services/workflow_demo -q
uv run pytest tests/integration/test_workflow_demo_agent_server.py -m integration -q
```

可复制的本地调用以 [test_agent.py](../../../../../tests/services/workflow_demo/test_agent.py) 的 `test_workflow_demo_interrupt_resume_does_not_repeat_completed_step` 为准：显式注入 `BindableFakeChatModel`（`_runtime_model`）、本地测试身份、稳定 thread_id，并使用实际 interrupt ID。仅开启本地身份不会自动得到 fake 模型。

另读该文件中模型引用延迟获取、最新消息、条件分支、非法 Resume 和外层预算保持的测试。正式时间预算由受信 Worker attempt 提供，内层模型重建不能重新计时。集成测试需要隔离基础设施，环境按 [运行与验证](../../../../../docs/standards/runtime-service-onboarding-and-verification.md) 准备；命令列出不代表本轮已执行。
