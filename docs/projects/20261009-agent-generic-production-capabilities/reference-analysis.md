# 源码对照与方案评估

## 证据范围

本项目基线为 `85d63d87bdf84dabbb963f79e8dd4b2db4432ade`。参考项目是用户提供的 open-swe，HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`，但参考工作树存在未提交修改和其他文件合并冲突；**本文依据读取时的工作树源码，不把它归为该 HEAD 的上游正式实现**。没有修改、运行或处理参考仓库的冲突。

以下 open-swe 路径均相对参考仓库根；本项目路径均相对本仓库根。关键参考文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `agent/tools/background_execute.py` | `a9dfda6bb5613768f27e88b000107be677fa1e8c9806146eb50e01e6bf8431cc` |
| `agent/tools/background_task.py` | `6eae28b1950d8e84a584a1a1f476329596c5b01ff0cdfb44271bacade79a7e3d` |
| `agent/background_tasks.py` | `f450fcd85dca482a95956d55e1fb7de599d0cb19cd93744ce93a6b9025aea276` |
| `agent/scheduler.py` | `7e8182055bc218f662bcfa636f02bdf51ea9381d0bde7aa2b0363f6cdeaa8a98` |
| `agent/dispatch.py` | `cdf800ac55b3abaae6bd9056375ff2409797ce7a733cacb570f83e0b46bb8df2` |
| `tests/tools/test_background_execute.py` | `34861fb6c88f7def0b1505ce1be9384bd6960834104f3d17cee04cb27a0cd123` |

本次验证为静态代码与文档核对；没有执行参考实现的测试，也没有验证生产环境。

## open-swe 实际怎样做

| 环节 | 代码证据 | 实际行为 |
|---|---|---|
| 显式启动工具 | `agent/tools/background_execute.py:287` `background_execute()` | 从 `RunConfig` 和 `SANDBOX_BACKENDS` 找当前 Thread 沙箱，校验命令和超时，生成 `cmd-<UUID>` |
| 非阻塞启动 | 同文件 `:147` `_launch_command()` | 沙箱内 `setsid python3 runner.py`，短时间等待 `state.json` 后返回；要求 Linux 的 `setsid` |
| 真正执行进程 | 同文件 `:34` `_runner()` | 生成的 Python runner 调用 `subprocess.Popen(["/bin/sh", "-c", command], start_new_session=True)`；合并 stdout/stderr，以 selector 持续消费 |
| 状态与日志 | 同文件 `_runner()` | `os.replace(tmp, path)` 原子替换；日志保留 head/tail，约 1 MiB；status 工具内联最多约 64 KiB |
| 超时与停止 | 同文件 `_runner()` / `control_script()` | 默认 3600 秒，最大 86400 秒；stop 文件触发进程组 TERM 后 KILL；运行丢失检查 runner PID；终态目录保留 7 天 |
| 查询与停止工具 | `agent/tools/background_task.py:64` `background_task()` | 按 task ID 路由 command / environment refresh 两个 provider；环境刷新需要管理员，线程命令借助沙箱归属隔离 |
| 建监控 cron | `agent/background_tasks.py:39` `ensure_background_task_cron()` | 用 `client.crons.create("scheduler", schedule="* * * * *")`；metadata 绑定 kind/Thread，重复 cron 后续删除 |
| 无模型 tick | `agent/scheduler.py:45` `_launch()`、`:77` `get_scheduler()` | 单节点 StateGraph 调 `monitor_background_tasks()`；会产生 scheduler Run，但轮询本身不调用 LLM |
| 找回执行环境 | `agent/background_tasks.py:138` `monitor_background_tasks()` | 读 Thread metadata 中的 `sandbox_id`，通过 `create_sandbox(sandbox_id)` 重新连接沙箱 |
| 完成通知 | 同文件 `:106` `_claim()`、`:119` `_mark_delivered()` | `mkdir notify.claim` 领用；创建 Agent Run 后 rename 为 `notify.done`；失败释放 claim，超过 300 秒的 claim 可回收 |
| 新建 Run | 同文件 monitor、`agent/dispatch.py:223` `create_durable_run()` | 完成通知使用 `enqueue`，durability=sync、可恢复流；没有轮询时向 LLM 发“继续” |
| 空闲回收 | `agent/background_tasks.py` monitor 尾部 | 没有 running/pending 时持 monitor lock，再读一遍任务后删除 cron，降低启动/删 cron 竞态 |

同事引用的 `asyncio.create_subprocess_shell()` 是概念示例，**当前读取源码的后台 runner 实际用同步 `subprocess.Popen`，异步性来自沙箱中的独立 runner，不是 Python API 名称**。

`start_new_session` 仅改变进程组/会话关系。沙箱被停止、容器退出、宿主故障、超时和资源限制仍会终止任务，不能推导为“父进程退出后必定持续运行”。

参考测试 `tests/tools/test_background_execute.py` 覆盖快返回、日志截断、并发上限、timeout/stop、cron 搜索和单次通知；Linux 进程测试在没有 setsid 的主机上 skip。`tests/tools/test_background_task.py` 覆盖环境刷新路由与管理员权限。这些覆盖不构成本项目多副本、撤权、通知响应丢失或真实 Docker 恢复的证据。

## 当前项目已有能力与真实缺口

“所有工具都同步、后端没有后台能力”不准确。当前服务大量使用 async/Worker，并支持定时 Run、运行中 inbox、交互 PTY、取消和 Workspace 执行。准确的缺口是：**shell 工具必须等命令终态才返回，且没有通用、跨原 Run 的后台命令句柄和可靠完成交付**。

| 维度 | 当前代码事实 | 缺少的能力/复用方式 |
|---|---|---|
| 等待式命令 | `workspace/execution.py:194` `execute_in_workspace()`；Showcase/DearWorkspace `aexecute()` | 工具等待结果，默认 30 秒/上限 60 秒；新增后台工具，保留原合同 |
| Docker 生命周期 | `workspace/execution.py:144` `docker_workspace_args()` | `docker run --rm`，每命令新容器，`/tmp` 是 16 MiB tmpfs；不能放入 open-swe 的 `/tmp` 目录后跨调用轮询 |
| 安全沙箱 | 同文件 Docker flags；`workspace/scoped.py::resolve_thread_workspace()` | 已有无网络、只读根、cap-drop、PID/CPU/内存限制和 scope 工作区；后台执行沿这些边界，不放宽网络或宿主权限 |
| 长期文件 | Showcase `_ThreadWorkspaceBackend` / Dear `DearWorkspaceBackend` | 文件按 tenant/project/thread 隔离，可持久；后台私有日志/控制数据需与 Agent 可写文件隔离 |
| 用户终端 | `workspace/terminal.py::TerminalSession` / 进程内管理器 | PTY 会话有 1 MiB buffer、idle/lifetime/shutdown 回收；它是人工入口、进程拥有，不能作为 Agent 的持久后台 runner |
| 定时执行 | `runtime/scheduled.py::scheduled_execution()`；`http/crons.py`；API `modules/scheduled_tasks/` | 已复用原生 scheduler，并在执行前回查授权；定时 Agent 任务和“已提交命令完成”是不同生命周期 |
| 原 Run 停止 | `run_control/service.py::advance_stop()`；`resources.py` | 有持久 Stop、租约、inbox 屏障和资源回执；现有资源表没有后台容器 handle、跨 Run 任务清单及自动通知抑制 |
| 运行中消息 | `messaging/inbox.py::MessageInbox`；`middlewares/message_queue.py` | 持久消息按 target_run_id 消费并做 checkpoint 对账；不是任意系统后台通知总线，不直接复用旧用户 authorization_ref |
| 受管新 Run | API `RuntimeGatewayService.create_thread_run()` / `launch_runtime_run()` | 已有 run_requests、未知提交状态和稳定上游 idempotency_key；应复用完成通知的幂等提交，显式覆盖 enqueue |
| 通用授权 | Runtime `runtime/auth.py`、`auth/platform.py`、`tool_access.py`；API `core/security/tokens.py` | 已有严格 operation、当前 Thread ACL、模型/tool policy；新查询/日志/取消要接入这些边界 |
| 图装配 | Showcase/Dear `agent.py`、Showcase `subagents.py`、`runtime/capabilities.py` | 公共工具通过组合根显式装配；无 Workspace 的 Reference/Workflow 不应被自动赋予 shell |
| 媒体回执 | Dear `external_task_storage.py` | 是付费图片提交去重/unknown 的业务基础，不是通用后台任务 worker；不把通用命令塞进该表或恢复此前 deferred 媒体范围 |

表中 Runtime 短路径以 `apps/runtime-service/src/runtime_service/` 为前缀；API 短路径以 `apps/platform-api/src/platform_api/` 为前缀。实施位置见 plan.md 的完整路径清单。

## 同事方案逐条判断

| 建议 | 判断 | 本平台处理 |
|---|---|---|
| 优先级低，有长命令时才需要 | 认可场景判断，但生产实施风险不低 | 用 90 秒以上本地测试/构建作为首个验收场景；没有长命令需求的图不装配，默认关闭 |
| `background_execute` 立即返回 task_id | 采纳 | 三个小工具覆盖启动、只读管理、取消；ACK 和命令完成分开 |
| 原子 status 文件 | 保留机制，改变事实源 | PG 应用表记录任务与交付，Docker inspect 提供执行证据；日志文件原子写。不信任命令可篡改的 state.json，也不只靠 PID 判断跨机器任务 |
| 每分钟 LangGraph scheduler cron | 不直接照搬 | 当前 API lifespan 已有数据库对账模式；先采用有界、可恢复的无模型 reconciler。每 Thread cron 会新增调度 Run、checkpoint 和授权配置成本 |
| 完成后 dispatch 新 Run | 采纳，但加平台治理 | 通过 Platform 当前授权/受管模型快照/稳定 key 提交 enqueue；不复制 open-swe 业务 configurable |
| `mkdir notify.claim` 防重复 | 仅能防并发领取 | 派发成功后、标记 done 前崩溃仍可重复建 Run；改为 PG 租约/fence + 持久通知意图 + 原生幂等提交与对账 |
| Head-Tail 最大 1 MiB | 采纳有界原则 | 限制采集前的内存、持久文件及 Docker logging，不只截断 HTTP 输出；截断标记也计入上限；模型读取进一步限额 |

原子 rename 保证读者不看见半份文件，并不等于跨卷事务、断电持久性或通知 exactly-once。文件 claim 过期回收也不能阻止旧监控者的迟到写入。上述故障窗口必须在本平台真实 PG/双进程/响应丢失测试中覆盖。

## 通用能力与业务属性的剥离

采纳：显式任务句柄、短启动等待、进程隔离、无模型状态检查、期限、日志限额、结果查询、取消、完成通知和受管清理。

不带入：`source/repo/github_login/triggering_user_email/environment/SourceContext`、Slack 身份和投递、Linear/GitHub issue/PR、environment refresh provider、管理员账号白名单、沙箱供应商 registry、固定 `assistant_id="agent"` 或 `platform="open-swe"`。

本平台替换为受信 tenant/project/owner/credential/graph/thread/origin_run/tool_call scope、已有 tool policy、当前 Thread ACL 和受管 Run 提交；工具只接收命令、超时或 task ID。

## 前端、后端与 Runtime 的必要性

- **前端：** 不是任务执行、监控或派发的必要条件。参考 `ui/` 中本轮检索未找到直接引用这两个工具名称的独立后台命令模块；不能因此断言参考项目没有任何通用工具展示。我们的产品需要任务可见性、取消和离线完成后重新订阅 Run，交同事按 frontend-handoff.md 实施。
- **Platform API：** 必须，决定谁能读/取消/继续执行、用哪个受管模型、如何审计及幂等；不启动 shell、不另建任务事实表。
- **Runtime：** 必须，拥有实际命令资源、期限、日志、任务事实及对账；通用实现放公共目录，Agent 只负责显式装配。

## 官方资料与适用边界

已查询 `langchain-docs` 和 `langchain-reference` MCP，资料包括 [Cron jobs](https://docs.langchain.com/langsmith/cron-jobs)、[enqueue concurrent runs](https://docs.langchain.com/langsmith/enqueue-concurrent)、[CronClient](https://reference.langchain.com/python/langgraph-sdk/_async/cron/CronClient)。官方确认 cron 调度的是 Run，enqueue 让后续 Run 排队；CronClient 还注明 license/部署可用性限制。资料不能证明本项目 GraphHarbor 与官方服务的所有语义相同，T01 必须验证本仓库锁定包的 HTTP/Worker 行为。

当前代码锁 `graphharbor==0.13.0.post43`（`apps/runtime-service/pyproject.toml:12`），但 `apps/runtime-service/deploy/Dockerfile:14`/`:15` 固定双包 post20；Compose 中没有由本次核对证明可用的 Docker 管理连接/一致挂载配置。核对前 CONTEXT 与若干标准仍写 post42 或旧 blocked；本次将 CONTEXT 的依赖描述改为源码/部署差异，未重验安装与现役版本。以代码为当前事实，记录差异供评审，不将旧状态直接视为已满足新能力的生产门禁。
