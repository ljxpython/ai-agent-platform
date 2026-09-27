# GraphHarbor 上游修复建议：历史中断事件重放（Zombie Interrupts Replay）根因与方案

> **文件性质：** 交付给 GraphHarbor 团队的上游协同修复说明
> **关联项目：** `docs/projects/20260927-sse-stream-heartbeat-and-resilience/`
> **问题级别：** 严重（破坏 HITL 多轮审批状态机一致性）
> **涉及服务：** GraphHarbor `langhost` 协议服务、Run 状态机调度器
> **创建日期：** 2026-09-27

---

## 1. 现象与复现链路

### 1.1 现象描述
在开启人工审批（Human-in-the-Loop, HITL）的对话场景中，智能体执行多次需要审批的工具调用（例如连续调用维基百科抓取、文件修改等）：
1. 智能体触发第 1 次工具调用审批（中断 ID：`be9b9aff86a5e50f17a72febe6925c27`）；
2. 用户在前端确认批准，后端成功下发 `resume` 指令，智能体恢复执行；
3. 智能体执行完第 1 个工具后继续推理，触发第 2 次工具调用审批（中断 ID：`430ad73e0cc51269255adcd732f345be`）；
4. **异常发生：** 客户端建立或重连 SSE 协议流（`/threads/{thread_id}/stream/events`）时，GraphHarbor 在事件重放（replay）阶段，**不仅下发了当前最新的中断，还将历史上所有已经处理完的历史中断事件（整整 8 个）全量重新推送给了客户端！**
5. 前端 SDK 收到这些被重放的历史 `input.requested` 事件后，将其重新渲染在 UI 界面上。当用户尝试点击批准时，前端校验发现后端当前的真正 Checkpoint 已经推进到了新中断，两边 ID 无法对齐，抛出异常：
   ```text
   审批请求已变化，请恢复连接后重新确认
   ```

---

## 2. 根因深度剖析（代码与数据库实锤）

经过排查数据库实际数据和 `langhost` 源码，定位到以下两个关键缺陷相互耦合：

### 2.1 缺陷 1：被恢复的旧 Run 状态未终态化（Zombie Interrupted Runs）
在 GraphHarbor 数据库 `graphharbor_acceptance` 中查询该 Thread 的 `runs` 记录：
```sql
SELECT run_id, status, kwargs->>'stream_resumable', created_at
FROM runs
WHERE thread_id = '17379834-a1c3-4df6-b453-03d1667cc126'
ORDER BY created_at;
```
实测输出结果：
```text
(UUID('2dc1de0a-...'), 'interrupted', 'true')
(UUID('e39a3ec7-...'), 'interrupted', 'true')
(UUID('afda5df3-...'), 'interrupted', 'true')
(UUID('662d963a-...'), 'interrupted', 'true')
(UUID('0a74feae-...'), 'interrupted', 'true')
(UUID('aa5de4a8-...'), 'interrupted', 'true')
(UUID('860b4c09-...'), 'interrupted', 'true')  <-- 产生 be9b9aff... 的 Run
(UUID('3ed79114-...'), 'interrupted', 'true')  <-- 当前最新的 Run
```
**问题点：**
当客户端下发 `resume` 指令时，GraphHarbor 创建了一个新的 Run 去接管执行，**但原先被打断的旧 Run 在 `runs` 表中的 `status` 却永久保持为 `'interrupted'`，且 `kwargs->>'stream_resumable'` 仍然是 `'true'`！** 导致系统遗留了大量“僵尸中断 Run”。

