# 引擎与 Runtime 实现记录

## 日期

2026-10-07

## 相关任务

- Task 1.1–1.4
- Task 2.1–2.4

## 改动文件与函数

平台文件路径相对仓库根；GraphHarbor 路径相对外部配套仓库根 `$GRAPH_HARBOR_ROOT`，不得混入平台工作树。

| 文件 | 函数/位置 | 改动理由 |
|---|---|---|
| GraphHarbor `libs/langhost/src/langhost/cancellation.py:22` | `_receipt()`、`cancel_active():82`、`get_cancellation():198` | 以完整原子目标和持久退出证据代替逐页活动列表取消 |
| GraphHarbor `libs/langhost/src/langhost/core_api.py` | 复用 `_cancel_row()` | 沿既有 interrupt、checkpoint fence 与Worker通知，不造第二套取消协议 |
| GraphHarbor `libs/langhost/src/langhost/server.py:475` | `create_app()`路由 | 注册cancel-active和固定回执GET，位于动态Run路由之前 |
| GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/models.py:187` | `RunCancellationRow` | 保存principal/scoped key/targets/accepted_at/审批快照，只有通用引擎属性 |
| GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/migrations/versions/011_run_cancellations.py` | `upgrade()/downgrade()` | 增量目标表，旧单Run取消意图在回退后仍保留 |
| GraphHarbor `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/graph_executor.py:59` | `thread_config()` | LangGraph重建Runtime时传递服务端assistant_id/graph_id，恢复身份一致性 |
| `apps/runtime-service/src/runtime_service/db/migrations/versions/0002_run_control.py` | `upgrade()/downgrade()` | 独立业务控制/资源表，downgrade不删除已受理回执 |
| `apps/runtime-service/src/runtime_service/run_control/repository.py:14` | `request_stop()`、`claim_stop():87`、`save_stop():100`、`renew_stop():135`、`inbox_blocked():160` | scope/key哈希幂等、短事务、45秒fenced lease与固定旧目标屏障 |
| `apps/runtime-service/src/runtime_service/run_control/service.py:29` | `engine_receipt()`、`_advance_claim():122`、`_settle_inbox():95`、`run_control_lifespan():231` | 先回读固定取消ID再决定提交；全页回执核验、后台重试/重启、committed对账 |
| `apps/runtime-service/src/runtime_service/run_control/authorization.py:30` | `native_headers()`、`stop_callback():62` | 无持久JWT；受信后台短委托与当前权限/HMAC回查 |
| `apps/runtime-service/src/runtime_service/messaging/inbox.py:35` | `MessageInbox.enqueue()`、`claim():120` | 与Stop准备共用Thread advisory lock，竞争时不再向旧Run注入 |
| `apps/runtime-service/src/runtime_service/webapp.py:49` | `lifespan()`、路由挂载、`enqueue_message()` | 后台恢复不依赖页面，入口拒绝已停止旧目标 |
| `apps/runtime-service/src/runtime_service/http/run_control.py` | `cancel_thread()`、`get_stop()`、`list_stop()`、`_storage_call()` | 内部Thread精确scope、空正文/key/分页校验、安全503 |
| `apps/runtime-service/src/runtime_service/run_control/resources.py:35` | `register_resource()`、`wait_cleanup():55`、`finish_resource():65`、`execute_local():95` | 清理独立取证，重复取消也不能丢失已拥有资源收尾 |
| `apps/runtime-service/src/runtime_service/workspace/execution.py:79` | `execute_in_workspace()` | Docker创建/清理期间取消保护，rm失败/超时标unconfirmed |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py:112` | `LocalWorkspaceBackend.aexecute()` | local共用受管资源执行适配 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:102` | `DearWorkspaceBackend.aexecute()` | local/Docker沿现有backend边界接入，不增加Agent专属Stop |
| `apps/runtime-service/src/runtime_service/run_control/report.py:11` | `safe_label()`、`_run_evidence():61`、`build_report():139`、`stop_view():188` | 固定目标、安全有界证据、未知字段显式反馈，公开面隔离内部事实 |

## 关键行为变化

