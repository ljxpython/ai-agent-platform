# GraphHarbor 接续：后台完成 Run 的只读回查

## B01：Run接受回执正式交付，lost-ACK引擎门禁已解除

状态：**done（B01解除）**，2026-10-10；所属任务T01/T05/T08的引擎门禁由GraphHarbor接受回执专项交付。双包正式post45已发布，`apps/runtime-service/pyproject.toml`、服务`uv.lock`及Dockerfile精确断言已接入；四产物独立下载hash匹配，Worktree从PyPI同步，两包来自本目录site-packages。应用对账只用正式adapter，不直读引擎表。原专项T08剩余矩阵、T10/F12全栈Final及新Linux镜像/现役启用未因B01自动完成。

**正式交付：** 独立POST/GET `/threads/{thread_id}/runs/acceptance`，原Idempotency-Key及最终UTF-8 bytes SHA256绑定，可信scope/credential/Thread/key/digest grant；原子Run+ledger，accepted/持久busy拒绝/unknown，纯SELECT固定GET，active保留详情、終态/删除首次观察后默认7天，永久墓碑。migration013与平台0007均拒绝删除接受事实的downgrade。这是GraphHarbor扩展，未声称LangGraph Server公开提供相同保证。post43/post44缺该契约的历史核查保留在引擎专项方案。

**本Worktree正式源联合Final：** `test_lost_native_ack_reconciles_queued_run_without_resubmission`三个参数各自disposable PG/Redis：notify **1 passed/249.96s**、stop **1 passed/322.48s**、revoke **1 passed/339.07s**。Worker暂停、POST已接受但ACK故意丢失、固定GET回查后仍为同一Run；每case仅源+完成2 Run/1 ledger，完成模型分别1/0/0。Stop回填保持suppressed、精确取消后cleanupconfirmed；撤权公开list/新执行403，内部GET仍可读且execution guard拒绝模型。

证据：`.local-stack/acceptance-{notify,stop,revoke}-pypi.xml`及对应case的`background-lost-ack-evidence.json`。脱敏副本、正式四hash、来源/锁/迁移、故障/两API/回退和32场景映射见 GraphHarbor 仓库 `docs/projects/20261010-run-acceptance-receipts/verification.md`。Platform132+116subtests、Runtime115、真实PG repository21、平台PG迁移1通过；skip/剩余全栈项如实记录。现役未部署，其他会话的本地栈未停启。

触发顺序：平台持久 RunRequests 预留 `background:<event_id>` → 原生 `/threads/{thread_id}/runs/acceptance` 接受一个 queued Run → 回包丢失 → Worker 暂停或该 Run 在开始前被 Stop/撤权。平台和 Runtime 均可能没有 run_id。开始前 guard 只有实际被调度时才能回填，因而不能替代全部回查。

当前对账：正常ACK使用原run_id；ACK丢失时从发送前保存的最终bytes/key/digest与非secret授权快照签短期固定只读委托GET回执。accepted回填同一Run，Stop仍suppressed；无记录/过期/普通错误unknown，不二次POST或换key。旧无body记录/旧API404/405仅当前ACL内有界分页正向匹配event+task+source，不能证明未接受。公开GET与shell不触发执行。

## 必须提供的能力

已交付只读按key查询：Thread+原Idempotency-Key+最终摘要 → 原接受记录，包括run_id与只读原生状态。GET不得创建Run、更新input/config、延长期限或恢复审批；原生接受记录与key绑定原子持久化。

返回至少区分 `accepted`、`definitively_not_accepted`、`unknown`。仅找不到 run_id 不证明未接受；需要明确事务/保留期语义。接受回执保留期必须覆盖最长完成通知和 Stop 对账，超期只能 unknown，不能默认重执行。

鉴权按固定原执行 scope、actor/credential 与 key/请求摘要控制回执读取，不授予新执行或任意 Thread/模型/日志读取。原操作者已撤权时，Runtime 仍需受信内部固定回执通道完成清理；浏览器公开权限继续按当前 ACL。可复用既有取消回执模式，不能放宽 `read` 使之读取所有任务。

## 本项目接线位置

- Platform `modules/runtime_gateway/application/background_completion.py::deliver()`：reconcile-only 分支调用 adapter 的只读回查；校验固定 event/source/scope/请求摘要后保存原 RunRequests 接受回执。
- Platform `adapters/langgraph/runtime_gateway_upstream.py` 与 `application/ports.py`：新增byte POST与固定GET正式adapter，最终bytes只序列化一次并发送前落盘；不在use case查询引擎表。
- Runtime `background_tasks/delivery.py::deliver_completion()`：仍用原 event/key，不切换事件、不 POST 新执行。`finish_delivery()` 绑定原 run_id 后，Stop 已抑制时保留 suppressed 并精确取消该 Run。
- Runtime `background_tasks/authorization.py`与auth/platform：已知run_id固定Stop清理与无run_id固定read回执委托分别约束；ordinary公开ACL及执行guard仍按当前授权，read token不能扩权。

## 解除条件

1. 正式双包发布并锁接入；记录版本、来源、wheel 哈希及冷安装。
2. 故障测试覆盖接受前/接受后/ACK 落盘前、Worker 未启动、排队中 Stop、开始前撤权、回查期限过期；只有一个 Run/消息/模型执行。
3. accepted 回查不产生模型/MCP/Workspace 动作；无回执情况下也能明确标注不可确认，不能 fake 成功。
4. 已撤权内部固定回执可清理，公开查询拒绝；错 tenant/project/Thread/key/摘要/credential 均拒绝。
5. 在 API/Worker 两进程和重启后补验迟到回包、原 key 对账、Stop 摘要从 unconfirmed 到 confirmed；旧 foreground、cron、HITL、inbox/Usage 回归通过。

上述引擎门禁已有真实证据，B01解除。原专项继续完成T08剩余矩阵、T10/F12与部署拓扑门禁；新提交默认关闭，未自动启用现役。前端不得将unknown渲染为失败后自动重试。永久墓碑随key线性增长，恢复到接受前备份会丢防重事实；receipt.accepted不能代替停止确认。
