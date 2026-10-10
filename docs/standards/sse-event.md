---
status: draft
last_verified: 2026-10-09
confidence: medium
source_project: docs/projects/20260926-sse-event-contract/verification.md
note: 帧安全/SDK重试/会话池/410降级已验(S1-S10)；8条并发H2/H3容量(S11)因HTTP/1.1入口阻塞，持续容量/堆增长/三段脱敏样例未验
---

# SSE 事件格式契约（draft）

> **适用服务：** runtime-service（产出）、platform-api（网关脱敏/心跳）、platform-web（消费）
> **验证证据：** API 事件脱敏 11 passed；Web Vitest 391 passed；受控 Playwright 15 passed；真实 SDK 链路通过
> **执行错误投影补充：** 2026-10-07隔离普通/Protocol/v3原生Run失败链路通过；debug task_result和checkpoint错误槽位安全，见[可观测性验收](../projects/20261006-agent-observability-hardening/implementation/02-backend-verification.md)。本轮未实施前端。
> **⚠️ 未完成：** H2/H3 8 条并发容量（S11）因 HTTP/1.1 入口限制阻塞；30 分钟持续容量、堆增长、资源归零待验

## 网关帧安全规则

| 规则 | 说明 |
|---|---|
| 单帧上限 | 8 MiB（8,388,608 字节），超限立即关闭，不输出部分 payload |
| 切片方式 | 按分隔符增量切片，不先拼接 chunk；支持 LF/CRLF 及跨 chunk 分隔符 |
| 心跳帧 | 注释心跳不作 JSON 解析，固定转为 `: heartbeat`，不透传上游文本 |
| 异常帧处理 | 非 JSON data / 损坏 UTF-8 / 非法 Protocol 外层：不透传原文，安全记录原因后关闭上下游 |
| 日志约束 | 只含固定 reason、request_id / trace_id 及授权范围内 thread_id；禁止记录 payload / token |
| 执行错误槽位 | Protocol/v3 `tasks/lifecycle.params.data.error`、普通 `tasks/error/lifecycle`、`debug.task_result.payload.error` 及 checkpoint `tasks[].error` 使用精确安全投影；移除异常 stack/body/traceback/provider_response，保留 event/id/seq、终态与正常消息/工具正文 |

执行错误投影不是 provider 分类来源。分类在 Runtime 模型边界记录，通过授权诊断 GET 查询；不能从安全消息猜原因或用模型尝试失败覆盖原生 Run 状态。实装与验收见 [可观测性专项](../projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md)。本次不代替原容量与浏览器验收，草案状态保留。

Workspace补充：仅完整白名单码或可信Worker类型/稳定message精确投影，字符串保持字符串、对象附固定code/message；未知字符串与对象code为 `runtime_execution_failed`，对象message为 `Runtime execution failed`。没有新增SSE事件、重试参数或独立终态；SDK恢复连接不重发Workspace命令。五码与安全v1诊断字段见 [交接契约](../projects/20261007-agent-workspace-resilience/frontend-handoff.md)。

## 执行预算通知 v1

获批 Runtime/API 实施复用现有 `custom` channel，普通默认 modes 已包含 custom；没有新增通知路由、
物理 SSE 或事件存储。数据类型为 `runtime_budget_notice`，字段为 version/type/notice_id/run_id/scope/
budget_scope/code/limit/used/remaining/unit，未知字段删除，非法通知投影为 null，客户端忽略。

| code | unit | budget_scope |
| --- | --- | --- |
| model_call_limit_approaching / model_call_limit_reached | model_calls | run / thread |
| graph_step_limit_approaching | graph_supersteps | graph |
| wrapup_started | seconds | run |
| token_budget_approaching / token_budget_exhausted / token_budget_unverifiable | tokens_total | run |
| tool_loop_approaching / tool_loop_reached | tool_rounds | run |

scope 为 primary/subagent；namespace 使用协议外层，notice_id 在相同 Run/graph namespace/维度内确定。
run_id 最大128字符，notice_id最大256字符；数值为 null 或有限非负且不超过 JS safe integer，调用/步骤必须整数。
没有工具预算 custom 或 graph reached custom；这两种硬异常按[错误出口](error-envelope.md)精确类型解释。

Token 额度分支固定 scope=primary，代表根 native Run 全树；不按子 namespace 分配新余额。limit 是正安全整数，known used 可超额，remaining=max(0,limit-used)；unverifiable 的 used 是已知小计或 null、remaining 固定 null。Token approaching 只在 ceil(max*4/5)<=used<max 且可验证时有效，exhausted 只在确实拒绝新增工作时通知。notice_id 是不透明去重键；自然最后回答达到 cap 不生成 exhausted/失败事实。

