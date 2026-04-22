# Phase 2 完成记录

这份文档作为第二阶段收尾记录，也作为 `phase-3` 的输入。

## 1. 本阶段完成了什么

### 1.1 运行工作台稳定化

已完成：

- `chat / threads / sql-agent / testcase generate` 共享基座梳理
- runtime gateway 工作台服务层收敛
- `thread / run / stream / cancel / history / state` 错误态和页面态对齐
- 加载中 / 空态 / 中断 / 重试 / 无权限 交互基线补齐

详见：

- `phase-2-p1-runtime-workspace.md`

### 1.2 平台治理能力补齐

已完成：

- `operations` 模块首版落地
- `platform-config` 系统入口落地
- 权限码与审计命名补齐
- 长动作纳入 `operations` 的优先列表冻结

详见：

- `phase-2-governance-baseline.md`

### 1.3 数据与部署基线

已完成：

- PostgreSQL 切换条件冻结
- Alembic 基线已存在并继续补到 `operations`
- SQLite smoke / PostgreSQL 正式基线口径分离
- Redis / worker 接入边界冻结

详见：

- `delivery/postgres-baseline.md`
- `phase-2-governance-baseline.md`

### 1.4 前端继续迁移与收口

已完成：

- `platform-web-vue` 继续作为唯一正式前端宿主
- 运行工作台统一服务层落地
- `operations` / `platform-config` 前端 service 落地
- control plane 模块枚举继续收敛

### 1.5 验收与发布基线

已完成：

- 后端 smoke checklist
- 前端 smoke checklist
- 演示口径文档
- phase-2 完成记录

详见：

- `phase-2-smoke-checklist.md`

## 2. 本阶段验证

已实际执行：

```bash
cd apps/platform-api-v2
uv run python -m compileall app
```

```bash
cd apps/platform-api-v2
uv run python - <<'PY'
from app.entrypoints.http.router import api_router
for route in sorted(api_router.routes, key=lambda item: item.path):
    if route.path.startswith('/api/operations') or route.path.startswith('/_system/platform-config'):
        print(route.path, sorted(route.methods or []))
PY
```

```bash
cd apps/platform-api-v2
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
    actor = ActorContext(user_id=str(uuid.uuid4()), platform_roles=('platform_super_admin',))

    created = await service.submit_operation(
        actor=actor,
        command=CreateOperationCommand(
            kind='runtime.models.refresh',
            idempotency_key='smoke-op-1',
            input_payload={'scope': 'platform'},
            metadata={'source': 'smoke'},
        ),
    )
    await service.list_operations(actor=actor, query=ListOperationsQuery(limit=10, offset=0))
    await service.get_operation(actor=actor, operation_id=created.id)
    await service.cancel_operation(actor=actor, operation_id=created.id)

asyncio.run(main())
PY
```

```bash
pnpm --dir apps/platform-web-vue build
```

## 3. 当前达到什么程度

已经达到：

- 可以继续作为正式重构主线推进
- 可以对外演示运行工作台和治理基线
- 可以作为 phase-3 的稳定输入

仍未在 phase-2 强行做的事：

- 真正 worker / queue 执行器
- operation 驱动的完整前端治理页
- project policy overlay 写库和配置页
- PostgreSQL 成为唯一日常开发数据库

这些留到 phase-3，避免第二阶段继续发散。
