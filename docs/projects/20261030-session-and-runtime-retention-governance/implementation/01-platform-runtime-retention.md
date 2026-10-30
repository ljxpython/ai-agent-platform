# 平台与 Runtime 生命周期实现记录

改动日期：2026-10-30；对应 P02–P08。进度见 [tasks.md](../tasks.md)。仅修改专属Worktree，不修改平台主工作区。

## 平台定义业务策略

| 位置 | 改动前 → 改动后与理由 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:2842` `create_thread()` | 客户端策略可能透传 → 平台强制idle43200分钟、可信tenant；业务期限只在平台定义 |
| 同文件 `record_thread_activity()/_touch_thread()`，发送路径 | 无显式活动 → 真实查看/发送前touch；自动运行、标题、metadata及后台读取不续期 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/retention.py:42` `register_missing()` | 无存量登记 → 从本服务ACL选取有限候选，经精确JWT读/设置引擎策略；已有策略/活动不覆盖，缺历史时间给足30天，不因404删ACL |
| `apps/platform-api/migrations/versions/20261030_0010_thread_retention_registration.py`、`infra/sqlalchemy/models.py` | 新增策略登记/尝试时间与快照已清理时间，保持可重入及失败候选公平性 |
| `adapters/langgraph/runtime_gateway_upstream.py:376`、`application/ports.py`、`presentation/http.py:821` | 增加受平台授权activity入口和引擎touch/retention适配 |
| `apps/platform-web/src/modules/chat/composables/useThreadActivity.ts:4`、`ChatPage.vue`、`DearAgentPage.vue`、`services/threads/session.service.ts` | 普通读取无法区别主动查看 → 实际打开/KeepAlive返回时报告活动，异步切换避免串会话 |

`apps/platform-api/src/platform_api/core/security/tokens.py` 与 `apps/runtime-service/src/runtime_service/auth/platform.py`/`runtime/auth.py` 增加两个精确委托，38操作两端一致。thread-touch仅既有read ACL与严格touch形状；thread-retention限定维护身份、空permissions、maintenance模型哨兵及单Thread/project策略读写，不获得会话内容读取权。`tests/fixtures/runtime_delegation_verifier.py` 改为导入公共 `RuntimeAuthError`，契约分类同步两例外。

## Runtime 兑现资源回收

- `apps/runtime-service/src/runtime_service/thread_lifecycle.py:67 _job()`：hook先核验真实task、阶段和metadata；不能伪造“会话已删除”。`before_delete()` 检查后台/inbox/Stop/外部unknown/Lease/未确认资源，并尝试受管资源核实。
- `thread_lifecycle.py:110 _bind_legacy_local()`：历史目录只接受可信metadata或唯一usage/background scope导出的canonical本地路径；scope冲突、远端位置不可确认不猜测。
- `thread_lifecycle.py:162 workspace_unused()`：验证symlink、挂载、lsof占用与目录实现安全性；`_clean_application()`核验host/node/存储绑定再回收。原计划七天等待 → 会话删除后确认释放即回收，失联则保留持久任务。
- `run_control/resources.py:18 _register()`、`workspace/locations.py:14 bind()`、`background_tasks/repository.py`、`messaging/inbox.py`、`run_control/repository.py` 和 `sandbox_node/cleanup.py`：创建入口共享引擎线程锁/删除屏障，防标记后新资源逃逸。
- `workspace/terminal.py`、`run_control/resources.py:70 reconcile_terminal_resources()`、`db/migrations/versions/0010_terminal_cleanup_binding.py`：持久化owner PID/启动时间、host、root和container，owner活着不能伪报释放；已有实例使用janitor观察删除标记。
- `thread_lifecycle.py:276 _notify_platform()`：应用资源与payload清理后HMAC通知本环境平台；失败可幂等重试。`langgraph.json`配置双hook，完成墓碑仅保留tenant/project授权字段。

## 关联记录与维护

`apps/platform-api/scripts/maintain_run_completions.py:28 maintain()` 由按时间清理提升为证据驱动清理：30天前充分终态且非HITL才清请求快照；详情30天、去重90天；origin/event/未清请求配套保留。`completion.py:203 _accept()` 对合法超90天回调duplicate ack，`_fresh_thread()`不得凭迟到schedule回调复活删除ACL。`presentation/completion_http.py:96 receive_thread_deletion()` 验签/固定body后调用 `thread_access.remove()` 清关联并审计。

`apps/runtime-service/src/runtime_service/maintenance.py:17 maintain()` 复用日志与资源对账，只操作本host有限候选，默认report、limit100、预算30秒和PG互斥。`messaging/inbox.py:299 prune_deleted_threads()` 仅completed删除墓碑满24小时且无Thread/活跃Run再删终态inbox。删除hook先清payload、succeeded外部任务正文和cleanup_confirmed资源，保留紧凑幂等/usage/Stop事实。

`deploy/systemd/`交付一套小时timer的platform/runtime实例；模板账户aiplatform、根/opt/ai-agent-platform，未安装。`scripts/local_stack_worktree.py` 确保本环境完成/删除回调密钥配对，拒绝跨环境配置。逐表规则及恢复步骤见 [运维手册](../../../runbooks/session-retention-maintenance.md)。

## 验证与影响

新增Runtime `tests/services/test_thread_lifecycle.py` 和 `tests/e2e/test_session_retention_stack.py`、Web `useThreadActivity.spec.ts`/`e2e/session-retention.spec.ts`，扩充平台completion/request/ACL/委托测试、Runtime inbox/resource/terminal/Workspace测试及 `scripts/tests/test_local_stack_completion.py`。

正式post48已锁定并重启所属API/Worker。相关Runtime10文件119passed/11skipped、PG completion35passed、修复后委托5passed/67subtests、Web8passed；三服务13项和浏览器真实模型5项通过。首次环境注入/fixture失败及修正不抹去，详见 [verification.md](../verification.md)。

本次不改变生产、主目录、其他Worktree资源，不提交Git；不承诺旧包能读取新014或降包还原文件。旧post45被schema门禁拒绝，已验停维护保留任务/恢复post48继续。未实跑Linux systemd，远端失联/恢复使用受控fixture而非真实离线节点。
