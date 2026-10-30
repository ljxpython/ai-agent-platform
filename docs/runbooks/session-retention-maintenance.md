# 会话与运行时保留维护

最后核验：2026-10-31。GraphHarbor 双包 `0.13.0.post48`；平台专属 Worktree 验收通过后已停止并清理。本手册和 systemd 模板尚未安装到现役服务。

## 所有权与计时

| 所有方 | 权威事实与操作 |
|---|---|
| Platform | 定义闲置 30 天（43200 分钟），校验当前访问权限，主动查看和发送时调用引擎 touch；维护平台自己的记录 |
| GraphHarbor | 保存策略、最后显式活动、到期时间；扫描到期、冻结新工作、执行引擎事务删除；持久化任务并重试生命周期交接 |
| Runtime | 检查未结业务与资源，确认执行退出，回收本机或已绑定远端 Workspace，通知平台清理关联权限 |

列表、后台轮询、自动运行、标题和 metadata 更新不续期。前端实际打开历史会话或从 KeepAlive 返回时报告活动，发送前由平台续期。新会话由平台覆盖客户端 TTL；存量从平台 ACL 有限选取，使用精确委托和引擎 API 登记。无策略、无真实活动时间的存量从启用时给足 30 天；已有策略和真实活动时间不覆盖。引擎 404 不能作为清 ACL 的证据。

删除开始后不接受新 Run、续期或资源创建。到期遇到活跃 Run、未确认停止/Lease 或启用的 Cron 时等待；应用的 queued/claimed 消息、未结后台任务、Stop 审计、unknown 外部操作、未确认资源同样保护。Workspace 随删除流程回收，没有额外七天等待；未确认释放的任务继续重试。

## 逐表保留规则

| 数据 | 清理时机 | 保留与保护 |
|---|---|---|
| GraphHarbor Thread、Run、Cron、三张 checkpoint 表、引擎事件/重试/取消记录 | 可靠删除任务的引擎阶段，同一 PostgreSQL 事务 | 活跃 Run、未确认 Lease/停止阻塞；TTL 额外保护 enabled Cron；手动删除可清绑定 Cron |
| GraphHarbor `thread_deletions` | 完成后保留最小墓碑 | 防相同 UUID 复活；pending 保留恢复资料；完成时仅保留配置指定的 `project_id`/`tenant_id` metadata，旧 completed 墓碑不追溯精简 |
| GraphHarbor Run acceptance、webhook delivery | 各自既有规则 | acceptance 永久最小墓碑；未完成 delivery 不因会话删除被抹掉 |
| 平台 `run_requests` 请求/鉴权/上下文/config 快照 | 有 30 天前充分终态 completion，且不是 HITL 等待 | 清快照，保留请求幂等行；pending/unknown/未证实终态不按创建时间删除 |
| 平台 completion 详情及用户 receipt | 详情到期 30 天 | 清 payload/reason/error 和用户 receipt；保留事件去重事实 |
| 平台 completion event 去重 | 90 天后 | 仍关联未清快照请求时保留；签名合法且发生时间超过 90 天的迟到回调 duplicate ack，不重建 origin |
| 平台 completion origin | completed/deleted 满 90 天且无 event、无未清请求 | origin/event 配套保留，避免正常重试变成 503 |
| 平台 Thread ACL | 收到可信 HMAC 删除回调 | 清权限关联并审计；迟到 schedule completion 不得重建已删除 ACL |
| Runtime `runtime_workspace_locations` 与目录 | after_delete，确认资源无未结事项后 | 目录删除，绑定状态记为 purged；绑定事实保留；错误 host、路径、symlink、挂载、占用或失联阻塞 |
| Runtime 后台输出与 `runtime_background_tasks` | 原日志期限或所属会话删除 | 清日志并释放保留标记；紧凑幂等行保留，未结任务保护 |
| Runtime `runtime_message_inbox` | 删除 hook 先清 payload；completed 删除墓碑满 24 小时再维护 | 仅无 Thread、无活跃 Run 时删除终态 inbox；queued/claimed 保护 |
| Runtime `dear_external_tasks` | 删除 hook | 仅 succeeded 清 request/result；intent/unknown/有效 Lease 保护 |
| Runtime `runtime_run_resources` | 删除 hook | 仅物理删除 cleanup_confirmed；其他状态必须先核实释放 |
| Runtime Stop、usage、受理/幂等凭证；平台审计/usage | 既有策略 | 本次不按会话或 created_at 一刀切删除 |

SQL DELETE 由 autovacuum 回收可复用空间，不保证数据库文件立即缩小。

## 配置与只读预览

API/Worker 使用同一 `langgraph.json`，保持 `thread_lifecycle.before_delete`、`after_delete` 与 `tombstone_metadata_keys` 配置一致。任务持久化了交接承诺；去掉或改名 hook 不能跳过已接受的任务。

Runtime 需要稳定的 `RUNTIME_EXECUTION_HOST_ID`、原 Workspace/日志根、原远端 node/证书绑定，以及 `lsof`。本地目录回收要求支持抵御 symlink 攻击的 `shutil.rmtree`，且能够确认无挂载和打开文件；缺工具/权限或结果不确定时保留任务。

回调复用完成通知密钥配对：Runtime 的 `GRAPHHARBOR_TERMINAL_WEBHOOK_SECRET`/`KEY_ID` 对应平台 `PLATFORM_API_RUNTIME_COMPLETION_SECRET`/`KEY_ID`（轮换可用 verification keys）。`GRAPHHARBOR_TERMINAL_WEBHOOK_URL` 必须指向本环境平台，删除回调从同一 origin 派生 `/api/runtime/internal/thread-deletion`。禁止输出密钥和带密码 DSN。