### 2.2 缺陷 2：`protocol_event_stream` 重放缺乏有效性门禁
在 `langhost/protocol_api.py` 的第 311-328 行：
```python
watermark, replay = await _load_protocol_events(thread_id, since)
parsed_run_ids = {
    uid
    for wire in replay
    if (uid := _safe_uuid(wire.get("params", {}).get("run_id"))) is not None
}
resumable = await _resumable_run_ids(parsed_run_ids)
replay = [
    wire
    for wire in replay
    if (uid := _safe_uuid(wire.get("params", {}).get("run_id"))) is None or uid in resumable
]
```
以及 `langhost/streaming.py` 中的 `_resumable_run_ids`：
```python
async def _resumable_run_ids(run_ids: set[UUID]) -> set[UUID]:
    if not run_ids:
        return set()
    async with connect() as conn:
        return set(
            (
                await conn.session.scalars(
                    select(RunRow.run_id).where(
                        RunRow.run_id.in_(run_ids),
                        RunRow.kwargs["stream_resumable"].as_boolean().is_(True),
                    )
                )
            ).all()
        )
```
**问题点：**
1. `_resumable_run_ids` 仅仅判断了 `kwargs["stream_resumable"] == True`，由于缺陷 1，所有历史旧 Run 全部落在这个条件里；
2. 于是 `replay` 包含了该线程历史上所有的历史事件；
3. 最致命的是：对于 `method == "input.requested"` 的事件，**GraphHarbor 完全没有校验该 `interrupt_id` 是否依然在当前 Thread 最新 Checkpoint 的待处理任务中（即 `threads.getState().tasks[].interrupts`）**，直接向客户端吐出了 8 个已经失效的历史中断！

---

## 3. GraphHarbor 修复方案建议

建议 GraphHarbor 团队按以下两个方案进行协同修复：

### 方案 A：在 Run 被恢复（Resume）时终态化旧 Run（生命周期治理）
当调度器收到对某个 Thread/Run 的 `resume` 指令并创建新的恢复 Run 时：
1. 将前序被打断的旧 Run 的 `status` 更新为终结状态（例如 `resumed` 或 `completed`），或者将旧 Run 的 `kwargs["stream_resumable"]` 标记为 `False`；
2. 这样旧 Run 就不会被 `_resumable_run_ids` 检索出来，从而避免历史事件被再次重放。

### 方案 B：在 SSE 重放时针对 `input.requested` 增加活跃门禁（推荐，见效最快）
在 `langhost/protocol_api.py` 的重放过滤中，对 `input.requested` 事件增加与当前最新状态的一致性校验：
只有当事件携带的 `interrupt_id` 依然存在于当前 Thread 最新 Checkpoint 的 `tasks[].interrupts` 中时，才允许将其重放给客户端。

**参考修改伪代码（`langhost/protocol_api.py`）：**
```python
# 1. 查询当前 Thread 最新 Checkpoint 中的活跃中断 ID 集合
active_interrupt_ids = set()
latest_state = await _get_thread_state(thread_id) # 获取当前最新 state
if latest_state and isinstance(latest_state.get("tasks"), list):
    for task in latest_state["tasks"]:
        for item in (task.get("interrupts") or []):
            if isinstance(item, dict) and item.get("id"):
                active_interrupt_ids.add(item["id"])

# 2. 在构建 replay 事件列表时，过滤已失效的历史 input.requested 事件
filtered_replay = []
for wire in replay:
    method = wire.get("method")
    if method == "input.requested":
        data = wire.get("params", {}).get("data", {})
        interrupt_id = data.get("interrupt_id")
        # 如果该中断已不在当前最新 Checkpoint 中，说明已经解决，严禁重放！
        if interrupt_id and interrupt_id not in active_interrupt_ids:
            continue
    filtered_replay.append(wire)

replay = filtered_replay
```

---

## 4. 交付与验证建议
1. 在修复方案上线后，执行多轮连续工具调用审批（HITL 测试用例）；
2. 保持会话重连，断言 SSE `/stream/events` 重放时仅输出当前唯一等待中的 `input.requested` 事件，不再输出任何已消费的历史中断；
3. 平台端前端与网关层也将同步加入防御校验，双方共同保障长连接会话的鲁棒性。