两个 Token 精确安全码在普通/Protocol/v3 的 tools/tasks/lifecycle/error/debug/checkpoint 错误槽位保留，异常正文仍隐藏。不新增物理 SSE 或状态机，通知不清 busy、不批准 HITL、不自动重发或加额恢复。历史通过现有 Run Usage 的可选摘要读取，已冻结样本见 [F01 前端交接](../projects/20260913-dearflow-agent/16-token-budget-frontend-handoff.md)。本补充不代表本规范容量门禁或 F01 浏览器验收已完成，draft 状态保留。

重复调用通知的 `tool_rounds` 表示连续相同参数和结果的完整只读工具批次，不是累计工具调用额度。approaching 固定 limit/used/remaining=5/3/2；reached 固定5/5/0；非法组合丢弃。复用 custom 和现有 Run/namespace/notice_id 去重，序列变更会产生新的 notice_id；前端不拼接 ID。v3 的数据在 `params.data`，v2 是直接 payload。reached 只证明触限转移，终态仍从原生生命周期/Run查询核实，不发送额外 cancel。

精确 `runtime.loop.detected` 在原生 error/tasks/debug/lifecycle 槽位按[错误出口](error-envelope.md)清洗，普通工具消息与记录保留。诊断不可用或事件410时不能根据最新 Thread.error 解释旧 Run；只用目标匹配的诊断/历史错误，否则安全降级。`runtime_loop_state` 递归剥离且拒绝客户端注入。当前默认关闭，前端待同事接入；真实 v2/v3 样例及后端验证见 [F02 交接](../projects/20260913-dearflow-agent/16-f02-frontend-handoff.md)。此补充不改变原容量门禁的 draft 状态。

Reference/Workflow 的 end 人工 AIMessage 带 `additional_kwargs.runtime_budget_notice`（仅 reached），
用于历史辅助恢复；网络写入口拒绝该标记、预算 clock/latch/counters。end 仍是原生 success，不表示任务完整完成。
error 路径保持原异常及真实终态，极低 recursion 可以只有安全错误而没有 custom。

客户端复用官方 SDK channel，按当前 Run/namespace 筛选、notice_id 去重；停止原因不能改写原生状态。
Run GET 没有 error，旧事件全部过期且无人工标记时安全降级，不借用最新 Thread.error 归因旧 Run。
软收尾不是 Worker timeout，不展示硬剩余时间。实际接线、联调与 H01-H16 回执见
[前端交接](../projects/20261007-agent-execution-budget/frontend-handoff.md)。本项不更改本规范容量门禁的 draft 状态。

## 计划状态与原生审批（2026-10-09 用户批准）

计划复用 state/history/values/updates/checkpoints 和原生 interrupt，不新增物理 SSE 或计划 custom 事件。API 仅在可信 state 槽位把 `runtime_plan` 投影为有限 `agent_plan`，移除 `plan_execution_id`、`bound_execution_id`、bootstrap 与签名；消息和 ToolMessage 中的普通同名内容保持原样。

公开字段为 version/status/active/plan_id/revision/title/markdown/content_hash/decision。无计划时该键可缺失；未批准时 approved_by/approved_at 省略，批准后只有 `approved_by={user_id}` 与服务端带时区 ISO8601 时间。revision=0 是空草稿；有效正文 UTF-8 最多64 KiB。status 为 planning/awaiting_review/approved/abandoned，只有当前真实 `agent_plan_review` interrupt 支撑时标记 awaiting_review；Workflow 的嵌套 interrupt 可投影当前快照。

`agent_plan_review` v1 含 plan_id/revision/content_hash/title/markdown/allowed_decisions；回复为当前 interrupt ID 映射的 `agent_plan_response` v1，decision 仅 approve/request_changes/abandon，反馈最多2000字符。前端保留真实 id/ns，复用 input.respond 与固定请求重试；投影、历史批准或“批准”聊天文本都不是操作依据。

Runtime 九个 `runtime.plan.*` 错误码只对可信异常类型与精确固定码公开；附带异常正文的字符串保持安全泛化。没有新终态：计划审批为原生 interrupted，abandon 结束但 active 保留，approve 不代表 Run success。完整 DTO、错误表与前端剩余验证见 [交接](../projects/20261008-agent-plan-mode-governance/frontend-handoff.md)。本补充不改变容量门禁的 draft 状态。

## 后台任务完成 Run（2026-10-09 用户批准）

