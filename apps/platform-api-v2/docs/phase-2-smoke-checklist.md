# Phase 2 Smoke Checklist

这份清单只服务一件事：

> 当你要演示 `platform-api-v2 + platform-web-vue` 的第二阶段成果时，最少要过哪些检查。

## 1. 后端 smoke

在 `apps/platform-api-v2` 下执行：

```bash
uv run python -m compileall app
```

通过标准：

- 所有模块可编译
- `operations`、`system config`、`runtime_gateway` 等新增路径不报语法错误

## 2. operations 烟测

在 `apps/platform-api-v2` 下执行：

```bash
uv run python - <<'PY'
import asyncio
import uuid

from app.core.context.models import ActorContext
from app.core.db.base import Base
from app.core.db.init_db import import_core_models
from app.core.db.session import build_engine, build_session_factory
from app.modules.operations.application import CreateOperationCommand, ListOperationsQuery, OperationsService

async def main() -> None:
    engine = build_engine('sqlite+pysqlite:///:memory:')
    import_core_models()
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    service = OperationsService(session_factory=session_factory)
    actor = ActorContext(
        user_id=str(uuid.uuid4()),
        platform_roles=('platform_super_admin',),
    )

    created = await service.submit_operation(
        actor=actor,
        command=CreateOperationCommand(
            kind='runtime.models.refresh',
            idempotency_key='smoke-op-1',
            input_payload={'scope': 'platform'},
            metadata={'source': 'smoke'},
        ),
    )
    listed = await service.list_operations(actor=actor, query=ListOperationsQuery(limit=10, offset=0))
    fetched = await service.get_operation(actor=actor, operation_id=created.id)
    cancelled = await service.cancel_operation(actor=actor, operation_id=created.id)

    print('created', created.id, created.status.value)
    print('listed', listed.total)
    print('fetched', fetched.kind)
    print('cancelled', cancelled.status.value)

asyncio.run(main())
PY
```

通过标准：

- 能提交 operation
- 能列出 operation
- 能读取 operation
- 能取消 operation

## 3. 路由装载 smoke

在 `apps/platform-api-v2` 下执行：

```bash
uv run python - <<'PY'
from app.entrypoints.http.router import api_router

for route in sorted(api_router.routes, key=lambda item: item.path):
    if route.path.startswith('/api/operations') or route.path.startswith('/_system/platform-config'):
        print(route.path, sorted(route.methods or []))
PY
```

通过标准：

- `/_system/platform-config`
- `/api/operations`
- `/api/operations/{operation_id}`
- `/api/operations/{operation_id}/cancel`

都已经在正式 router 上。

## 4. 前端 smoke

在仓库根目录执行：

```bash
pnpm --dir apps/platform-web-vue build
```

通过标准：

- `runtime-gateway/workspace.service.ts`
- `operations.service.ts`
- `platform-config.service.ts`
- `chat / threads / sql-agent / testcase generate`

相关代码全部通过构建。

## 5. 演示口径

最低可演示内容：

- 运行工作台统一基座已经收敛
- threads 页面与 chat 状态语义对齐
- operations 后端协议已正式存在
- platform-config 可以返回系统级运行快照
- PostgreSQL / Alembic / future Redis 的接入边界已经冻结

## 6. 本地演示账号与启动依赖

推荐演示账号：

- 管理员：`admin / admin123456`

推荐启动顺序：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 3035
```

```bash
pnpm --dir apps/platform-web-vue dev
```

当前阶段联调依赖：

- LangGraph upstream
- `runtime-service`
- `platform-api-v2`
- `platform-web-vue`

如果只做 phase-2 smoke，不强制要求 PostgreSQL 常驻，可先用 SQLite。
