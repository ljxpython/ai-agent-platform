# 平台 HTTP 错误出口

当前平台 API 的普通 JSON、文件及 SSE 握手前失败使用以下结构；已开始的 SSE 流不追加 HTTP 错误体。实施进度与未验证项见[错误响应专项](../projects/20260926-error-response-contract/README.md)。

```json
{"error":{"code":"workspace_directory_changed","message":"Directory changed","details":[]},"request_id":"req-example"}
```

- `request_id` 位于根级且等于 `x-request-id` 响应头。`error.extra` 仅在有安全字段时出现。
- 平台本地业务码保持原名；上游机器码必须在[精确清单](../projects/20260926-error-response-contract/error-catalog.md)登记并匹配来源 HTTP 状态。未知正文不公开。
- Runtime 来源401对外为502 `runtime_delegation_rejected`；403保持403；5xx通常转502；超时504；`memory_storage_unavailable`来源503对外502且保留该机器码。`extra.upstream_status_code` 记录真实来源状态。
- 上游 `thread_id/reconcile_path` 不透传；仅平台创建Thread结果未知时由平台生成并附加，客户端必须先调用 reconcile，不能直接重建。
- 422详情最多20项，只有有界 `loc/type/message`；上游原文、任意extra、Cookie/Authorization等响应头均不公开。500固定 `internal_server_error` / `Internal server error`。
