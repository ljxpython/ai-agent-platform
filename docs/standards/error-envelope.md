---
status: active
last_verified: 2026-10-07
confidence: high
source_project: docs/projects/20260926-error-response-contract/verification.md
---

# 平台 HTTP 错误出口

当前平台 API 的普通 JSON、文件及 SSE 握手前失败使用以下结构；已开始的 SSE 流不追加 HTTP 错误体。实施进度与未验证项见[错误响应专项](../projects/20260926-error-response-contract/README.md)。

```json
{"error":{"code":"workspace_directory_changed","message":"Directory changed","details":[]},"request_id":"req-example"}
```

- `request_id` 位于根级且等于 `x-request-id` 响应头。`error.extra` 仅在有安全字段时出现。
- 平台本地业务码保持原名；上游机器码必须在[精确清单](../projects/20260926-error-response-contract/error-catalog.md)登记并匹配来源 HTTP 状态。未知正文不公开。
- Runtime 来源401对外为502 `runtime_delegation_rejected`；403保持403；5xx通常转502；超时504；`memory_storage_unavailable`来源503对外502且保留该机器码。`extra.upstream_status_code` 记录真实来源状态。
- 前端不得把网络失败、502/503/504 解释为权限撤销，也不得以此清除登录会话。403 只触发对应作用域的权威复核，项目 `/access` 空权限与 `project_not_found` 明确收回访问；路由不存在的 404 不作为撤权依据。
- 上游 `thread_id/reconcile_path` 不透传；仅平台创建Thread结果未知时由平台生成并附加，客户端必须先调用 reconcile，不能直接重建。
- 422详情最多20项，只有有界 `loc/type/message`；上游原文、任意extra、Cookie/Authorization等响应头均不公开。500固定 `internal_server_error` / `Internal server error`。

授权成功的 Thread/Run JSON 中 `error` 和 state/history 中 `tasks[].error` 属于执行错误槽位，保留字符串/对象形状及有限类型。未知对象为 `code=runtime.execution_failed`、固定 `message=Runtime execution failed`；未知字符串为 `runtime.execution_failed`。已知 Workspace 错误按完整五码精确投影为稳定码和固定说明，原生 `RuntimeWorkspaceError` 的 `message` 可作为精确机器码来源；不从嵌入文本抽码。详见 [Workspace 交接契约](../projects/20261007-agent-workspace-resilience/frontend-handoff.md)。不修改原生 Run 状态，普通消息/工具正文、artifact/result 不是执行错误槽位；私有字段仍递归清理。流内对应规则见 [SSE 契约](sse-event.md)。

`GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics` 的 provider 分类是 HTTP 200 安全 DTO 数据，不是 HTTP 错误码；`provider_auth_failed/provider_access_denied` 不触发平台登出或撤权。未启用/未录入/观测后端不可用以 availability 返回；授权拒绝、非法上游 DTO 等仍走本 Envelope。见 [诊断契约](../projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md)。

同一v1 DTO新增可选 `workspace_executions=[]`（最多20条），以及graph/startup的Workspace白名单错误码；不新增HTTP错误码、路由或权限，`model_errors`保持模型专用。Workspace执行错误仍是原生失败终态数据，HTTP200诊断或SSE握手成功不代表Run成功。
