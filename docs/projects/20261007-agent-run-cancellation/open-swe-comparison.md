# 源码对照与同事方案评估

## 核对范围与证据级别

核对日期：2026-10-07。平台源码基线 `bf47991b7592b19cbda1051c6a674623450318ae`；open-swe 基线 `ad417d64d91cc349d63d832c7b643637dc1774cf`；GraphHarbor checkout HEAD `f9bb32ed123110cb07d18cf9c5b76a7895c7b33e`。

下文 `open-swe:...` 和 `GraphHarbor:...` 均为对应仓库内的相对路径。参考仓库工作树源码与发布包/现役进程可能不同；本轮只做静态核对，没有运行参考项目或安装锁定包验收。平台声明 `graphharbor==0.13.0.post41`、`langgraph==1.2.11`、`langgraph-sdk==0.4.3`，实施前必须核实实际安装版本。

外部参考只提供设计，不覆盖本项目开发规范；旧 [能力差距文章](../../knowledge/open-swe-vs-runtime-gap.md)第 20 节与同事提案相近，但其“没有用户停止流程”已不符合当前源码。

## open-swe 实际如何设计

### 1. 前端：通过 Thread 停止，而不是只断开本浏览器的流

`open-swe:ui/src/features/agents/components/composer/ComposerPrimaryActions.tsx` 的 `StreamPrimaryActions.handleStop()` 先调用 `cancelThread.mutateAsync()`，成功后才断开 SDK 订阅。取消失败时保留订阅和状态轮询，避免界面伪装成已停止。

原因写在其代码中：SDK `stream.stop()` 不一定知道 Slack/Linear/GitHub 或其他客户端启动的 Run。本项目当前会回查 Run 列表，已经比只断流更完整，但仍然只取消一个选中的 Run。

`open-swe:ui/src/features/agents/lib/api.ts` 的 `cancelThread()` 调用 Dashboard `/threads/{thread_id}/cancel`。这属于产品控制接口，不是 LangGraph 原生单 Run cancel 的替代实现。

### 2. Dashboard 后端：收集所有活动 Run，但可能继续处理排队消息

`open-swe:agent/dashboard/threads/api.py`：

- `_cancel_active_thread_runs()` 分别分页读取 `pending`、`running`，去重后调用 `runs.cancel_many(..., action="interrupt")`。
- `cancel_dashboard_thread()` 校验 Thread 的发帖权限，发出取消，再更新产品 metadata。
- **若 Store 中仍有排队消息，它会再次调用 `dispatch_agent_run()` 处理这些消息。** 因此 Dashboard Stop 不等同于“停止并清空全部待办”。
- `admin_cancel_dashboard_thread()` 是另一条管理业务路径；不把其管理范围移植为平台全局取消能力。

列表读取、批量取消、metadata 更新、后续派发是多个操作；这里没有证明它们相对于新提交/Worker claim 是同一原子事务。

### 3. Slack 后端：取消、清业务队列、记录意图、派发状态摘要

`open-swe:agent/slack/stop.py`：

1. `_resolve_stop_target()` 将 Slack 消息定位到 Thread，并核实频道/Thread metadata。
2. `claim_slack_event(event_id)` 对渠道事件去重。
3. `_active_run_ids()` 分页收集活动 Run，`cancel_many(action="interrupt")` 发出取消。
4. `_clear_deferred_work()` 删除 Store 的 `("queue", thread_id)/pending_messages` 和 `("autofix", thread_id)/pending_event`。
5. 更新 `latest_run_status` 与 `stop_requested_at_ms`。
6. **表情停止**派发 `stop_summary=True` 的摘要 Run；**session stopped 事件**仅取消/清队列，不发摘要。

摘要提示词在 `open-swe:agent/resources/prompts/runs/slack-stop-summary.md`，要求只回报已完成、进行中与剩余工作，不继续旧任务。

### 4. Agent 装配：摘要模式降低实际权限