以下命令在各 app 目录执行，使用本 app 虚拟环境，先由进程管理器或 dotenv 加载**所属环境**配置。Worktree 必须遵守 [隔离规范](../standards/worktree-development.md)，使用 `.local-stack/platform.env`/`runtime.env`，不得整体 source 或回退主工作区配置。

```bash
# apps/platform-api：平台记录预览；可选附带缺失策略登记预览
.venv/bin/python scripts/maintain_run_completions.py --register-retention --limit 100 --budget-seconds 30

# apps/runtime-service：应用日志、资源核实与 inbox 预览
.venv/bin/python -m runtime_service.maintenance --limit 100 --budget-seconds 30

# apps/runtime-service：GraphHarbor 到期/删除任务预览，显式指定所属 env
.venv/bin/graphharbor retention --config "langgraph.json" --env-file "/path/to/owned/runtime.env" --limit 100
```

以上默认只读；确认候选和环境后追加 `--apply`。limit 默认 100、范围 1–1000。平台记录维护与策略登记**各自**有默认 30 秒预算，范围 1–300 秒，不能把整个脚本称为严格 30 秒。Runtime 在动作之间检查预算；单次 SQL/远端调用仍有自己的超时。GraphHarbor 每次有限扫描，hook 每阶段 30 秒、claim 两分钟、指数重试最大一小时；没有统一 30 秒整轮期限。

平台策略登记只访问引擎 API，不扫描其库。平台记录维护、登记和 Runtime 维护各有 PostgreSQL advisory 互斥；GraphHarbor 使用持久 claim 和短事务处理并发。观察 maintenance_busy、budget_exhausted、候选/处理数、任务 state/attempts/last_error。候选数不等于已删除数；对外排障输出避免泄漏 metadata 或请求快照。

## Linux systemd 调度模板

仓库交付 `deploy/systemd/ai-agent-platform-retention.service`、`ai-agent-runtime-retention.service` 和 `ai-agent-retention@.timer`。与 [原生部署手册](native-systemd-deployment-runbook.md) 对齐为 `aiplatform` 用户、`/opt/ai-agent-platform`；变更实际部署根或账户时同步调整 WorkingDirectory、EnvironmentFile、ExecStart。

EnvironmentFile 必须为 systemd 可读取的逐行 `KEY=value` 文件，无 `export`、命令替换或依赖 shell 展开；权限限制为服务账户所需。维护进程与本机 Runtime 使用同一执行 host/配置。GraphHarbor Worker 自带每轮结束后等待 60 秒的 TTL 维护，不再用这两个 timer 复制 TTL 扫描。

以下仅为经授权部署时的安装示例，本次未执行：

```bash
sudo install -m 0644 "deploy/systemd/ai-agent-platform-retention.service" "/etc/systemd/system/"
sudo install -m 0644 "deploy/systemd/ai-agent-runtime-retention.service" "/etc/systemd/system/"
sudo install -m 0644 "deploy/systemd/ai-agent-retention@.timer" "/etc/systemd/system/"
sudo systemctl daemon-reload
sudo systemctl enable --now ai-agent-retention@platform.timer ai-agent-retention@runtime.timer
systemctl list-timers 'ai-agent-retention@*'
journalctl -u ai-agent-platform-retention.service -u ai-agent-runtime-retention.service
```

两实例每小时运行，随机延迟最多 300 秒、Persistent 补触发；oneshot 超时 120 秒。macOS 验收只检查模板映射和命令，未验证 Linux systemd 实际启停。

## 阻塞、恢复与回退

1. 通过受鉴权的 `GET /threads/{id}/deletion` 检查 state、attempts、last_error；`GET /threads/{id}/retention` 读取策略且不续期。删除可能已进入 after_delete，此时普通 Thread 404 不代表跨服务清理完成。
2. before_delete 阻塞时核实活跃 Run、后台任务、inbox、Stop、终端 owner PID/启动时间和资源凭证；正常停止并确认释放。PID 仍存活、node 失联、外部结果 unknown 不伪造成功，不手删 Lease 或改 completed。
3. after_delete 阻塞时恢复原执行 host/node、原 canonical Workspace 绑定和回调密钥/地址。确认文件句柄关闭、挂载已释放后由相同配置重试。通知失败不重建已删引擎数据；Workspace 重复清理应幂等。
4. 历史无绑定目录仅在可信 metadata 或唯一 usage/background tenant/project scope 可证实时采用 canonical 路径。scope 冲突、缺失、远端历史位置无法证明时保留任务并排查，不遍历磁盘猜归属。
5. 暂停平台/Runtime 定时维护时，同时停 timer 和正在运行的 oneshot。**这不会关闭引擎 TTL**：post48 没有独立 TTL 关闭开关。需要冻结删除时先暂停相关写入口和手动删除，停止所属 Worker 及 apply CLI；保留任务、墓碑和 Schema。API 手动删除也能推进任务，故必须一起阻断相关写流量。

```bash
sudo systemctl stop ai-agent-retention@platform.timer ai-agent-retention@runtime.timer
sudo systemctl stop ai-agent-platform-retention.service ai-agent-runtime-retention.service
```

恢复原 post48 双包与配置后重新启动所属进程，等待 claim/重试窗口或执行有界 apply。已实测停维护保留任务、重启恢复继续；旧 post45 因严格 schema head 门禁不能接管 migration014，migration014 拒绝破坏性 downgrade。不能靠降包还原文件或会话；需要备份恢复时使用独立目标并核对升级后新增事实。

实测范围、首次失败及修复记录见 [项目验证](../projects/20261030-session-and-runtime-retention-governance/verification.md)。
