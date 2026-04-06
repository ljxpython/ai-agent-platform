# Phase 3 完成说明

这份文档用于给当前阶段做一次正式收口，避免清单勾了一半、口径还在乱飞。

## 本阶段已完成

### P0 operations worker / queue 正式接入

- `operations` 已具备 `dispatcher / executor / worker`
- 当前默认 queue backend 为 `db_polling`
- `runtime refresh / assistant resync / testcase export` 已接入真实异步执行
- export 已支持 artifact 持久化与下载出口

### P1 policy overlay 正式落库

- `models / tools / graphs` 的项目级 overlay 已落库
- 已具备读取、更新、权限校验和前端治理页

### P2 operations 前端治理页

- `platform-web-vue` 已具备正式 `Operations Center`
- runtime refresh / assistant resync / testcase export 已统一回流到 operation 反馈链
- 详情与审计、资源详情、结果下载已建立联动

### P4 平台配置与环境治理

- `platform-config` 已从只读快照扩展到正式治理入口
- feature flags 已支持读取与写入
- 权限与审计已补齐
- 前端正式治理页已可验收

## 当前阶段明确不强推的项

### P3 PostgreSQL 正式切主

当前仍按既定决策保持：

- 开发 / smoke / 演示先允许 SQLite
- PostgreSQL 切主延后到下一阶段合适时机处理

这不是漏做，而是当前阶段的明确决策，避免在控制面主干还在快速演进时过早把数据库口径锁死。

### P5 release / harness 收口

当前已经完成：

- Harness 规范入口文档保留并纳入 README
- `platform-api-v2` README 已补齐当前阶段启动与验收口径

当前仍待后续阶段继续做：

- release checklist / release note / rollback 模板
- 一轮正式的端到端演示回归留痕

## 已完成的最小验证

- 后端导入验证：
  - `uv run python -c "import main; print('import-ok')"`
- 后端最小单测：
  - `uv run python -m unittest tests/test_operations_artifact_flow.py -v`
- 前端校验：
  - `pnpm typecheck`
  - `pnpm lint`
  - `pnpm build`

## 手动验收建议

推荐按这个顺序看：

1. `Runtime / Policies`
2. `Operations Center`
3. `Platform Config`
4. `Assistants` 重同步
5. `Testcase Documents / Cases` 导出

## Phase 4 入口

下一阶段建议从这几件事开始：

1. PostgreSQL 切主与 Alembic 升级回滚验证
2. operation 能力生产化：并发 claim、retry、SSE 或 WebSocket 推送、artifact 生命周期治理
3. release / deploy / CI 标准模板
4. Harness 与模块脚手架进一步压缩成团队开发入口
