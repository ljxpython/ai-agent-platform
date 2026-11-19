# 显式新运行的生产预算版本故障与获准修复

> 本文保留Task1–4开发阶段事实；后续合并、验收和清理以[交付记录](05-delivery-and-cleanup.md)为准。原Worktree私有证据已归档至 sshmy1:/opt/mlflow-eval-platform/.local-stack/deliveries/20261119-universal-authoring/pre-merge-evidence/，下述相对日志路径以此为根。

2026-11-19，本项目没有修改 Agent 产品代码。首次显式新运行被生产预算版本差异拒绝；用户明确批准最小状态修复后，已备份两端状态、仅推进 Platform 一行版本并经原生签名接口同步。两端版本现为2，新的显式任务成功产生回答和完整 Trace，生产服务未重启。原失败保留，不改成成功。

## 修复前核实的故障事实

- 评测任务：`1b3f422b-4860-4d76-9fa6-5c31191a6af0`。
- Session：`844860c6-a35e-45d8-9f90-6ea4f3adda84`。
- Runtime Run：`df443a11-baaa-468f-8eb1-2470885b8ffe`。
- Worker 调用链：`GatewayBudgetDispatchGuard` → `ledger.admit()` → `apply_snapshot()` → `budget_stale_revision` → `runtime.gateway_budget.unverifiable`。
- 只读事务查询确认：租户 `__default` 在 Platform 数据库的预算版本为 0、已同步版本为 -1、错误为 `budget_sync_failed`；Runtime 数据库已保存版本 1。两端当前预算策略数均为 0。
- Runtime 的版本单调检查按当前设计拒绝较旧快照。现有一次刷新重试仍收到旧版本，不能修复两个持久状态的差异。本次没有重置账本、关闭守卫或重启生产服务。

现场证据在远端 Worktree 的私有目录 `.local-stack/universal-authoring/e2e/`：`new-run-summary.json`、`failed-new-runtime-run-v2.json`、`new-run-worker-failure.log`、`budget-readonly-state.json`。不复制生产配置、密钥或数据库转储入仓。

## 用户批准的最小修复范围

这是生产数据库状态变更，超出原所属测试进程操作授权。用户于2026-11-19明确回复“生产预算状态修复 同意”，以下范围据此获准并已执行。

1. 再次只读核对两端版本、空策略集和生产服务身份。若与上述条件不同，停止，不套用此修复。
2. 备份两端该租户预算状态行到私有目录。在 Platform 事务中锁定且仅更新该租户状态行，将 revision 从 0 单调推进至 2；不修改任何策略、用量、费用或 Runtime 账本，不降低版本。
3. 调用现有 `BudgetService.sync("__default")`，走现有签名和 `/internal/budgets/query` 接口同步，确认两端 revision/synced_revision 一致、原错误消失。同步失败则保留向前版本并按错误排查，不能将版本倒退当回滚。
4. 服务保持原配置与运行进程，用正常授权入口新建一次评测任务，复核新的 Session/Run/Trace、目标绑定及结果。保留原失败任务，不覆盖或伪称原任务成功。

本修复不包含修改预算阈值、授权、网关防护、应用代码、数据库结构或生产服务重启。若修复或新运行暴露新的边界问题，按实际影响重新判断范围，不自动扩大生产变更。

## 实际执行与验证

两端预算状态行在写入前备份到私有目录 `.local-stack/universal-authoring/e2e/budget-repair-20261119T044845Z/`。脚本在事务中锁定 Platform 状态行，严格核对 revision=0、synced_revision=-1、原错误及两端空策略集，确认无并发修改后，仅更新该租户一行 revision=2 及正常更新时间，再调用现有 `BudgetService.sync("__default")`。

| 检查 | 修复前 | 修复后及 Final 再读 |
|---|---|---|
| Platform revision | 0 | 2 |
| Platform synced_revision | -1 | 2 |
| Platform last_error | budget_sync_failed | null |
| Runtime revision | 1 | 2 |
| Platform策略数 / Runtime快照策略 | 0 / [] | 0 / [] |
| 生产服务身份与 NRestarts | 修复前快照 | 四项服务均与快照一致 |

没有改预算阈值、策略、历史用量、费用或 Runtime 账本，没有关闭守卫、改配置或重启生产。新运行正常产生的调用用量由原链路记录，不是手工改写账本。当前仍未配置预算策略，任务准确保留 `budget_policy_not_configured` 警告；本次没有顺带创建预算规则。

首版临时修复脚本直接导入 BudgetService 时触发既有循环导入，失败发生在数据库连接和写入前；只读复查确认两端仍为0/1。第二版按正常应用入口先初始化 `platform_api.main` 后导入服务，成功执行上述修复。`budget-repair-import-failure.json`、原脚本及日志保留，不将首版记为成功，也未为此修改应用代码。

后续正常入口显式任务 `a9ca7536-0828-43d5-985d-461bada1a7ee` passed。Session `cf4f647f-b068-4ce5-a26e-d73524ef2cad`、Runtime Run `3cfdab07-a2c1-4e09-b376-8432aaa232bf` 和 Trace `tr-db5ebd2afe90d74305979827993739c0` 经正常受控接口回读，回答与完整证据已核对，见[联合验收](04-delegated-review-and-final.md)。

成功摘要为 `e2e/budget-repair-summary.json`，备份目录保留 before/after-state、services-before/after、platform-forward-update、native-sync-result 与 summary。不得重复执行只接受0/1前置的修复脚本；版本不能倒退作为回滚。任务状态已回写唯一来源 [Task 3.2](../tasks.md)。
