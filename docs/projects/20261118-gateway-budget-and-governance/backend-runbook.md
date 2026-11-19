# 预算后端启用、恢复与兼容回退

> 2026-11-18；供后端实施与前端联调使用。当前代码仅在独立 Worktree，未提交、未合并、未部署生产。性能阈值及人工治理验收尚未签定。

## 1. 本地环境

Worktree：`/Users/<name>/PyCharmMiscProject/ai-agent-platform-gateway-budget`，分支 `feat/gateway-budget-and-governance`；环境 `wt_1c4f0f7fb905`。Web `http://127.0.0.1:24824`、Platform API `http://127.0.0.1:26911`、Runtime `http://127.0.0.1:24254`。端口只对应本环境，以 `.local-stack/environment.json` 和 `local-stack.sh status` 为当前事实。

数据库和 Redis / Workspace / 依赖均独立；不使用主工作区的 `.venv` 或 `node_modules`。私有配置、凭据和运行日志位于 `.local-stack/`，不要复制进交接、Git 或截图。

```bash
bash "scripts/local-stack.sh" status
bash "scripts/local-stack.sh" start
bash "scripts/local-stack.sh" restart-one platform-api
bash "scripts/local-stack.sh" restart-one runtime-api
bash "scripts/local-stack.sh" restart-one runtime-worker
```

当前受控模型验证使用临时本机 HTTP 服务，其费用和回答均为合成数据。公共模型管理接口仍保留回环/私网地址防护，只有隔离测试夹具直接登记了临时回环模型。验证结束后临时 HTTP 服务关闭，不把该模型作为同事可用的线上模型。

首选实际 catalog provider 为 `maomaoai`、模型 `deepseek-v4.1-flash`。本次真实请求返回 403 `insufficient_user_quota`；需要供应商账户维护者补充额度后再验真实成功路径。未继续盲重试，也未悄悄换用其他付费供应商。

## 2. 启用顺序与执行域门禁

1. 排空当前 running Runs，暂停接入新任务并保留停止/查询能力。先备份双库及配置，记录原迁移版本。
2. 部署带预算支持的 Platform API、Runtime API 和全部 Runtime Workers，执行 Platform API `20261118_0015`、Runtime `0012_gateway_budget` 与 `0013_budget_worker_fence` 迁移。本地统一使用 `bash "scripts/local-stack.sh" migrate`；不要从别的 Worktree 取配置。
3. Runtime API / Worker 同时配置 `RUNTIME_USAGE_ENABLED=true`、`RUNTIME_GATEWAY_BUDGET_ENABLED=true`。控制面和 Runtime 复用已配置的 delegation secret，但预算使用单独 purpose、方法/路径/body/时效/nonce 签名域；密钥至少32字节。
4. 通过真实认证的预算接口检查同步能力，再保存策略。保存 REJECT 前会先检查并激活数据库 Worker 栅栏；激活时若仍有 running Run，返回不可用，先排空再重试。
5. 栅栏激活后，只有新代码且两个开关都启用的 SQLAlchemy Worker 连接带有 session capability，可以将持久 Run 从 pending 转为 running。旧版本或关闭开关的新版本无法领取，不会绕过预算。

**执行域约束：** 栅栏是整个 Runtime 数据库级、粘性的执行门禁，不只影响配置了 PROJECT REJECT 的项目。预算同步/检查会激活它，包括空策略集的能力检查。必须统一升级/切换执行域，不能声称任意新旧 Worker 混跑是透明滚动升级。默认开关为 false；激活后把开关改回 false不会撤销数据库保护。

## 3. 记账和恢复

`runtime_usage_calls` 为原始事实，价格快照固定；`runtime_budget_windows / contributions / outbox` 是同事务派生。所有调用写入先取 tenant PostgreSQL advisory transaction lock；锁不跨越模型请求。开始记录不能落库则不发模型；已准入在途允许超支。

状态检查会核对窗口累计与逐调用计入总额；不一致时在同一受锁事务内从原调用事实重建，再作准入决定。窗口丢失也从事实重建。恢复失败返回不可用，不先暴露一个临时零余额。显式完整重建入口为 `gateway_budget.ledger.rebuild(conn, identity)`，调用方必须先 `ledger.locked(conn, tenant)`；identity 为 tenant、policy_id、definition_version、window_start。它使用调用开始时价格，不读取当前 catalog 价格。

普通只读 Usage 查询保留 750ms statement / 250ms lock 超时；带租户栅栏的逐调用记账/准入为 2s statement / 1s lock，控制面同步与首次回填为 4s / 1s，HTTP 调用也有界。本地8并发实测触发原250ms等待后，先去掉无关项目窗口处理，再调整该写入边界并复测；不放宽只读查询。超时或累计数值溢出时事务回滚；REJECT 停止新增调用，维护任务/下一次同步重试。不能靠提高额度掩盖数据缺失，也不无限放宽锁等待。

正常调用持30秒租约，每5秒续约；租约失联后，未闭合且费用未知的调用使窗口不可核实。进程重启或数据库恢复连接不会自动把未知补成0。确有可信用量时，按原调用主键及原价格补记，仓储只补差额；无法确认的供应商费用继续未知。已持久化的 `degraded` 区间也不能仅凭重建金额而清除，需要人工核对该区间原始证据。

Thread 删除不删除独立调用账本和预算；Trace 从来不是记账来源。运维清理不能删除有效窗口重建所需的调用或降级事实。回填发现受信已结束Run没有Usage时，将缺口持久保存为 `runtime_usage_runs` 的 `graph_id=budget_coverage_gap`、`degraded=true`，Thread删除后仍保留。解除缺口前必须核对原执行证据并可信补记/修复，不能直接删标记或靠调额恢复。

对启用采集之前未纳管的供应商调用不制造费用；上线前必须确认该自然周期的纳管范围和历史采集覆盖，存在已知采集缺口时保留未知/停止限制，不能把本地夹具测试当成生产覆盖证明。

## 4. 通知重试

Runtime outbox 在结算/策略应用事务内写首次超额事件，维护循环每5秒检查，失败至少30秒后重试。Platform API 同事务写事件收据、管理员站内信和各外部渠道任务后 ACK。外部任务由平台维护循环重试。

诊断先只读检查所属库：outbox 的 attempts / next_attempt_at / delivered_at / last_error，平台 event_receipts 和 deliveries。错误只记录安全代码，不存供应商提示词或密钥。重试保留原 event_id，不重新生成窗口或重复结算费用。站内同事件、同接收人一份；外部发送成功但记录前退出可能重复，需要外部用 event_id 去重。

## 5. 兼容回退与再次升级

只读前端或不影响预算的控制面可按兼容范围回退。执行服务回退必须保留当前 guard / 账本 / Worker fence，或暂停整个受保护执行域的新任务。原版本缺少 session capability 时，数据库拒绝其领取 pending Run，这是预期保护，不应通过删除 trigger 或清空 active 来恢复。

账务迁移拒绝破坏性 downgrade；不删除策略、窗口、计入记录、费用、事件或迁移版本来伪造回退成功。暂停期间仍应提供历史读取及按现有权限停止的能力。再次升级后，全部执行进程恢复兼容配置，核对金额、版本、未知调用和通知，再恢复接入。

本轮已执行新/旧 session 的真实数据库领取测试、开关关闭后拒绝，以及 API/Worker 实际重启后的金额和事件重投检查；不等同生产版本包的全栈回退演练。完整发布仍需人工确认性能阈值、历史覆盖、备份/恢复和前端联合验收。
