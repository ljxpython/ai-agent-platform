# Platform API 方案

## 目标

在现有 Runtime 网关边界内增加建议问题接口，复用现有项目、Thread、模型目录和 delegation 机制，让浏览器永远看不到 Runtime 凭据。

## 方案设计

### 当前代码证据与缺口

- `apps/platform-api/src/platform_api/entrypoints/http/router.py` 已挂载 `runtime_gateway_router`。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` 的 router 前缀为 `/api/langgraph`，已有 Thread、Run、workspace、memory、skills 等入口。
- `RuntimeGatewayService._load_thread()` 已统一做项目存在性、Thread ACL、Thread project scope 和 takeover 审计；建议接口必须复用它。
- `RuntimeGatewayService._assert_runtime_target_allowed()` 已校验 graph 是否属于项目；建议入口不能绕开。
- `get_runtime_gateway_service()` 已按请求创建 delegation headers factory，支持 `operation`、thread_id、context hash 和 opaque model reference。
- `LangGraphRuntimeGatewayUpstream` 已封装 `require_json`、错误转换和 forwarded headers，但没有 `generate_suggestions()`。
- 当前 `_delegation_operation()` 对 `/api/langgraph` 非 Run 路径默认为 `read`；新增建议入口应明确映射为独立 operation，避免误用普通 read token。

### 文件和函数落点

1. `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
   - 新增严格 Pydantic 请求/响应模型（建议 `SuggestionMessageBody`、`SuggestionsRequestBody`、`SuggestionsResponseBody`、`SuggestionsConfigResponse`）。
   - 新增 `GET /suggestions/config` 和 `POST /threads/{thread_id}/suggestions`。
   - 复用 `_require_project_id()`、`get_actor_context`、`_redact_runtime_private_fields()` 和现有 error handler。
   - body 使用 `extra="forbid"`；不得接收 `config`、`headers`、`tools`、`mcp`、`api_key` 等字段。

