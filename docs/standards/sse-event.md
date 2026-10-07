---
status: draft
last_verified: 2026-10-07
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
| 执行错误槽位 | Protocol/v3 `lifecycle.params.data.error`、普通 `error`/`lifecycle`、`debug.task_result.payload.error` 及 checkpoint `tasks[].error` 使用固定安全消息；移除异常 stack/body/traceback/provider_response，保留 event/id/seq、终态与正常消息/工具正文 |

执行错误投影不是 provider 分类来源。分类在 Runtime 模型边界记录，通过授权诊断 GET 查询；不能从安全消息猜原因或用模型尝试失败覆盖原生 Run 状态。实装与验收见 [可观测性专项](../projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md)。本次不代替原容量与浏览器验收，草案状态保留。

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
