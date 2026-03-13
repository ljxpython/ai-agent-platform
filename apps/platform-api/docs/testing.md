# 测试与验证

## 1. 目标

只记录当前仓库下真实可执行、可复现的验证方式。

## 2. 当前测试层级

### 2.1 后端快速测试（默认必跑）

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
```

覆盖内容：

- 密码哈希/校验
- access token / refresh token 基础行为

### 2.2 LangGraph 真实集成测试（按需）

```bash
RUN_REAL_LANGGRAPH_TESTS=1 PYTHONPATH=. uv run pytest tests/test_langgraph_sdk_real_integration.py
```

说明：

- 依赖真实可用的 LangGraph upstream
- 默认不会运行
- 适合在修改 `/api/langgraph/*`、scope guard、upstream client 行为后执行

## 3. 前端联动验证

前端当前在 `apps/platform-web`。

### 3.1 构建验证

```bash
cd ../platform-web
pnpm build
```

### 3.2 联调建议

修改以下能力后，建议同时联调前端：

- `/_management/*`
- `/api/langgraph/*`
- auth / project scope / assistant 管理 / runtime catalog

## 4. 每次改动后的最小验收

### 只改后端基础能力

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
```

### 改 LangGraph 网关行为

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
# 如环境允许，再跑：
RUN_REAL_LANGGRAPH_TESTS=1 PYTHONPATH=. uv run pytest tests/test_langgraph_sdk_real_integration.py
```

### 改前后端联动功能

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
cd ../platform-web && pnpm build
```

## 5. 当前测试边界

目前后端测试并不重，因此需要明确：

- 当前自动化后端测试主要覆盖 auth 基础能力
- 真实 LangGraph 集成是 opt-in
- 许多管理面与 catalog 能力仍依赖手工联调或前端构建验证作为补充

## 6. 常见问题

### `ModuleNotFoundError: app`

使用：

```bash
PYTHONPATH=. uv run pytest tests/test_self_hosted_auth_basics.py
```

### 真实集成测试默认被跳过

因为测试文件里要求：

```bash
RUN_REAL_LANGGRAPH_TESTS=1
```
