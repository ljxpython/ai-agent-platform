# 运行时网关执行配置白名单扩展支持 Checkpoint 分叉与时间旅行

## 背景与问题
当用户在前端会话详情中选择历史检查点（包括最初根检查点或中间快照）执行分叉（Fork）与时间旅行恢复时，前端通过 LangGraph 官方流式协议携带 `config.configurable.checkpoint_id`。
后端运行时网关（`platform-api`）的 `_execution_config` 存在过度防御性校验：
`set(configurable) - {"platform_runtime", "project_id"}`
导致携带任何合法 `checkpoint_id` 或 `checkpoint_ns` 的运行请求均被拦截并抛出：
`400 Bad Request — code: unsupported_run_config, message: Unsupported execution config`，时间旅行与分支恢复全线受阻。

## 变更内容
1. **白名单对齐官方协议**（`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`）：
   - 将 `_execution_config` 允许的 `configurable` 扩展为 `{"platform_runtime", "project_id", "checkpoint_id", "checkpoint_ns"}`；
   - 增加对 `checkpoint_id`（非空纯字符串）与 `checkpoint_ns`（字符串）的严格格式校验；
   - 维持对未知/敏感字段（如 `api_key`、`user_id` 等）的强防御拒绝；
   - 在生成的 `config_snapshot` 中保留合法的 `configurable.checkpoint_id` 与 `configurable.checkpoint_ns`，确保持久化与重试一致性。
2. **协议透传与顶层提升**：
   - `service.py`：在 `_promote_protocol_run_start` 与 `launch_runtime_run` 中，若 `configurable` 包含 `checkpoint_id`，同步提升至顶层 `payload["checkpoint_id"]`，实现与 Agent Server 标准 Runs API 的双重兼容；
   - `apps/platform-api/src/platform_api/core/runtime_contract.py`：在 `normalize_protocol_v2_command` 中将 `checkpoint_id`、`checkpoint_ns`、`checkpoint` 纳入允许的顶层运行字段白名单。
3. **自动化测试补充**（`apps/platform-api/tests/test_run_requests.py`）：
   - 增加 `test_fork_and_checkpoint_execution_config_allowed_and_preserved`，覆盖合法分叉参数的转发、非法空字符串的拒绝，以及恶意字段的拦截。

## 涉及文件
- [MODIFY] `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- [MODIFY] `apps/platform-api/src/platform_api/core/runtime_contract.py`
- [MODIFY] `apps/platform-api/tests/test_run_requests.py`
- [MODIFY] `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`