后台任务不新增 SSE channel/custom 事件。完成通知是同 Thread 的独立 enqueue Run，客户端从任务元数据的 `latest_delivery_run_id/delivery.run_id` 发现后复用官方 SDK。源 Run 已结束不代表后续通知已创建，delivery accepted 也不代表 Run 已执行。私有 `platform_background_completion` 在 HTTP/history/Protocol/v3 JSON 出口递归剥离，普通输入递归拒绝；安全 task/event/source Run metadata 可保留用于关联。日志单独 GET 纯文本，不注入系统消息或执行错误槽位。见 [F06 前端接续](../projects/20261009-agent-generic-production-capabilities/frontend-handoff.md)。此加法契约不改变本规范原有容量门禁的 draft 状态。

## SDK 自动重试规则（补丁扩展）

| 规则 | 值 |
|---|---|
| 最大重试次数 | 5 次 |
| 重试延时 | 1 / 2 / 4 / 8 / 15 秒（±20% 抖动） |
| 预算重置条件 | 连续健康连接 30 秒才重置（防止空 200/立即 EOF 无限循环） |
| 空闲超时 | `streamIdleReconnect=45000`，任何字节（含心跳）刷新计时 |
| 可重试 | 网络错误、408/429/500/502/503/504、空响应体/异常 EOF |
| 不可重试 | 其余 4xx、410、错误 content-type / 协议结构错误 |

## Run 与连接状态分离

- 网络异常 / EOF 是连接变化，不伪造 Run 失败
- lifecycle 流先收 r1 终态，内容流后收 r1 最终 values，两者都必须处理
- r1 终态不能清掉 r2 的 busy 或待确认动作

## 会话池（ChatSessionPool）规则

| 规则 | 说明 |
|---|---|
| 条目 key | 始终用不变 `instanceId`，不用 threadId / route / mountVersion |
| scope 定义 | `userId + auth.sessionEpoch + projectId` 不可变组合；任一改变先使旧 scope 失效 |
| 隐藏后行为 | 继续流消费、运行核实、审批状态同步；暂停 DOM 测量、自动滚动、focus |
| promptQueue | 仅在 visible 且满足原条件时 drain |

## 410 cursor_expired 降级流程

```
收到 410
  → 立即停止自动重试，暂停两类物理 SSE
  → 读取 ACL / Run / state 确认授权
  → 通过现有 history / state 显示快照
  → reconnectEvents 重新订阅（不带失效 since）
  → 每条目只允许一个 recovery Promise
  → 一次恢复仍 410 则停止，不递归
```

不声称无缝恢复（无原子 snapshot 游标）。

## 权限清理规则

| 触发条件 | 行为 |
|---|---|
| 明确 403 / 404 / allowed_actions 失去 read | 清此 Thread 实例、缓存、收据、附件引用和对应草稿存储 |
| 网络故障 / 5xx | 不能当撤权清内容 |
| 换项目 / 登出 / sessionEpoch 变更 / 离开 Workspace | 同步 clearScope |

## 双入口约定

| 入口类型 | 重连参数 |
|---|---|
| Protocol 流 | `since`（非负整数） |
| 标准 Run SSE 流 | `last_event_id`（join 参数） |

两者不混用；`last_event_id` 不能改成 `since`。

## 上下文整理 custom（2026-10-06 用户批准）

复用已有 custom 通道，不新增物理 SSE。标准 Run 默认 modes 包含 custom。v3 Protocol 帧为 `method=custom`，`params.namespace/params.timestamp/params.data` 和 `seq`；data 直接是业务 payload，没有 payload 子层。显式 v2 标准 Run stream 的 custom data 直接为业务 payload。

`type=conversation_offloading`，允许 `status=started/completed/skipped/failed`、`trigger=manual/automatic`、不超过 128 字符的 operation_id/run_id、布尔 history_saved 和固定 reason_code。网关剔除额外字段、私有摘要/session 和 history 文件；客户端 input/state update 不能写这些字段。

根 namespace 为 `[]`，子图非空；根 UI 只消费根进度，run_id/operation_id 防重放和迟到覆盖。completed 是步骤状态，不是 Run success；checkpoint 最近 completed/skipped 由公开 state 恢复，失败或取消按 Run 终态核实，不要求存在 failed checkpoint。

浏览器沿已有 hydration、Run/state 对账、后台暂停和 410 路径恢复整理状态，不重新提交维护、不等待完整 history、不新增运行状态机。真实 v2/v3、子图和状态出口证据及前端剩余项见 [上下文专项](../projects/20261006-agent-context-window-governance/verification.md)。原 SSE 专项的容量门禁仍未完成，整体保留 draft。