`open-swe:agent/server.py` 在 `stop_summary_mode` 下跳过个人 MCP/Notion 加载；静态工具缩至 Slack 读/回帖，`STOP_SUMMARY_EXCLUDED_TOOLS` 排除 `execute/task/write_file/edit_file/delete`，不挂 `check_message_queue_before_model`。

可借鉴的是“摘要与正常执行有不同的实际能力集合”。仅改 Prompt、仍给摘要 Agent 生产工具，不足以保证只读。原项目仍用了 Deep Agents 组合与 Slack 发送动作；本项目已存在 [无工具 one-shot 路径](../../../apps/runtime-service/src/runtime_service/services/suggestions.py)，未来摘要可沿该模式实现，减少状态副作用。

### 5. 参考测试能证明什么

`open-swe:tests/slack/test_slack_stop.py` 覆盖定位、事件去重、取消失败、队列清理失败、摘要配置及调用。也存在允许非发起用户触发表情停止的测试，这是它的渠道策略，不适用于本项目 Thread edit 权限。

这些替身测试没有证明 Worker 已退出、Docker/线程内子进程已停、关闭浏览器后的收敛、分页与 claim 并发安全。不能把“参考代码有测试”换算成我们的生产验收。

## 当前项目：已有与不足

| 能力 | 当前源码事实 | 本轮结论 |
|---|---|---|
| 用户 Stop | `ChatSession.vue::handleStop()` 调用 `useChatSession.ts::stop()` | 已有；改接会话级闭环，不重建按钮 |
| 显式 `interrupt` | `session.service.ts::cancel()` 传 `false, "interrupt"`；工作区 service 同样显式传入 | 已有；“当前只有强杀”不准确 |
| 网关取消 | `presentation/http.py::cancel_thread_run()` -> `RuntimeGatewayService.cancel_thread_run()` -> `LangGraphRunsSdkAdapter.cancel()` | 已有单 Run 端点、Thread write 授权和 `run-cancel` 委托 |
| 取消与审计关联 | `service.py` 记录 `runtime.cancel.result`，审计解析已有 `runtime.run.item.cancelled` | 复用；增补会话取消请求关联及 accepted/confirmed 区分 |
| 终态回查 | `stop()` 调用 `verify(true)`，`active()` 只识别 `pending/running` | 有回查，但 `interrupted` 本身不是 Worker/清理确认 |
| 持久 Run 队列 | `useServerPromptQueue.ts`、`manage_thread_run_queue()`、GraphHarbor `runs_queue()` | 已有源码；单 Run Stop 不会一起取消其余队列 |
| 旧本地队列 | `usePromptQueue.ts` 当前作为 legacy 数据；ChatSession 正式使用 `useServerPromptQueue()` | 不再按“只有 localStorage 队列”规划；部署验收仍待旧专项 T7 |
| 运行中消息 inbox | `MessageInbox`、`MessageQueueMiddleware.abefore_model()` | 已有 claim、租约、授权、checkpoint 回执；与 Run 队列是两种不同资源 |
| inbox 收敛 | `webapp.py::list_messages()` 回查 Run，再 `reconcile_run()` | 查询驱动；把 `interrupted` 统一算 `run_ended`，没有会话停止屏障与独立后台收敛 |
| Docker 清理 | `workspace/execution.py::execute_in_workspace()` 捕获取消，shield 清理容器并回收进程 | 已有；需真实故障测试，不重复造清理层 |
| 本地 shell | Showcase/DeerFlow backend 的 `aexecute()` 用 `asyncio.to_thread()` 包装同步命令 | 协程取消不停止底层线程/命令；必须明确等待与清理边界 |
| HITL | 标准 `interrupt()`、真实 ID 的 `Command(resume=...)` | 已有；用户停止和等待审批不可混为一个状态 |
| 通用 Middleware | 当前组合根显式装配权限、工具错误、模型错误、消息队列等 | 复用范式；取消不必由模型调用一个新工具 |
| 取消后报告 | 无通用停止回执/证据报告端点，未见 `stop_summary` 等能力 | 必做确定性报告；模型润色可选后置 |

