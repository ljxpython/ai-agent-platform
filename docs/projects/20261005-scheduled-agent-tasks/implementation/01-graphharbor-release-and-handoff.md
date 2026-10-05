# GraphHarbor 发布接入与前端交接

日期：2026-10-05。关联 T0.1b、T3.0。

本篇保留 post40 首次发布时的实施历史；其中未开放、待裁决和未验收描述均为当时状态。后续用户批准与 post41 平台实现见 [02 实现记录](02-platform-cron-and-execution-guard.md)，当前进度以 [tasks.md](../tasks.md) 为准。

## 改动

- GraphHarbor `libs/langhost/pyproject.toml`、`libs/langgraph-runtime-pg/pyproject.toml` 与 `uv.lock`：双包由 post39 升至 post40，并发布 PyPI。cron 调度、协议和验证细节见 GraphHarbor `docs/projects/20261005-cron-parity/`。
- 平台 `apps/runtime-service/pyproject.toml` 与 `uv.lock`：将 GraphHarbor 依赖锁定到已发布 post40。此改动只使包可安装，未开放 Runtime cron 原生资源。
- `docs/projects/20261005-scheduled-agent-tasks/frontend-handoff.md`：给前端同事提供页面范围、已验证能力、待定产品契约和联调门槛，明确正式 Platform API 尚未实现。
- `plan.md`、`tasks.md`、`verification.md`、`README.md` 和 `docs/CONTEXT.md`：按已发布的 GraphHarbor 能力修正过时状态，记录持续授权待裁决。

## 理由与影响

复用 GraphHarbor 唯一调度器，避免平台再建调度表和 worker。创建时身份快照不会自动执行撤权复核；平台不能在确认并实现新的授权决策前开放创建接口。前端可以按页面范围开发 mock，但联调必须以实际 OpenAPI 为准。

## 验证

GraphHarbor 双包 PyPI JSON 200、独立安装 CLI 输出 post40；平台 `uv lock --check` 和两个仓库 `git diff --check` 通过。平台真实 cron E2E 尚未运行，详见 `verification.md` Phase 记录。
