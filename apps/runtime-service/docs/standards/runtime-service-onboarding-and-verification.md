# Runtime Service 介入与验证

## 本地介入

```bash
cd apps/runtime-service
uv sync
docker pull python:3.13-slim
uv run graphharbor serve --config langgraph.demo.json --host 127.0.0.1 --port 8123
```

先运行不依赖外部服务的快速测试：

```bash
uv run pytest tests/services/showcase_demo -m "not integration and not e2e"
```

需要 Docker 隔离时运行 integration；需要真实模型或外部 MCP 时显式设置对应环境变量和 marker，凭据缺失必须失败并说明原因，禁止静默降级。

## 提交前检查

运行可靠性验证可复用本机已安装的 PostgreSQL（PATH 中的 initdb/postgres，或 macOS `/Library/PostgreSQL/17/bin`）和 redis-server。以下测试自行创建临时数据目录、随机端口和独立 API/Worker/provider，退出仅关闭自己创建的进程，不调用 Docker或使用现役数据目录：

```bash
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="/absolute/path/to/platform-api/.venv/bin/python" \
  uv run pytest tests/e2e/test_run_reliability.py -q -s
```

故障 provider 和观测 HTTP 服务使用合成凭据；真实现役 Langfuse/模型验收需单独记录，不与受控故障证据混记。前端浏览器验证由对应交接负责人完成。

- Graph entrypoint 可导入，注册文件指向正确的 `get_agent`。
- 组合测试确认工具列表、Middleware 顺序、Subagent 权限和 Context 语义。
- integration 测试确认真实文件产物、退出码、隔离和资源限制。
- HITL 测试覆盖批准、拒绝、多 action 请求和 resume。
- 跨服务改动验证请求契约、错误码、事件顺序和 scope。
- 文档链接、命令、环境变量与代码一致。

## Token 额度验证

单元与组合图测试不依赖供应商；真实账本验证显式使用隔离 `USAGE_TEST_DSN`，没有该变量的 skip 不算通过。以下 HTTP 测试自行创建临时 PG/Redis/API/Worker 和受控 OpenAI HTTP provider，不使用现役 DSN；配置均由临时 fixture 提供。

```bash
uv run --frozen pytest -q tests/runtime/test_token_budget.py tests/middlewares/test_token_budget.py
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="/absolute/path/to/platform-api/.venv/bin/python" \
  uv run --frozen pytest -q tests/durable/test_token_budget.py
USAGE_TEST_DSN="postgresql://test-user@127.0.0.1:test-port/test-db" \
  uv run --frozen pytest -q tests/durable/test_token_budget_ledger.py -k 'not real_model and not performance'
```

真实模型测试另需 `TOKEN_BUDGET_REAL_MODEL_ENV_FILE`；试验仅两次调用、Run cap 4096、单次输出 128，证据只保存用量，不输出密钥。性能矩阵由 `TOKEN_BUDGET_PERFORMANCE=1` 显式开启，记录本机 P50/P95/事务与峰值内存，不代表生产 SLO。证据与前端剩余项见 [F01 验证记录](../../../../docs/projects/20260913-dearflow-agent/15-token-budget-governance.md)。

## 故障定位顺序

Thread ACL 回查使用 `PLATFORM_THREAD_AUTHORIZATION_URL`，超时由 `PLATFORM_ACL_TIMEOUT_SECONDS` 控制（默认 10 秒）。`auth/acl_client.py` 由应用 lifespan 创建/关闭连接池，供文件路径加载的鉴权模块共同使用；不缓存授权结果。回查超时/无效响应为 503，合法响应明确拒绝为 403。日志记录项目、动作、目标数量、耗时及异常类型，不记录签名或凭据。

先看 Graph 注册和 import，再看 Context/身份校验，再看 Middleware 和工具授权，最后看模型、Docker、PostgreSQL/Redis 等外部依赖。每次失败记录复现命令、日志摘要和边界归属。
