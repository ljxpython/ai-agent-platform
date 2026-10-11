# 完成续接与合并接线修复

## 日期与任务

2026-10-11；K03/K04，K05/K06 故障验证增量。实施目录为 `~/.codex/worktrees/b01-closeout/ai-agent-platform`，未修改前端代码。

## 业务修补

- `apps/runtime-service/src/runtime_service/runtime/auth.py`：合并遗漏 `credential_id` claim 和 `VerifiedDelegation.credential_id`，认证后的 Thread/Plan/后台与服务凭据调用仍读取此字段。恢复原字段，以关键字同时传递 credential、callback_context、run_acceptance，避免位置错配。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py::launch_runtime_run()`：接受回执分支签发提交委托时保留 `origin_ref`，使固定接受回执与终态 callback 来源共存。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/background_completion.py::deliver()`：受信完成续接不能复用源 Run 的 `plan_execution_id`。只在此服务端入口剥离源执行标识，仍由正常 launcher 创建新标识；普通请求的私有字段拒绝保持有效。
- `service.py::launch_runtime_run()` 与 `presentation/http.py::get_runtime_gateway_service()`：用既有 delegation secret 在新执行 Context 确定后重签 completion marker，再序列化和持久保存最终 bytes。marker、创建委托、记录 Context hash 必须一致。独立 model-config secret 不用于替代 delegation secret。
- `apps/runtime-service/src/runtime_service/background_tasks/repository.py::list_tasks()`：最新自动接续候选仅 `delivery_state='accepted' AND stop_id IS NULL`；suppressed 的原 run_id 留在详情供精确 Stop/对账，不投影为自动候选。候选查询仍独立于当前分页。

核心差异是 `source_context.plan_execution_id` → launcher 的新执行标识；`marker.context_hash` → 最终 Context hash。无新公开 DTO、权限、回执页面或 Local runner。

## 测试与夹具