2. `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
   - 新增 `generate_thread_suggestions(...)`。
   - 第一步调用 `_load_thread(write=False, action="read")`，再提取 graph_id 并调用 `_assert_runtime_target_allowed()`。
   - 将 `messages` 规范化、截取最近窗口、检查空内容和字符上限；将可选 `model_id` 合并到现有 Runtime context 并复用 `_validate_run_options()` / `_assert_runtime_options_allowed()` 的模型目录规则。
   - 通过 `_delegation_headers_factory(... operation="suggestions-generate")` 创建 thread-bound delegation；如配置了 model reference，调用 `_attach_runtime_model_reference(thread_action="suggestions")`，只转发短期 opaque reference。
   - 对上游建议推理错误做 best-effort 空数组降级；对当前用户/Thread/模型权限错误原样保留标准错误语义。

3. `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`
   - 新增 `generate_suggestions(thread_id, payload)`，调用 Runtime `/internal/threads/{thread_id}/suggestions`。
   - 沿用 `with_forwarded_headers()`，禁止另造 HTTP client 或绕过 SDK 错误转换。

4. `apps/platform-api/src/platform-api` 的配置/审计位置（按实际 Settings 组织落点）
   - 增加 `suggestions_enabled`、`suggestions_max`、`suggestions_timeout` 的平台配置读取；默认 enabled、3、8 秒，最大数量 5。
   - correlation/audit 只增加固定 operation 和结果字段，不写完整会话文本。

5. `docs/standards/delegation-jwt.md`
   - 将 `suggestions-generate` 登记为新的自定义 operation，明确它只能访问 suggestions 内部路由，不能访问任何原生资源。
   - 同步 operation 数量、允许的 scope 键、错误映射和隔离测试矩阵；标准保持 draft，待人工评审后再进入实现。

### Platform API 对外行为

- `GET /suggestions/config` 不需要 Thread，但仍需要平台登录和项目上下文；没有项目上下文时沿用 `project_id_required`。
- `POST /threads/{thread_id}/suggestions` 必须绑定项目 header 与 Thread ACL；非 DearFlow 或不支持 one-shot 的 graph 先返回空数组或明确 `suggestions_not_supported`，选择一种后在契约测试锁定，建议 V1 统一空数组以保持前端无感。
- 上游 `401`/`403` 等授权失败不可吞掉；模型推理 `5xx`、超时、非法输出转为空数组并记受控日志。
- 该接口不创建 `run_requests`、不调用 `launch_runtime_run()`、不写消息队列、不触发 SSE。

## 任务拆分

- [x] Task 2.1：定义 Pydantic 请求/响应和配置来源；锁定最多 6 条输入、每条/总长度和 n=1～5。
  - **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → `SuggestionsRequestBody`、`SuggestionsResponseBody`、`SuggestionsConfigResponse`；`apps/platform-api/src/platform_api/config.py` → suggestions 配置。
  - **预期结果：** 未知字段、非法角色、空消息、超长消息和非法数量按标准 422 拒绝；默认返回 3 条且服务端上限 5 条。
  - **验证项：** `PYTHONPATH=.:src:tests uv run --with pytest --with httpx pytest tests/test_runtime_gateway_suggestions.py tests/test_runtime_delegation_contract.py -q` → ✅ 通过（8 passed，48 subtests）
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.2：新增 `RuntimeGatewayService.generate_thread_suggestions()`，复用 `_load_thread`、模型策略和 opaque model reference。
  - **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `suggestions_config()`、`generate_thread_suggestions()`。
  - **预期结果：** Thread ACL、项目/Graph/模型策略和 delegation context 在调用 Runtime 前完成校验；推理失败只降级为空数组。
  - **验证项：** 同上定向测试 → ✅ 通过
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.3：扩展 `LangGraphRuntimeGatewayUpstream`，加入内部 endpoint 调用和错误映射。
  - **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` → `generate_suggestions()`。
  - **预期结果：** 复用现有 upstream client、forwarded headers 和 timeout，调用 `/internal/threads/{thread_id}/suggestions`。
  - **验证项：** 定向测试 → ✅ 通过
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.4：在 HTTP router 接入两个接口，设置 operation=`suggestions-generate`，补 audit correlation。
  - **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → `get_suggestions_config()`、`generate_thread_suggestions()`、`_delegation_operation()`。
  - **预期结果：** 浏览器只访问 Platform API；请求不创建 Run、不写消息、不触发 SSE。
  - **验证项：** 定向测试 → ✅ 通过
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.5：补 `apps/platform-api/tests/test_runtime_gateway_suggestions.py`，覆盖授权、项目/Thread 隔离、模型策略、请求边界、空数组降级和“不创建 Run”。
  - **代码位置：** `apps/platform-api/tests/test_runtime_gateway_suggestions.py`。
  - **预期结果：** 成功、校验、越权、上游错误和副作用隔离都有可重复证据。
  - **验证项：** 定向 pytest → ✅ 通过
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.6：检查错误契约并复用现有错误语义。
  - **代码位置：** `docs/standards/error-envelope.md`（无需新增公开错误码）；Platform API 现有异常转换链路。
  - **预期结果：** 模型失败返回空数组，鉴权、ACL、模型授权和 schema 错误保留标准错误 Envelope。
  - **验证项：** 定向 pytest 与 Ruff → ✅ 通过
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步
- [x] Task 2.7：更新 `docs/standards/delegation-jwt.md` 的 `suggestions-generate` operation。
  - **代码位置：** `docs/standards/delegation-jwt.md`；Platform API/Runtime delegation 白名单与契约测试。
  - **预期结果：** suggestions token 只能访问 suggestions 内部 endpoint，不能访问原生 Thread/Run/workspace/tools/MCP。
  - **验证项：** delegation 定向测试 → ✅ 通过；正式标准人工评审 → ⚠️ 待完成
  - **状态：** `[x]` 已完成 2026-10-06 → 见 `implementation/01-platform-runtime-suggestions.md`
  - **合规检查：** [x] 代码实现；[x] 验证执行；[x] 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步

## 验证要求与记录

### 验证要求

- [ ] router 请求校验拒绝未知字段、空消息、超长消息、非法 n。
- [ ] 无 Thread ACL、跨项目 Thread、禁用模型、禁用 graph 均不能获得 Runtime 调用权限。
- [ ] delegation JWT 的 `operation`、`thread_id`、`assistant_id`、project scope 正确；不出现 token/API key 在响应体或日志。
- [ ] Runtime 失败只影响建议请求，正常聊天接口和 SSE 不受影响。
- [ ] `pytest` 定向通过，标准错误 envelope 与 request_id 保留。

### 验证记录

#### 2026-10-06

- ✅ `tests/test_runtime_gateway_suggestions.py` + `tests/test_runtime_delegation_contract.py`：8 passed，48 个参数化子测试通过。
- ✅ 改动文件 Ruff 检查通过。
- ✅ 覆盖 Thread ACL、跨项目隔离、模型策略、请求边界、delegation operation、上游降级和不创建 Run。
- ⚠️ Platform API 全量 pytest、真实 Runtime upstream 联调和三服务 E2E 待后续环境验证。

## 状态

已完成（本服务）

Platform API 代码和定向验证完成；全量测试与真实跨服务联调仍记录在项目总验证中。
