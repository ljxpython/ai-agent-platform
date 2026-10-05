# Runtime 网关状态读取 Delegation Token 注入与反向 ACL 容灾加固

## 背景
用户在对话界面切换或离开会话时，界面偶尔会抛出 `HTTP 502: {"error":{"code":"langgraph_upstream_request_failed","message":"Runtime request failed", ... "upstream_status_code":503}}`，提示平台授权不可用（`Platform authorization unavailable`）。

## 根因剖析
1. **网关状态读取 Delegation Token 漏传**：
   在 `platform-api` 的 `RuntimeGatewayService` 中，`get_thread_state` 与 `get_thread_history` 之前直接使用 `self._upstream.get_thread_state` / `get_thread_history`，缺少 `await self._thread_upstream(project_id=project_id, thread=thread, operation="read")`。向 `runtime-service` 转发请求时未携带包含正确 thread scope 与 read operation 的 Delegation JWT，导致 runtime-service 无法直接认定权限。
2. **Runtime 反向 ACL 超时过紧（3 秒硬超时）**：
   在缺少有效 Delegation 时，`runtime-service` 的 `deny_image_scope_on_server_resources` 退化为向 `platform-api` 反向请求 `/api/runtime/internal/thread-authorization`。该内部 HTTP 请求原先硬编码 `timeout=3.0` 秒，在前端会话切换触发密集并发时容易因短暂排队发生超时，直接抛出 `503 Service Unavailable (Platform authorization unavailable)`。
3. **前端对 Raw JSON 错误的展现缺乏友善化**：
   前端在接收到 stream 错误时，直接将原始未解构的 JSON 抛出，污染用户交互。

## 改动内容
1. **`platform-api/service.py`**：
   - `get_thread_state` 与 `get_thread_history` 统一经过 `self._thread_upstream(..., operation="read")` 包装，显式携带针对当前 thread_id 的合法读取委托令牌。
2. **`runtime-service/platform.py` & `.env`**：
   - 将反向 ACL 请求超时参数化，支持 `PLATFORM_ACL_TIMEOUT_SECONDS`，本地栈与生产配置调整为 10.0 秒；
   - 增加 ACL 校验失败时的详细 warning 日志。
3. **`platform-web/ChatSession.vue`**：
   - 提取并格式化 upstream 错误中的请求编号与人类可读提示，引导用户恢复连接。

## 验证结论
- Platform-API 网关测试：4 passed in 6.06s
- Runtime-Service 认证与权限测试：109 passed in 10.94s
- Platform-Web 前端单测：213 passed, 46 套测试文件全绿
- 前端静态类型检查：0 errors
- 前端生产构建：17.11s 顺利通过
