# 运行时网关执行配置白名单支持 SDK 自动注入的 thread_id

## 背景与问题
在前端（`platform-web`）通过 `@langchain/vue` 或 `@langchain/langgraph-sdk` 的 `StreamController` / `SubmitCoordinator` 发起会话流式运行或分发 Protocol v2 命令时，官方 SDK 底层 `bindThreadConfig` 会强制将当前会话的 `thread_id` 自动合并进 `config.configurable`（即 `config.configurable.thread_id`）。
后端运行时网关（`platform-api`）的 `_execution_config` 执行过度防御性白名单校验：
`_ALLOWED_CONFIGURABLE_KEYS = {"platform_runtime", "project_id", "checkpoint_id", "checkpoint_ns"}`
由于白名单中缺失 `thread_id`，导致真实浏览器环境下所有提交请求均被 400 拦截，抛出：
`Protocol request failed: 400 Bad Request — Unsupported execution config`，阻断会话对话。

## 变更内容
1. **白名单补齐官方 SDK 注入字段**（`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`）：
   - 将 `_ALLOWED_CONFIGURABLE_KEYS` 扩展为 `{"platform_runtime", "project_id", "checkpoint_id", "checkpoint_ns", "thread_id"}`；
   - 在 `_execution_config` 中增加对 `thread_id` 的非空纯字符串校验；
   - 在持久化的 `config_configurable` 快照中保留合法的 `thread_id`；
   - 维持对未知恶意字段（如 `api_key`）的防御性拒绝拦截。
2. **自动化测试覆盖**（`apps/platform-api/tests/test_run_requests.py`）：
   - 增加 `test_sdk_injected_thread_id_execution_config_allowed`，覆盖带 `thread_id` 的合法运行请求放行与快照保留，以及非法空白串的拦截。

## 涉及文件
- [MODIFY] `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- [MODIFY] `apps/platform-api/tests/test_run_requests.py`