### 引擎事实：为什么 ACK 和 interrupted 都不能当完成

GraphHarbor 源码：

- `libs/langhost/src/langhost/core_api.py::_cancel_row()` 先写 `interrupted/cancel_requested`；有 Worker lease 时保留 lease，再发布控制信号。
- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/production_worker.py::_listen_for_cancel()` 接收信号；执行分支调用 `execution.cancel()` 并等待执行 task 退出。
- `run_store.py::finish()` 写 `execution_stopped=true` 的持久终态事件并释放 lease。
- `run_store.py::stopped_event()` 明确拒绝把单独的公开终态或 `execution_stopped=false` 当成停机确认。
- `core_api.py::runs_cancel_many()` 的批量 SELECT 没有提供请求级固定目标快照与 Thread 提交/claim 原子屏障。重试时重新按状态筛选可能命中后来创建的 Run。

确认执行 task 已退出，也不等于远端 HTTP 请求被撤回或 `to_thread` 中的子进程已退出。工具资源适配和外部副作用报告必须单独负责。

## 对同事提案逐条判断

| 提案 | 判断 | 调整后方案 |
|---|---|---|
| 没有用户主动停止流程 | 不采纳现状描述 | Stop、SDK cancel、网关及授权均已存在 |
| `interrupt` 等当前工具完成，是优雅而非强杀 | 不成立 | 它主要区分保留 checkpoint 与 rollback；当前 Worker 使用任务取消；真正 superstep drain 是另一能力 |
| 新增 Thread cancel endpoint | 采纳产品目标 | 补会话级停止端点，保留现有单 Run cancel；禁止公开部署级 `/runs/cancel` |
| 直接 `cancel_many` 全部取消 | 有价值，但不足以达到生产验收 | 引擎内固定目标、原子取消意图及回执；避免列表/分页/claim/重试竞态 |
| 清理 `message_queue` | 目标采纳，实现重设计 | Run 队列和 Runtime inbox 分开；已消费记录保留，未消费留原因，不删除全部记录 |
| 写 `stop_requested_at_ms` | 采纳为意图 | 使用服务端时间；metadata 仅作导航，不替代 Run/lease/终态事实，不立即伪造 `latest_run_status` |
| 派发“摘要小 run” | 不作为首期默认 | 必做无模型证据报告；可选无工具 one-shot 润色，不接回原 graph 或 inbox |
| 全部优先级为中 | 拆开判断 | 队列误继续、取消误确认、重复请求误伤属于正确性优先项；模型润色后置 |

## 借鉴与排除

**借鉴：** 会话级定位、先向服务端提出停止、事件/动作去重、待办收敛、意图时间、摘要与正常执行隔离、取消失败不伪装成功。

**排除：** Slack reaction/频道映射、GitHub/Linear 身份、repo/PR/autofix 属性、管理全局 stop、Slack 回帖 tool、原项目默认 follow-up `multitask_strategy="interrupt"`、Dashboard 取消后自动派发旧队列，以及未经证实的“interrupt 等工具完成”。

## 官方语义核对

本轮查询了 `langchain-docs` 与 `langchain-reference` MCP：

- [Cancel a run](https://docs.langchain.com/langsmith/cancel-run)：默认 `interrupt` 保留 Run/checkpoints；异步 ACK 后仍须等待或回查。
- [RunsClient.cancel](https://reference.langchain.com/python/langgraph-sdk/_async/runs/RunsClient/cancel)：默认 `wait=False`、`action='interrupt'`。
- [Graceful shutdown](https://docs.langchain.com/oss/python/langgraph/fault-tolerance#graceful-shutdown)：`RunControl.request_drain()` 是完成当前 superstep 后停止，不等于 cancel API；不终止线程。
- [LocalShellBackend](https://docs.langchain.com/oss/python/deepagents/backends#localshellbackend-local-shell)：宿主同步 shell 属受信任开发场景，不能用它证明生产沙箱安全或取消完成。

这些是上游设计说明；本项目最终仍以锁定的 GraphHarbor 包与真实跨服务测试为运行事实。
