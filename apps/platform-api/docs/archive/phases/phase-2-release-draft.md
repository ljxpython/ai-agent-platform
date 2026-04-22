# Phase 2 Release / Tag / Changelog 草案

## 1. 发版对象

- 仓库主线：`main`
- 阶段版本口径：`agent 工作台可演示版`

## 2. 建议 tag

建议：

- `phase2-agent-workspace-demo`

如果要带日期：

- `phase2-agent-workspace-demo-2026-04`

## 3. changelog 建议结构

### Added

- `platform-api-v2` 新增 `operations` 模块
- 新增 `/_system/platform-config`
- `platform-web-vue` 新增 operations / platform-config service

### Changed

- 运行工作台 service 收敛到 `runtime-gateway/workspace.service.ts`
- `chat / threads / sql-agent / testcase generate` 状态语义统一
- 权限码与审计动作补齐到 operation / config 维度

### Infra

- `operations` Alembic migration 新增
- PostgreSQL / Alembic / Redis 边界冻结
- phase-2 smoke checklist 与 completion 文档补齐

## 4. 发布前最少检查

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
pnpm --dir apps/platform-web-vue build
```

## 5. 对外描述建议

当前版本适合这样描述：

> 第二阶段已经把 agent 运行工作台和平台治理基线收住。
> 前端正式宿主继续是 `platform-web-vue`，后端正式重构主线是 `platform-api-v2`。
> 当前版本已经适合演示与继续迭代，但真正的异步 worker、policy overlay 配置页和 operation 治理页放到 phase-3。
