# Phase 4 P4 - 交付与发布工程化

这一阶段不再只是“代码能跑”，而是要把控制面收成“别人也能拉起、能验、能发、能回滚”的最小交付面。

## 1. 当前新增交付物

### CI

- `.github/workflows/ci.yml`
  - `platform-api-v2`:
    - `python -m unittest`
    - `python -m compileall app`
  - `platform-web-vue`:
    - `pnpm lint`
    - `pnpm typecheck`
    - `pnpm build`

### 容器与部署示例

- `apps/platform-api-v2/Dockerfile`
- `apps/platform-api-v2/deploy/docker-compose.example.yml`

### 数据库脚本

- `apps/platform-api-v2/scripts/init_db.py`
- `apps/platform-api-v2/scripts/backup_db.sh`
- `apps/platform-api-v2/scripts/restore_db.sh`

### 发布模板

- `apps/platform-api-v2/docs/delivery/release-template.md`
- `apps/platform-api-v2/docs/delivery/runbook.md`

## 2. 当前设计口径

### 数据库

- 当前默认开发口径仍允许 SQLite
- PostgreSQL 仍是后续正式切主方向
- 脚本优先保证本地/演示环境可恢复和可备份

### 容器

- `Dockerfile` 先覆盖 `platform-api-v2`
- compose 示例把 `api + worker + redis` 作为最小组合
- runtime-service 和 legacy platform-api 不强绑进这个交付模板

### CI

- 先做最小流水线
- 不在这轮引入一堆外部服务型集成测试
- 重点先兜住 lint/typecheck/unit/smoke 这几条线

## 3. 发布建议

### 推荐发版粒度

- 基线分支：`main`
- 版本口径：`agent 工作台可演示版`
- 建议 tag 形态：
  - `platform-v2-demo-YYYYMMDD`
  - 或 `v0.x.y`

### 发版最小动作

1. 跑 CI
2. 跑 demo up / health
3. 前端验收 chat / operations / platform-config
4. 导出 release note
5. 打 tag
6. 保留 rollback 指令和数据库备份

## 4. 当前仍未覆盖的点

- 暂无生产级 secrets 注入方案
- 暂无完整 k8s/helm 模板
- 暂无对象存储、邮件、告警类外部基础设施接入

这些不是不做，而是不应该在这轮最小交付里硬塞。