- Platform `tests/test_run_acceptance.py` 补 Plan Thread/state 夹具、callback/receipt 共存、最终 Context 签名与普通注入拒绝；真实 SQLite 触发器分别拒绝 reserve、最终 bytes 保存、接受后 run_id 回填，进程中断模拟发生在发送边界。重开连接后只读查询保存身份，零替代 POST。
- `tests/test_runtime_gateway_sdk_adapters.py` 用 HTTP transport 断言中文原字节、固定 key/digest、GET 空 body 与正确路径。
- Runtime `tests/runtime/test_platform_auth.py` 断言凭据、callback 与接受扩展同时保留；`tests/background/test_repository.py` 增加跨分页候选和两个独立控制进程的领取/死亡租约接管/旧 fence 拒绝。
- `tests/e2e/test_background_tasks.py` 的 lost ACK 在源码与最终 Linux 镜像分别参数化；Worker=0、API 实际重启、20 次真实只读 GET、原 Run/ledger 和完成模型计数均取证。原 2 秒命令可能早于故障设置完成，改为文件屏障，按“停 Worker → 设置故障 → 释放命令”确定触发边界。
- `tests/fixtures/run_reliability.py` 只记录安全事件/次数，故障位于真实提交已接受后丢响应；GET 重复不创建 Run。生产代码不增加故障选项。
- 2026-10-11 重启验收首轮 1 failed（1091.55s）：固定 120 秒命令在 API/Worker 重启完成前已终态，随后等待 running 超时。改为文件屏障；同样固定 drain/模型撤权、Stop 后新任务的测试时序，门禁仍验证真实取消/开始前拒绝，不扩大业务默认期限或增加模型审批次数。
- 文件屏障复验 `phase-source-gated.xml` 中重启/异常清理与审批/固定 Stop 两条通过；原生超时条因等待第二次模型调用失败（整轮 2 passed、1 failed，3100.72s）。实际 PG 已证明源 Run 为 timeout，任务 cancelled/confirmed/suppressed。移除这一无效时序前提，取消条单独使用较长的测试期限并先核实任务与源 Run 正在运行；两种源异常的命令均改屏障，等待真实取消而不先自然结束。仅复验这两种源异常、排空回退和模型撤权，生产期限/审批政策不变。
- `phase-source-recovery.xml` 随后 1 failed（903.35s）：60 秒原生期限在本机首次后台登记前触发，任务列表仍为空。该场景改为启动时配置原生 300 秒、模型等待 600 秒、命令屏障 900 秒，明确保证要验的期限顺序；不额外重启 Worker 设置同样的期限。`tests/e2e/test_run_reliability.py::terminal()` 允许此条使用 360 秒的测试等待，其余调用保留原 180 秒。后续报告为 `phase-source-stable.xml`，两失败轮均保留。
- `phase-source-stable.xml` 1 failed（1461.89s）：上述超时/取消/关闭后排空与迁移回退均通过，Git 归档因从 Runtime 子目录解析仓库根相对路径失败。归档明确设置仓库根 cwd 并限制 30 秒；独立预检查确认旧提交 322 个文件、无后台执行钩子且凭据字段存在。复验分别记录 `phase-source-closeout.xml` 与 `phase-model-guard.xml`，保持独立资源；冷启动检查统一使用本场景 360 秒测试预算。
- `phase-source-closeout.xml` 1 failed（2015.79s）：超时/取消/关闭后排空、保留迁移和旧进程启动已通过，普通 Run 在旧 Runtime 因 `runtime.context.unknown_field: plan_execution_id` 失败。原基线 `85d63d87` 早于 Plan Mode；改用后台合并的第一父提交 `bd476ae62a61acb7c55bc0f08eba3645ce50daf0`，已核实包含 Plan Mode/credential、没有后台钩子，应用 head 为 `0003_token_budget`。测试与运行手册使用这个实际匹配组合，不剥离当前生产 Context 或弱化签名。复验报告单独保留。`phase-source-matched.xml` 又在排空启动前提失败（1746.40s），PG 实证为 exit=0、start 未确认；新增等待任务实际 running 才停应用，并发现 downgrade 后需 stamp 掉旧源码不认识的 `0003_background_tasks` 分支标记。源超时/取消与排空回退拆为独立用例，新轮为 `phase-terminal-and-rollback.xml`。
- `phase-model-guard.xml` 1 passed（951.77s）：完成 Run 已接受/pending 后撤销模型，执行前拒绝且完成模型调用为 0；当前 owner/shared-read/cancel-denied/cross-project/revoked ACL 全部通过。
- 回退失败轮 `final-rollback-stamped2.xml` 证明直接降到 Token 分支后 stamp 不能消除另一分支。`test_disabled_drain_preserves_receipts_and_matching_source_rollback()` 改为同一锁/事务内 downgrade 共同父节点 `0002_run_control` 后 stamp `0003_token_budget`，旧服务启动前后比对后台回执及单一 head，ready 等待检查进程存活。`final-rollback-stamped3.xml` 1 passed（308.04s）：排空、旧 API/Worker 启动、普通 Run 成功与回执逐字段保留全部通过。运行手册同步准确步骤；没有改变生产迁移或删除接受事实。

## 验证进度

已通过 Platform 完成 Context/后台定向 60 项、四个持久化故障边界 4 项、Runtime 凭据与 callback 46 项；更早 Runtime 接线 180 项通过。最终冷镜像、真实两 Linux controller、lost ACK notify/Stop/撤权、两根真实模型、源重启、审批/固定 Stop、模型撤权及匹配版本排空回退已通过。独立系统 Final 为 6 passed / 9 deselected（2285.02s），包含原生超时/取消、匹配源码回退及最终 Linux 正常/故障链；业务源码 12 个冻结摘要不变。非前端范围已完成，完整计数、限制和交付见 [verification](../verification.md)与[收口记录](04-nonfrontend-final.md)。

失败和中断轮保留在本 Worktree `.local-stack/verification/`。首个镜像的凭据遗漏、完成 Context 接线失败、原 2 秒命令的错误时序以及一轮 macOS Platform uvloop abort 均不能计为通过；后续只使用修复产物与确定触发的故障证据。
