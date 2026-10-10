# GraphHarbor 接续：后台完成 Run 的只读回查

## B01：post43 不能闭环全部 lost-ACK 窗口

状态：blocked；所属任务 T01/T05/T08。需要 GraphHarbor 负责人补正式只读契约与发行产物，再回本项目验证。当前工作树仅依赖正式 post43，不改引擎代码、不直读引擎 runs/lease/幂等表。

触发顺序：平台持久 RunRequests 预留 `background:<event_id>` → 原生 `/threads/{thread_id}/runs` 接受一个 queued Run → 回包丢失 → Worker 暂停或该 Run 在开始前被 Stop/撤权。平台和 Runtime 均可能没有 run_id。开始前 guard 只有实际被调度时才能回填，因而不能替代全部回查。

当前替代办法已验证：正常 ACK 使用原 run_id；Worker 恢复并进入 guard 后回填原 run_id；平台已有 RunRequests 回执时不需要新增授权或执行。对全部无回执窗口采用 `reconcile_only=true`，保持 unknown/inflight，停止重复 POST。公开 GET 和 shell 不触发新执行。此降级避免重复费用，但通知与 Stop 清理不能宣称确认完成。

## 必须提供的能力

建议只读按 key 查询接口（具体路由由引擎负责人冻结）：Thread + 原 Idempotency-Key → 原接受记录，包括 run_id、原 key 对应的请求摘要和原生状态。接口不得创建 Run、更新 input/config、延长幂等记录或恢复审批；原生接受记录与 key 绑定须原子持久化。

返回至少区分 `accepted`、`definitively_not_accepted`、`unknown`。仅找不到 run_id 不证明未接受；需要明确事务/保留期语义。接受回执保留期必须覆盖最长完成通知和 Stop 对账，超期只能 unknown，不能默认重执行。

鉴权按固定原执行 scope、actor/credential 与 key/请求摘要控制回执读取，不授予新执行或任意 Thread/模型/日志读取。原操作者已撤权时，Runtime 仍需受信内部固定回执通道完成清理；浏览器公开权限继续按当前 ACL。可复用既有取消回执模式，不能放宽 `read` 使之读取所有任务。

## 本项目接线位置

- Platform `modules/runtime_gateway/application/background_completion.py::deliver()`：reconcile-only 分支调用 adapter 的只读回查；校验固定 event/source/scope/请求摘要后保存原 RunRequests 接受回执。
- Platform `adapters/langgraph/runtime_gateway_upstream.py` 与 `application/ports.py`：仅新增正式只读 adapter 方法；不在 use case 拼数据库查询。
- Runtime `background_tasks/delivery.py::deliver_completion()`：仍用原 event/key，不切换事件、不 POST 新执行。`finish_delivery()` 绑定原 run_id 后，Stop 已抑制时保留 suppressed 并精确取消该 Run。
- Runtime `background_tasks/authorization.py`：已知 run_id 的固定 Stop 清理例外已实现。新增无 run_id 的回执读取例外须与引擎新协议同步评审，不让现有 token 扩权。

## 解除条件

1. 正式双包发布并锁接入；记录版本、来源、wheel 哈希及冷安装。
2. 故障测试覆盖接受前/接受后/ACK 落盘前、Worker 未启动、排队中 Stop、开始前撤权、回查期限过期；只有一个 Run/消息/模型执行。
3. accepted 回查不产生模型/MCP/Workspace 动作；无回执情况下也能明确标注不可确认，不能 fake 成功。
4. 已撤权内部固定回执可清理，公开查询拒绝；错 tenant/project/Thread/key/摘要/credential 均拒绝。
5. 在 API/Worker 两进程和重启后补验迟到回包、原 key 对账、Stop 摘要从 unconfirmed 到 confirmed；旧 foreground、cron、HITL、inbox/Usage 回归通过。

满足后再完成 T01/T05/T08 非前端 Final，并开启正式拓扑。前端 F01-F12 可消费现有 v1 查询契约开发，但不得将后台 unknown 渲染为失败后自动重试。
