# Runtime 后台任务、执行与清理

## 改动时间

2026-10-09

## 相关任务

- T02：应用迁移、幂等与租约存储
- T03：Docker runner、短启动回执和有界日志
- T04：无模型对账、取消与会话 Stop
- T06：通用工具、两组合根和未接入图隔离

## 改动文件

- `apps/runtime-service/src/runtime_service/db/migrations/versions/0003_background_tasks.py`
- `apps/runtime-service/src/runtime_service/background_tasks/{repository,schemas,output,service,delivery,authorization}.py`
- `apps/runtime-service/src/runtime_service/workspace/{background,background_runner}.py`
- `apps/runtime-service/src/runtime_service/tools/background.py`
- `apps/runtime-service/src/runtime_service/runtime/{capabilities,access_policy,background_completion}.py`
- `apps/runtime-service/src/runtime_service/graphs/{dearflow_agent,showcase_demo}.py`
- `apps/runtime-service/src/runtime_service/run_control/{repository,report}.py`
- `apps/runtime-service/src/runtime_service/webapp.py`

## 具体改动

### 1. 持久任务事实与并发边界

`repository.reserve_task()` 在 PostgreSQL 短事务内按 tenant/project/graph/thread、origin Run、checkpoint namespace 和 tool call 做幂等登记，并在同一事务中占用 Thread/project/host 容量。`claim_due()`、lease/fence 和 `save()` 防止重启或多副本的迟到观察覆盖新事实。终态事实、通知意图和 Stop 快照在同一应用表中保存；日志淘汰只清理正文，不清理幂等回执。

### 2. 受管 Docker runner

`workspace/background.py` 复用受管 Docker 参数，只允许显式 Docker backend 和已验证 Workspace binding。runner 从包资源读取，经 base64 编码后作为受控 Python 源码参数装入命令容器，避免 Docker daemon 解析 Runtime 容器内路径。`background_runner.py` 用独立进程组排空 stdout/stderr，使用单调 deadline 和签名 receipt；head-tail 正文上限 1 MiB，私有日志原子写入 UUID 任务目录，HTTP/工具层再分别限制 64 KiB/16 KiB。命令容器不挂 Docker socket、不继承平台/JWT/模型密钥，伪造 `state.json` 或输出不能改变任务权威状态。

### 3. 无模型对账、取消和 Stop

`background_tasks_lifespan()` 按 host 领取到期任务，不唤醒模型；`source_failed()` 通过公开 SDK lifecycle 回放区分 HITL `hitl_interrupt` 与用户取消/rollback。Runtime/Worker 重启、daemon 不可达、外部删除、deadline 和 Stop 都保留 `unknown/unconfirmed`，不伪造资源已释放。固定 Stop 只捕获已存在任务，后来的任务不会被旧 Stop 取消；报告以 `report.background_tasks` 加法摘要表达清理数量。

### 4. 通用工具与组合根

`build_background_tools(binding)` 提供 `background_execute`、`background_task`、`cancel_background_task` 三个工具。身份、五维 scope、origin Run 和当前 tool policy 在工具执行前核验；review 保留 HITL，execute deny 同时禁止后台启动；probe、maintenance、只读子图和通知完成 Run 无工具副作用。DearFlow 与 Showcase 只在组合根显式装配同一工厂，新 Agent 按 Runtime 接入规范复用四个接入点。

## 验证

- 真实隔离 PostgreSQL：幂等、两进程并发、容量、lease/fence、迁移往返、Stop 快照、1 万历史查询通过。
- 真实 Docker：退出码/期限、10 MiB 输出与日志盘占用、两任务UTF-8洪泛、OOM、外部移除、伪结果和环境隔离、create/start ACK 丢失、控制连接恢复及16并发资源回收通过。
- Runtime 定向回归、foreground/Terminal 回归和真实 API/Worker 组合通过；具体命令与数量见专项 `verification.md` Phase 记录。
- 真实受管模型 DearFlow/Showcase 各一条链路通过，完成 Run 独立计量；受控 provider 故障注入覆盖源 Run error/timeout/cancel、HITL 和关闭开关 drain。
- 关闭新提交/通知后drain，通过新迁移代码downgrade至0002，真实启动HEAD旧源码执行普通Run成功，3份后台任务回执保留。
- 55 个变更 Python 文件阶段 `ruff check` 与 `ruff format --check` 通过；后续新增测试以verification.md增量记录为准。

## 注意事项

- 新提交开关默认关闭；Docker 管理连接和共享挂载只适用于受审查的单主机拓扑。
- 后台通知的 lost-ACK 全窗口仍受 post43 缺少按幂等 key 只读 Run 回查阻塞，详见 `engine-handoff.md`；本记录不把正常 ACK/guard 回填扩大为完整 exactly-once。