### 原子目标与停止证明

之前仅有单Run cancel，调用方必须先知道run_id；“查询活动列表再逐个取消”不能定义完整提交/领取边界。新增引擎操作在同一事务中以NOWAIT锁Thread及完整活动Run，记录固定targets，复用 `_cancel_row()`；冲突整单回滚。相同key回读原边界，后来的Run不进入旧Stop。每页最多100项，但target_count和最终确认覆盖全量。

```python
# 新增原子边界内的核心步骤，完整实现见 cancellation.py。
conn.session.add(row)  # row.targets 已由全部锁定 Run 构造
for run in rows:
    await _cancel_row(request, conn, run, "interrupt")
```

之前公开interrupted/Redis ACK不能证明执行退出。回执要求无执行lease、持久终态事件及对应execution_stopped证明；fence后既无lease又无退出事件时返回confirmation_unavailable，Runtime重试。不通过“等待几秒”猜成功。逐Run取消仍有线性SQL成本，500目标实测约33.24秒/5524 SQL；已加ponytail注释，不宣称秒级。

### 持久控制动作与 inbox

之前页面离开没有独立停止动作恢复链路。新增控制表只保存安全授权事实/key哈希/回执与租约；第一次POST返回持久accepted，受管后台每秒领取可重试动作，45秒lease/10秒续租，保存通过token fence拒绝旧owner。

```python
# service.py：未知提交先读原取消 ID，404 才回查当前授权并提交同 ID。
current = await engine_receipt(client, row)
if current is None:
    if not await stop_callback(row, authorize=True):
        return await _save_phase(row, "rejected", reason="stop_denied")
    current = await engine_receipt(client, row, create=True)
```

inbox之前enqueue/claim不感知Stop。现在Stop准备与两者共用Thread advisory lock，屏障仅绑定旧固定目标；退出后复用 `messaging/reconcile.py::reconcile_run()`，已消费记录保留，其余user_stopped，既有run_cancelled/run_ended不覆盖。对账每次最多10个Run，失败重试。

### 资源与报告

Docker之前已有shield清理，但没有清理回执；现在登记实际受管资源，创建中取消也等待spawn，rm失败/超时留下cleanup_unconfirmed，重复取消仍等待同清理task并传播原取消。Local之前await线程可先退出、线程仍跑；现在shield同一线程task，取消时最多75秒等有界命令，不声称强杀Python线程。独立PTY、detached任务和工作区文件不删。

报告仅读固定Run的最近committed root checkpoint，排除input继承的旧ToolMessage；最多20 checkpoints/20计划+10工具/20合法成果。JWT/凭据/宿主路径清洗；工具调用已发但尚无ToolMessage也保留external_effect_unknown。没有模型调用、新Run或AIMessage。媒体/部署unknown幂等行为未重写，本轮用取消与重试测试证明不重提外部任务。

## 新增测试与证据

- GraphHarbor `libs/langgraph-runtime-pg/tests/test_thread_cancellation.py`：`test_fixed_snapshot_pagination_retries_and_new_run`、20次参数化claim/submit竞争、lease fence、1/10/100/500容量。新增26项通过；取消/Worker/public-runtime前轮48项证据独立保留。
- `apps/runtime-service/tests/services/test_run_control.py`：25项定向通过，覆盖幂等/fence/重启、60次inbox竞争、固定报告/成果/脱敏、在途工具unknown、local重复取消、部署取消后attempts=1不重提、HMAC/服务账号、Docker模拟清理异常和安全存储503。
- `scripts/verify_thread_stop.py`：15条真实隔离HTTP场景；`scripts/verify_stop_migrations.py`：7条候选/备份/回退。详见[验证记录](../verification.md)与[evidence](../evidence/acceptance.json)。

## 兼容与限制

旧单Run cancel、审批、Run/SSE契约保留；新能力需引擎011与Runtime0002。Runtime正式锁仍post41；本轮唯一post43四产物/锁步与临时锁接入已验，正式发布/正式源锁接入待明确发布指令。真实Docker两类取消与PPTX通过，B01解除；未做现役迁移/重启，整体blocked见tasks。
