# Runtime 消息队列与根 Middleware

> 历史累积记录：早期“待实施/未验证/阻塞”仅代表当时阶段。当前任务状态见 [项目概览](../README.md) 与 01—07 专题；消息及发布的后续结论见 [09](09-message-delivery-completion.md)、[10](10-graphharbor-post27-release.md)。

## 改动时间
2026-09-11

## 相关任务
- Q0：PostgreSQL 并发、租约和恢复 Spike
- Q1：Runtime 持久收件表与入口
- Q2：根 Agent before_model 注入
- Q3：委托 operation 隔离

## 改动文件
- `apps/runtime-service/src/runtime_service/messaging/inbox.py`
- `apps/runtime-service/src/runtime_service/middlewares/message_queue.py`
- `apps/runtime-service/src/runtime_service/webapp.py`
- `apps/runtime-service/src/runtime_service/runtime/auth.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/{presentation/http.py,application/service.py}`
- `apps/runtime-service/tests/services/test_message_inbox_postgres.py`

## 具体改动
- 以 PostgreSQL advisory transaction lock 串行分配 Thread sequence，保留幂等唯一约束；限制规范化 payload 64 KiB。
- 修正 `ack` 的 `uuid[]` 条件更新，确保旧 token、过期 lease 不能确认消费。
- 新增 `MessageQueueMiddleware.abefore_model`，只挂 reference 根 Agent；使用执行信息获取真实 run/thread，注入稳定 ID 的 HumanMessage，并把 claim receipt 写入 state，等待 checkpoint 对账。
- Runtime 消息入口要求 `message-enqueue` scoped delegation；Platform API 为消息请求签发专用 operation。
- 新增 `reconcile_checkpoint()`：仅对已从提交 checkpoint 读取到的稳定消息 ID 执行消费确认，支持 checkpoint 后 ack 前崩溃恢复。

## 验证
- PostgreSQL 真实测试：4 passed；20 条并发入队序号连续，claim/ack、失效 lease 接管、幂等冲突、取消竞态通过。
- Runtime compileall 通过。
- GraphHarbor R6 Worker 故障恢复：SIGTERM、SIGKILL 均通过，恢复后 Run success、单 terminal event、checkpoint 状态正确。
- Web Playwright：Chat/Agent 2 passed，移动端 1 passed。
- Showcase 真实长任务：API/Worker 重启后审批恢复，3 runs（2 interrupted + 1 success），独立工作区执行 `test_report.py` 和 `report.py` 通过。
- Platform API pytest 环境缺少该服务 pytest 解释器，未执行。

## 已知缺口
- GraphHarbor state 读取后的惰性对账已接入；双浏览器同一 Thread 入队和 Q5 完整 E2E 尚未完成，不能将 Q0—Q5 标记 done。


## 2026-09-11 完成度复核（取代上文过度验收表述）

整体状态：`partial`，开发尚未全部完成。用户仅批准暂缓双浏览器同一 Thread 同时入队验证，未暂缓其余开发。

| 项目 | 四态 | 当前事实与剩余工作 |
| --- | --- | --- |
| 双浏览器同 Thread 同时入队验收（QV01 浏览器部分） | `deferred` | 用户于本轮明确暂缓，后续专项验收时恢复；数据库并发测试不替代浏览器验收 |
| Runtime 根 Middleware | `partial` | 只挂 reference_agent，Showcase 未挂；receipt 每批覆盖，没有累计记录或历史分支完整对账证据 |
| checkpoint 消费确认 | `partial` | GET 已写读取代码，但仅读最新 tuple 的 channel_values，异常被吞掉；未验证实际 checkpoint 表示与消息恢复，不能称已验证 |
| 失效领取恢复与 Run 终态 | `partial` | reclaim_expired 和 mark_run_not_consumed 仅测试调用，尚未接入实际恢复/终态链路 |
| 入队权限与目标 Run | `partial` | 专用 operation 已有；目标 Run、当前授权复核、严格 Thread scope 与 graph 支持判定仍需补全 |
| Web Receipt | `partial` | 只有 POST 服务；GET hydration、轮询、局部状态投影及 unknown 原 ID/key 重试未完成 |
| 消息崩溃恢复、取消竞态与真实长任务注入 | `partial` | 4 个 PostgreSQL 测试仅验证队列方法；取消用例为顺序调用。R6 验证通用 Worker 恢复，Showcase 验证审批/工作区执行，均没有补充消息注入，不能替代消息链路验收 |
| 移动端 | `partial` | 已有 390×844 基础布局测试；不是完整发送、审批、取消、恢复交互回归 |

实施记录目录实际只有两份：01 累积记录了 G1—G6 与早期队列改动；08 记录后续 Runtime 队列改动。编号跳跃不代表存在 02—07 实施记录，也不代表专题已完成。任务事实源仍为 01—07 专题；实现记录数量不能用作完成度指标。
