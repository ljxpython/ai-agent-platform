# Platform API 与 Runtime follow-up suggestions 实现记录

## 改动时间

2026-10-06

## 相关任务

- 01-architecture-and-contract.md：Task 1、Task 1.1、Task 2、Task 3
- 02-platform-api.md：Task 2.1～2.7
- 03-runtime-service.md：Task 3.1～3.5

## 改动范围

本次完成 Platform API → Runtime Service 的后端链路；不修改 `apps/platform-web` 业务代码，前端以 `04-platform-web-handoff.md` 交接。

## 改动文件与理由

### Platform API

- `apps/platform-api/src/platform_api/config.py`
  - 增加 `suggestions_enabled`、`suggestions_max`、`suggestions_timeout_seconds`，默认 3 条、最大 5 条、8 秒超时。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - 增加配置查询和 Thread suggestions POST 路由；请求模型 `extra="forbid"`，只接受 `user`/`assistant` 消息、`n` 和可选 `model_id`。
  - 将 suggestions 路由映射到独立 `suggestions-generate` operation，避免复用普通 `read` delegation。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - 新增 `suggestions_config()`、`generate_thread_suggestions()`。
  - 复用 Thread ACL、项目/Graph 校验、模型目录/策略和 opaque model reference；限制 6 条消息、单条 4,000 字符、总计 12,000 字符。
  - Runtime 推理超时、5xx 和非法响应按 best-effort 返回空数组；用户鉴权、Thread ACL、模型授权和 schema 错误继续走标准错误。
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`
  - 增加 `generate_suggestions()`，复用现有 upstream client、forwarded headers 和错误转换，调用 Runtime suggestions endpoint。
- `apps/platform-api/src/platform_api/core/security/tokens.py`
  - 把 `suggestions-generate` 纳入 delegation operation 允许集合。
- `apps/platform-api/tests/test_runtime_gateway_suggestions.py`
  - 覆盖成功、配置关闭、输入边界、Thread/项目隔离、模型策略、delegation、上游降级和不创建 Run。
- `apps/platform-api/tests/fixtures/runtime_delegation_verifier.py`、`tests/test_runtime_delegation_contract.py`
  - 更新 operation 验证，移除新增 operation 后依赖固定索引的脆弱断言。

### Runtime Service

- `apps/runtime-service/src/runtime_service/http/suggestions.py`
  - 新增 `/internal/threads/{thread_id}/suggestions`；校验 JWT operation 及 tenant/project/thread/assistant scope。
- `apps/runtime-service/src/runtime_service/services/suggestions.py`
  - 新增独立 one-shot service：复用 resolver/model connection，调用一次 `model.ainvoke()`，不创建 Graph、Run、checkpoint、消息、workspace、工具或 MCP 资源。
  - 清洗 `<think>`、Markdown code fence、数组外文本、空值、重复和超长建议；模型初始化、provider 异常和超时返回空数组。
- `apps/runtime-service/src/runtime_service/runtime/modeling.py`
  - `build_model()` 增加 `max_retries` 注入点，suggestions 使用 `0`，避免回答完成后额外重试放大成本。
- `apps/runtime-service/src/runtime_service/webapp.py`
  - 挂载 suggestions router。
- `apps/runtime-service/src/runtime_service/runtime/auth.py`
  - 增加 `suggestions-generate` 自定义 operation 的严格隔离白名单。
- `apps/runtime-service/tests/http/test_suggestions.py`
  - 覆盖 scope mismatch、请求校验和 endpoint 响应。
- `apps/runtime-service/tests/services/test_suggestions.py`
  - 覆盖模型调用次数、输出解析、超时/provider/初始化失败和无副作用路径。

### 跨服务标准与状态文档

- `docs/standards/delegation-jwt.md`
  - operation 枚举更新为实际 26 项，明确 suggestions token 仅可访问内部 suggestions endpoint；保留 draft 状态，等待人工标准评审。
- `docs/projects/20261005-agent-followup-suggestions/{README.md,01-architecture-and-contract.md,02-platform-api.md,03-runtime-service.md,04-platform-web-handoff.md,05-verification-and-rollout.md}`
  - 更新任务完成卡、契约交接、验证证据和 `partial` 状态。

## 关键设计取舍

1. 建议使用 Platform API 传入的最近消息，不读取 Runtime 历史，避免新增历史读取权限和跨服务耦合。
2. 建议是 best-effort；模型失败返回空数组，不阻断正常聊天；权限和请求错误不伪装成成功。
3. 前端只接 Platform API，Runtime URL、delegation JWT、模型密钥和 opaque model reference 均留在服务端。
4. 不新增数据库表，不持久化建议，不建立普通 Graph Run。

## 验证

- Platform API suggestions + delegation 定向测试：8 passed，48 个参数化子测试通过。
- Platform API 路由矩阵回归：4 passed，305 个参数化子测试通过。
- Runtime Service suggestions 定向测试：10 passed。
- Platform API 与 Runtime 改动文件 Ruff：通过。
- Platform API 全量测试：323 passed、16 skipped、643 个参数化子测试；2 个既有 workspace HTML 脚本过滤断言失败，与本项目无关。
- Runtime Service 全量测试：572 passed、85 skipped；1 项因缺少 `DEEPSEEK_PROXY_API_KEY`、`DEEPSEEK_PROXY_DEFAULT_MODEL`、`DEEPSEEK_PROXY_URL` 失败，1 项因 Docker daemon 未启动失败。
- Platform API/Runtime `compileall`：通过。
- 真实三服务 E2E、真实模型性能采样和 Platform Web 浏览器验收：待前端接入及运行环境具备后执行。

## 实现期间修复的问题

- 仓库未安装 `pytest-asyncio`；新增 Platform API 异步用例改为项目现有 `asyncio.run()` 习惯，避免引入依赖。
- 新增 delegation operation 后，原契约测试固定 operation 索引失效；改为按 operation 名称和独立 cron 隔离断言，避免后续枚举扩展再次误报。
- Runtime 模型构造原本无法关闭重试；增加最小 `max_retries` 参数，只在 suggestions 路径传 `0`。
- 路由矩阵回归原先因新增 endpoint 导致固定数量断言失效；已改为按实际路由集合校验，避免后续合法路由扩展误报。
