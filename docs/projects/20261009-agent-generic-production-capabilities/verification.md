# Agent 通用后台非阻塞任务能力 - 验证计划和记录

## 当前结论

当前状态 `partial`。用户已批准 D01-D06，T02/T03/T04/T06/T07 与 F01-F11 已完成；正式 post45 锁/部署断言、接受回执三条发布后联合链路已交付，B01 解除。T01/T05/T08 的完整矩阵、新 Linux 应用镜像及后端 Final、T10/F12 全栈 Final 尚未收口；A/B 前后端独立验收已完成。以下历史 Phase 与失败记录保留，不能把引擎专项 Final 当作本专项全范围 Final。现役未部署、未调用生产 API。

本轮源码对照的基线、参考文件哈希、官方资料和环境限制见 reference-analysis.md。文档检查记录在“规划交付校验”，不得写成后端/全栈 Final。

## 测试环境与证据要求

- 使用隔离 Platform/Runtime PG、Redis、原生 API/ProductionWorker，分别记录服务地址、测试 DB/资源域、包版本/来源/哈希、迁移 head、镜像摘要和资源限制。不得用正式数据库做故障注入。
- Docker 相关测试必须在真实 Linux 容器与受管 daemon 跑；macOS 宿主或 LocalShell/mock 的通过不能替代 Linux 进程组、OOM、挂载和容器恢复。
- 多副本用两个独立 OS 进程/API/Worker，不用同一个 asyncio loop 两个 coroutine 假装恢复。冻结 source Run/context、task/event/container/run IDs，观察副作用计数。
- 模型费用验证至少一条真实受管模型完整链；故障测试可使用受控模型/tool fixture，但记录哪些不是实际模型。轮询模型调用数必须为零。
- 性能值是本专项验收建议，D05/T01 冻结后才作为门禁；当前仓库无已批准生产 SLO，不把下表拟目标写成现有达标事实。

## 单元和组合测试

实际文件：`apps/runtime-service/tests/background/{test_repository,test_service,test_tools_and_assembly,test_http,test_output,test_completion}.py`、`apps/runtime-service/tests/workspace/test_background_execution.py`、`apps/platform-api/tests/test_background_tasks.py`。下面名称是验收语义，不冒充实际pytest函数名；Phase记录与对应文件才是执行事实。

| ID | 拟用例 | 必须证明 |
|---|---|---|
| U01 | `test_background_input_scope_and_permissions` | 空命令/过长命令/bool 或越界 timeout/伪造 scope/execute deny/拒绝审批/只读子图不启动容器 |
| U02 | `test_replay_keeps_task_and_digest_conflicts` | 同原 Run/namespace/tool_call 返回同 task；日志过期后重放仍不执行；不同命令/期限/binding 摘要冲突，不二次启动 |
| U03 | `test_capacity_reservation_counts_unknown_and_cancelling` | 事务内 Thread/project/host 上限；unknown/取消未确认占位，不先查后写超额 |
| U04 | `test_container_args_reuse_foreground_security` | network/mount/user/cap/memory/PID 等一致；后台无 --rm/restart，普通 execute/Terminal 保持原语义 |
| U05 | `test_exit_codes_do_not_invent_timeout_or_cancel` | 非零 exit、124/137、OOM、命令成功与 CLI 成功分离；状态文件/输出写“完成”不能影响事实 |
| U06 | `test_output_head_tail_bytes_and_unavailable` | UTF-8/二进制/超大日志/分帧/截断标记均限额，丢尾/损坏日志返回不可用；ANSI/HTML 不变权限 |
| U07 | `test_cancelled_error_propagates_and_cleanup_is_bounded` | 请求取消不能变普通成功 ToolMessage；创建晚到/重复取消不遗弃清理，超时只能报告 unconfirmed |
| U08 | `test_expired_lease_rejects_late_observation` | lease/fence CAS，迟到旧 owner 不能回写或重复通知；远端等待无开放 DB transaction |
| U09 | `test_terminal_and_delivery_intent_commit_together` | 终态+event 原子；相同 event/key/body；已接受/未知提交回查原 Run，不新建替代事件 |
| U10 | `test_stop_snapshot_does_not_capture_future_tasks` | Stop 固定已存在 task/event；无活动 LLM Run 也清理；后来的用户 Run/其他 Thread/PTY 不被误取消 |
| U11 | `test_completion_guard_precedes_model_and_mcp` | 伪 marker/cron 混用/maintenance/撤权/Stop tombstone 拒绝发生在模型/tool 准备前；通知 Run 不再启动后台任务 |
| U12 | `test_background_dto_and_delegation_allowlists` | scope/task/graph 归属、三 operation 隔离、no-store、分页过滤先于 limit，未结标志/最近完成Run不受分页影响且不越权；未知 DTO/私有字段/输入拒绝及安全错误 |

## 真实集成与故障窗口

实际入口：`apps/runtime-service/tests/e2e/test_background_tasks.py` 复用 `tests/services/dearflow_agent/test_tool_error_platform.py::stack`；PG故障/容量在 `tests/background/test_repository.py`。没有额外durable/integration目录或第二个服务启动管理器。

| ID | 操作/故障 | 预期证据 |
|---|---|---|
| I01 | 启动 90 秒命令，工具返回后继续一个只读工具/模型回合 | handle 已开始、第二动作发生在命令终态前；真实 stdout/exit/成果可查询 |
| I02 | 20 个并发提交，同 key 重放和不同 key 超上限 | 不超过冻结额度；同 key 只有一个容器/真实业务副作用；冲突可解释 |
| I03 | 在意图落盘、create 接受、start 接受、handle 保存各边界杀 Worker/丢响应 | 名称/labels/ID 对账；原命令执行至多一次，unknown 不重新 start 已退出容器 |
| I04 | 两 API 对账抢占、lease 过期后另一进程接管，旧结果迟到 | 新 fence 生效；只有有效观察和一个通知意图，不覆盖新状态 |
| I05 | Runtime API/Worker 单独重启、daemon 不可达/恢复、容器 OOM/消失、机器模拟重启 | 管理重启重连；真正任务丢失如实 unknown/failed，不自动重跑；容量与 cleanup 不虚假释放 |
| I06 | 终态写库前后、outbox 领取、平台 reserve、原生接受、返回 run_id、ack 落盘边界分别故障 | 同一 event 对应一个接受的 Run；事务回滚无“已终态没通知记录”；平台/run 原生 ACK 丢失复用原 key |
| I07 | 活动 Run 与通知同时提交、检查空闲后新用户 Run 抢先；有 HITL/澄清 | enqueue 不 interrupt；审批保持真实 interrupt，不自动 resume/approve，普通 cron 仍工作 |
| I08 | Stop 与后台提交/通知派发/原生接受并发，响应延迟后到达 | 固定 snapshot/抑制 tombstone；晚到 Run 的开始前 guard 零模型/工具；已开始执行的固定目标正确取消 |
| I09 | 服务账号吊销/用户或项目删除/Agent禁用/模型与工具撤销/Thread删除；长任务 token 过期 | 后续执行拒绝、公开读按当前 ACL；已拥有资源可清理；不重建 Thread，不泄露回执/模型密钥 |
| I10 | 伪 HMAC、过期戳、正文替换、ID/owner/credential/graph 互换、HTTP 503/504 | 受信入口绑定用途/时间/scope；失败无新执行；unknown 保持查询路径，公共错误无正文/命令/handle |

## 端到端关键链路

后端 E01-E09 可以在前端交付前执行；不能等待同事页面完成才补后端故障测试。E10 为前端同事和后端联合验收。

| ID | 完整链路/操作 | 验证点 |
|---|---|---|
| E01 | 受管模型 -> Showcase -> 后台命令 -> 并行做其他工作 -> HTTP查结果 | 非阻塞、真实 exit/成果、无 extra Model polling、实际 task/Run/trace 关联 |
| E02 | 受管模型 -> DearFlow，同一类非业务命令 | 复用同一工具实现，没有 DearFlow mode/媒体/部署字段；protected mount/skills 保持 |
| E03 | 原 Run 正常结束、浏览器离线 -> 任务完成 -> Platform -> enqueue -> Worker | 创建同 Thread 的一个新 Run，输入为安全完成提示；用量/费用计入新 Run，原 Run 状态不变 |
| E04 | 后台任务运行期间用户会话 Stop；之后新的普通用户 Run | 旧任务/通知固定停止，新任务可启动；Stop摘要从 pending 到 confirmed，后续 Run 不被旧取消影响 |
| E05 | 原 Run timeout/error，后台命令超出原 attempt 时间 | 按批准语义清理、抑制；不能因为增加 shell 期限绕过原 Run治理；与正常 success 延续区分 |
| E06 | review/workspace_write/full_access + HITL 拒绝/编辑/批准/显式恢复 | 按冻结政策执行，原 call 身份/摘要稳定；拒绝零容器，resume不覆写新配置 |
| E07 | 无活动模型 Run但有旧后台任务，执行现有会话 Stop | 真实命令停止且资源清理；no_active_run 只指 LLM，不显示后台仍活跃时“全部已停止” |
| E08 | 成功通知前撤销原用户/服务账号或模型权限；平台离线后恢复 | 不新建或开始未授权 Run；已完成命令可由仍有 read 权限者查询；不靠过期 token 续接 |
| E09 | fork/time-travel/probe/maintenance、Reference/Workflow/LocalShell | 新 scope不接管旧 task；probe/维护零资源；无 Workspace 图不露启动工具；旧 execute/inbox/cron/Usage 通过 |
| E10 | Web -> API -> Runtime，关闭/刷新/切换后任务完成，重新打开页面 | F01-F12；任务可见、通知 Run被发现并SDK订阅、日志纯文本、取消真实确认、响应式/撤权/竞态正确 |

## 性能和资源边界

| ID | 拟验收 | 测量/判定 |
|---|---|---|
| L01 | 暖镜像 90 秒命令启动 ACK 目标不超过约 2 秒，正常第二动作不等待它 | 记录 p50/p95/最大值和 CPU/版本；冷 image缺失明确失败，不在线 pull |
| L02 | 连续输出至少 10 MiB、UTF-8 和无换行；两任务同时洪泛 | runner持续排空；private body<=1 MiB、HTTP<=64 KiB、Tool<=16 KiB、Docker log<=冻结轮转量；验证实际磁盘而非仅返回字符串 |
| L03 | 4 个 Thread/host 最大16任务，重启/取消/正常完成后观测进程与资源 | 额度无超卖、事件循环不被 DB/CLI阻塞、容器/FD归还；临时故障 unconfirmed 留事实，不能伪造归零 |
| L04 | 有代表性的 1 万条历史记录 + 到期扫描/分页/日志保留淘汰 | 查询按scope/index后分页；没有全表或全目录每 tick 扫描；私有日志含临时文件不超过批准总额，容量不足在启动前拒绝；记录吞吐与延迟再冻结门槛 |

## 安全与回退

| ID | 验收项 | 通过条件 |
|---|---|---|
| S01 | 五维 scope、三 operation、任务 ID/分页 cursor 替换、管理接口隔离 | token不能扩大用途；目录/模型/原生 Run/其他 tenant/project/thread/graph/资源拒绝，私有handle不公开 |
| S02 | 写入 state.json/伪完成日志/伪 marker/输出脚本；Task日志软链逃逸 | 文件/文本不能改变 Task权威状态或 grant；私有日志不进workspace tree/fork/zip，IO不跟随逃逸软链 |
| S03 | 检查 shell env/进程参数/日志/审计/错误/流 | shell中无平台/JWT/模型密钥及Docker socket；控制错误无宿主路径/命令；日志按权限输出不执行HTML/ANSI |
| S04 | 取消/已接受通知后撤权、多浏览器/服务账号 | 新执行与固定清理回执权限分别受控，后台回执例外不扩大公开读权限；HITL不被自动恢复 |
| S05 | Public input/config/context/metadata 注入私有 marker/lease/container/token | 入口拒绝，公开HTTP/SSE/history剥离；普通用户业务日志/成果不被当失败槽位错误清洗 |
| R01 | 空库/现有库迁移+正式双包/runner镜像冷安装 | 唯一正式版本/产物hash/迁移head一致；post20镜像不冒充post43；新增包和资源可导入/执行 |
| R02 | 关闭新启动/通知，仍有running/unknown/queued通知，执行drain后回退 | 不漏已有资源；应用回退前完成或明确受控处置所有任务；旧代码忽略加法表，无删Workspace/回执 |
| R03 | TTL/磁盘限额清理与Thread删除、非法symlink、其他任务目录同名；日志删除后重放旧checkpoint | 只处理已验证归属的终态私有文件；活跃/unknown不得盲删；保留最小去重/Stop回执，旧call不重复执行；DTO如实返回日志不可用；按运行手册完成unknown/drain接续 |

## 执行命令约定

依各服务 README 使用隔离环境执行；环境变量只启用测试fixture，不能加载现役DB或把测试密钥带入公开输出：

```bash
BACKGROUND_TEST_DSN="<isolated PG>" BACKGROUND_DOCKER_TEST=1 uv run --frozen --project "apps/runtime-service" pytest "apps/runtime-service/tests/background" "apps/runtime-service/tests/workspace/test_background_execution.py" -q
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="<platform-api venv python>" uv run --frozen --project "apps/runtime-service" pytest "apps/runtime-service/tests/e2e/test_background_tasks.py::<target_case>" -q -s --tb=short --basetemp="<new evidence directory>"
uv run --frozen --project "apps/platform-api" pytest "apps/platform-api/tests/test_background_tasks.py" "apps/platform-api/tests/test_runtime_delegation_contract.py" -q
```

阶段检查只跑必要增量/相关回归；阶段结束保留证据。全部功能合并后执行冻结范围的全量单元/集成、E01-E10、安全/资源/回退；格式/lint与必要类型检查按仓库门禁。未具备真实环境的项写未执行/blocked，不把 skip算通过。

## 验证记录

### 2026-10-09 规划交付校验

- **执行人：** Codex。
- **已核对：** 参考后台命令/工具/监控/dispatcher/测试、当前 Workspace/Stop/inbox/cron/Run幂等/权限/组合根/前端入口；官方 MCP资料；参考工作树有修改与冲突，依据已记录。
- **已发现：** 原命令最长60秒/临时容器；参考claim非exactly-once；Runtime锁post43与Dockerfilepost20不同；此worktree未见Runtime服务虚拟环境，未运行功能验证。
- **文档检查：** 专项范围通过。用脚本读取 `scripts/check_docs.py` 的同一 `check_file()` 规则检查本专项 6 份文档及已更新的 `docs/CONTEXT.md`、`docs/FEATURES.md`，结果 `changed_documents=8 changed_errors=0`；另以 Node 检查本专项本地 Markdown 链接、JSON 示例、代码路径引用、围栏、任务/验收矩阵，结果 `documents=6 local_links=6 json_examples=2 existing_paths=57 planned_paths=25 tasks=10 verification_cases=44 frontend_cases=12 failures=[]`；`git diff --check` 通过，新增未跟踪文档另检查尾随空白与冲突标记，均无问题。仓库全量 `python3 scripts/check_docs.py` 仍报告 38 条既有绝对路径问题（`docs/knowledge/*`、既有项目文档），本轮未修改这些文件，不能把全仓结果写成通过。
- **功能结论：** 未实施；待人工评审。没有Phase功能通过或Final结论。

### Phase 验证记录

#### T01 执行域与正式包门禁，2026-10-09

- 已安装锁定的 GraphHarbor/graphharbor-runtime 双包 post43；真实原生 API/Worker enqueue 和固定 Stop 用例保留在 `tests/e2e/test_background_tasks.py`。
- 镜像冷构建 `docker build --progress plain -t runtime-background-verification:20261009 -f apps/runtime-service/deploy/Dockerfile apps/runtime-service` 成功，双包版本断言通过，镜像 `sha256:c1e60072076af8c0f5640bf88048b86ef9f1729bf24ad80b3e5112c69eb515d0`。这是阶段产物，新增迁移索引等后续改动需要再构建最终产物。
- 前两次构建分别受 PyMuPDF 下载超时、容器 DNS 故障影响；Docker daemon 恢复后重试成功。真实完成通知 F 轮受 Docker 不可用影响失败；G 轮因测试 PATH 漏 Docker 失败；H 轮修复环境后通过，不能将失败轮算通过。
- 最新正式锁镜像 `runtime-background-verification:20261009-final` 冷构建成功，摘要 `sha256:c6b2a38e07f606240afcd0708d41ad0a048e49c769716fed943dab8ce9d42e0d`；双包post43/SDK0.4.3使用 `uv.lock`，不再固定post20。两Linux controller共享挂载/daemon和清理：**1 passed，115.26秒**，暖启动ACK **0.91秒**，证据 `/tmp/background-shared-image-20261009-b`。单样本不能声称p95或生产SLO达标。
- 独立发布镜像API/Worker：前一镜像 `cb97b0...` **1 passed，298.13秒**，证据 `/tmp/runtime-background-e2e-20261009-linux-release-b`。最新镜像c6b2的C轮授权回调 `RemoteProtocolError` 导致502，**1 failed，295.37秒**；D轮Worker启动就绪超时，**1 error，507.32秒**，不能算通过。减少并发后的E轮 **1 passed，473.24秒**，证据 `/tmp/runtime-background-e2e-20261009-linux-release-e`，后台真实命令/有界日志/独立完成Run通过。两次失败的触发原因与资源压力相关，但未独立证明根因，不宣称生产高负载可靠性已验。
- B01仍缺按幂等key只读回查原生Run；正式包版本/镜像可运行不能替代这个契约。

#### T02 持久化、并发与迁移，2026-10-09

- `BACKGROUND_TEST_DSN=<本轮隔离 PG> uv run --frozen --project apps/runtime-service pytest apps/runtime-service/tests/background/test_repository.py -q -s --tb=short --basetemp=/tmp/background-pg-20261009-rollback-perf`：**8 passed，26.62 秒**，未 skip。
- 覆盖：同 call 重放/异摘要冲突、日志清理保留回执、两个 OS 进程限额、旧 fence 拒绝事实/日志、Stop 固定快照、inflight/迟到 Run 清理、分页完整 scope 标志、保留回执的 downgrade/upgrade。
- 1 万条历史回执：10 次列表查询 p50 **14.54 ms**、最大 **15.07 ms**；EXPLAIN 使用 `runtime_background_due`，未把本机数值宣称为生产 SLO。
- 使用测试新建 schema 并在 fixture 退出清理，不修改现役数据库或引擎表。

- 增补Thread/project/host容量与20提交组：**11 passed，92.91秒**，证据 `/tmp/background-pg-20261009-capacity-final`；1万历史p50 **14.48ms**、max **15.90ms**，属于本机观测值。create/start lost-control-ACK 增量 **2 passed，61.87秒**，证据 `/tmp/background-pg-20261009-control-increment-b`。先前合组12 passed/1 failed因测试只等三次而未等到清理，改为最多30秒轮询后这两个故障边界重跑通过，不隐藏失败轮。
- 事务原子性与fork隔离增量 **2 passed，109.79秒**，证据 `/tmp/background-terminal-atomicity-20261009-a`。`test_terminal_intent_and_resource_receipt_rollback_together` 在真实PG schema内给资源回执UPDATE挂故障trigger，证明终态/通知意图/资源状态一起回滚，解除故障后原task正常提交；`test_fork_and_checkpoint_namespace_do_not_adopt_old_task` 证明新Thread、origin Run或namespace产生独立task，同身份重放仍复用原task。退出时fixture清理整个隔离schema，不改现役或引擎表。

#### T03-T07 阶段组合证据，2026-10-09

- `tests/background`阶段组：**58 passed，62.88 秒**；真实 PG 边界和签名/DTO/权限/Stop/输出组合均执行。后续改动分别有下述增量/定向记录，不把58视为最终总数。
- 私有日志增量 `uv run --frozen --project apps/runtime-service pytest apps/runtime-service/tests/background/test_output.py -q --tb=short`：**6 passed，9.28 秒**。task UUID 目录、原子 fence 快照、UTF-8 上限、软链拒绝；每次写入/清理不扫描其他任务目录。
- `TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON=<本工作树 API Python> uv run --frozen --project apps/runtime-service pytest apps/runtime-service/tests/e2e/test_background_tasks.py::test_real_background_command_completion_cancel_and_repository -q -s --tb=short --basetemp=/tmp/runtime-background-e2e-20261009-h`：**1 passed，125.06 秒**；内嵌 PG/Stop 回归 **31 passed，26.55 秒**。隔离 PG/Redis、Platform、原生 API、独立 Worker、真实 Docker 命令，模型为受控 HTTP provider fixture。完成通知只创建一个 Run；output 查询与重复取消、no-store、最近关联 Run 均验证。
- `--basetemp=/tmp/runtime-background-e2e-20261009-lifecycle` 的 lost native ACK 用例 **passed**：Worker 暂停、原生已接受但回包丢失、不二次提交，Worker 恢复后 guard 回填原 Run。该轮另一生命周期用例因测试使用错误的metadata PATCH失败；改用 `/access-policy` 后 `/tmp/runtime-background-e2e-20261009-lifecycle-c` 的重启/HITL/源error/空闲Stop/期限/exit124 **1 passed，359.48秒**。
- Runtime 先前边界/真实 Docker runner **39 passed，179.28 秒**；foreground 重复取消修复与执行回归 **40 passed，250.09 秒**；Platform 新后台测试 **14 passed，1.84 秒**。后续总检只重复受新改动影响的项。
- Platform 扩展回归曾 **30 passed/30 failed**，29 项受既有 `project-1` fixture 与 UUID 模型治理冲突影响（代表失败在 HEAD 对照复现）；另 1 项 delegation 子进程超时。必须列为既有/环境问题，不能写全仓绿。

#### T03 执行资源和日志增量，2026-10-09

- Docker OOM/外部删除/伪 `state.json`、HTML完成文本、环境与管理socket隔离：`tests/workspace/test_background_execution.py::test_real_runner_trust_boundary_oom_and_external_removal` **3 passed，65.13秒**，证据 `/tmp/background-trust-boundary-20261009-a`。退出码与签名receipt区分CLI/命令事实。
- 4项目/host16个真实任务：`tests/background/test_repository.py::test_host_sixteen_real_tasks_and_no_model_cleanup` **1 passed，100.75秒**，`concurrent_tasks=16/rejected=4/cleanup_confirmed=16/model_calls=0`，证据 `/tmp/background-host-capacity-20261009-a`。
- 两任务UTF-8洪泛 C 轮 **1 passed，82.75秒**，证据 `/tmp/background-two-output-floods-20261009-c`。两份真实输出各超过10MiB，私有日志各<=1MiB、HTTP<=64KiB/Tool<=16KiB并保留尾部；清理confirmed。前两轮macOS首次并发创建 `.writer.lock` 遇到 `openat(O_CREAT|O_NOFOLLOW)` 的ENOENT；标准库复现同条件，先由lifespan等价初始化lock后100次并发open通过。测试补实际启动前置，未改生产日志代码；失败轮不计通过。
- 后台daemon控制连接失联/恢复：`test_daemon_connection_recovers_without_releasing_or_replaying_task` **passed**；与日志盘占用组同轮 **1 passed/1 failed，120.22秒**，证据 `/tmp/background-daemon-and-log-bytes-20261009-a`。使用不存在的测试socket断开该调用者，未关闭现役daemon；unknown窗口占位不释放，同call重放复用task，恢复后原容器仍running、真实counter只写一次，取消后confirmed。
- 10MiB输出的Docker实际日志盘占用 B 轮 **1 passed，65.98秒**，证据 `/tmp/background-daemon-and-log-bytes-20261009-b`；在隔离只读诊断容器内检查daemon的该容器local-logs目录，实际文件总量<=4MiB，正文<=1MiB/尾部完整。A轮失败来自测试假定local驱动公开inspect.LogPath，本机该字段为空；改用DockerRootDir定位并严格绑定容器ID，未改生产runner。

#### T04 生命周期与回退增量，2026-10-09

- 正式SDK修复后的 `tests/background/test_service.py` **21 passed，37.95秒**，使用真实SDK/MockTransport回放区分HITL、cancel_requested、rollback。原因：锁定0.4.3的 `get_client` 不接受 `http_client`；改用公开 `LangGraphClient(httpx.AsyncClient)`，保留超时与trust_env=False。
- 取消传播增量 `tests/background/test_service.py` **22 passed，96.07秒**，证据命令 `uv run --frozen --project apps/runtime-service pytest apps/runtime-service/tests/background/test_service.py -q --tb=short --basetemp=/tmp/background-service-cancel-20261009-a`。受控等待中取消工具启动，迟到container handle仍写取消意图，CancelledError原样传播；本组不是实际杀Worker，真实资源边界另由Docker/重启用例证明。
- `test_source_native_timeout_cancel_and_disabled_drain` D轮 **1 passed，505.30秒**，证据 `/tmp/runtime-background-e2e-20261009-drain-d`；真正原生timeout/cancel使任务cancelled/suppressed，flag0保留查询/取消/对账且禁止新通知。
- 最新E轮扩大旧源码回退：**1 failed，991.84秒**。关闭开关/清理已通过，旧源码启动失败原因为Alembic不认识新head `0003_background_tasks`。回退顺序已补：停止新API/Worker → 用新迁移代码downgrade应用版本至0002（表/回执保留） → 旧源码启动/普通Run实测。
- F轮两项合组 **1 passed/1 failed，2017.60秒**：`test_source_native_timeout_cancel_and_disabled_drain` **passed**，证据 `/tmp/runtime-background-e2e-20261009-closeout-f/test_source_native_timeout_can0/background-source-drain-evidence.json`；源原生timeout/cancel、flag0对账/查询/取消、drain无未结项、旧源码普通Run成功、保留3份任务回执均验证。用运行手册顺序真实启动旧应用，迁移往返单测不替代此证据。
- 同组 `test_completion_waits_for_hitl_and_new_tasks_survive_old_stop` **failed** 于等待pending通知超时；固定15秒完成与审批时序竞争。fixture已改为当前HITL确认后用Workspace文件释放命令，G轮单独复验；此时不把审批扩展和Stop后新任务记为通过。更早一轮后段复用tool_call_id，已改成prompt独立ID，保留失败原因。
- G轮用同步文件替代固定sleep后，测试误把容器`work`相对路径写成`work/文件名`，命令工作目录本身已是`/workspace/work`，导致等待文件不命中。主动中断该轮并清理隔离资源，exit130，不能记pass；路径修正后H轮接续。测试ready/spec内token不进入交接样本。
- H轮仍未通过，证据 `/tmp/runtime-background-e2e-20261009-approval-h/test_completion_waits_for_hitl0`。任务已succeeded/cleanup confirmed，但首个delivery审计耗时 **11596ms**，超过Runtime默认 **10秒** ACL超时；平台最终HTTP200不能证明Runtime收到回包。平台RunRequests只有三个用户/审批Run，没有 `background:<event_id>` 预留；Runtime保存unknown/inflight，`delivery_attempts=1`，随后reconcile-only均返回unknown。这是派发前检查的回包未知窗口，不能用“无预留”推断原请求已停止并自动重发，仍由B01只读接受语义承接。
- I轮 **1 error，316.93秒**，证据 `/tmp/runtime-background-e2e-20261009-approval-i`。失败在Runtime就绪等待；Runtime最后才记录production ready并在fixture收尾退出，没有业务异常栈。J轮开始前宿主load averages超过900，Docker backend约530% CPU；这些是环境观测，不是已证明的业务根因。仅此HITL验收使用 `PLATFORM_ACL_TIMEOUT_SECONDS=60` 和 `startup_timeout=360`（Runtime/Worker），不改生产超时/提交规则；J轮结果另列。I轮隔离PG已正常退出。
- J轮 **1 failed，749.31秒**，证据 `/tmp/runtime-background-e2e-20261009-approval-j`。已到达edited命令succeeded/confirmed、通知HITL pending、interrupt ID不变、显式reject恢复后唯一完成Run success及日志`EDITED`；随后Stop摘要 `target_count=2` 与测试假设1不符。源码 `request_stop()` 固定捕获活跃任务和accepted通知；已完成的通知Run也要只读确认终态，Task表不复制原生Run状态。此Thread已有一个accepted旧任务和一个running任务，2符合当前批准的保守清理语义。测试修正为两项confirmed、旧结果与完成Run关联保持、后续新任务不进入快照；K轮接续。J轮不计整条pass，fixture已关闭隔离PG/Redis/API/Worker。
- K轮单独复验 **1 passed，724.02秒**：`TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON=<本工作树API Python> uv run --frozen --project apps/runtime-service pytest apps/runtime-service/tests/e2e/test_background_tasks.py::test_completion_waits_for_hitl_and_new_tasks_survive_old_stop -q -s --tb=short --basetemp=/tmp/runtime-background-e2e-20261009-approval-k`。证据 `test_completion_waits_for_hitl0/background-approval-stop-evidence.json`。edit使用当前interrupt ID，命令真实输出`EDITED`；等待下一审批时任务succeeded/confirmed而通知pending，interrupt ID保持、完成模型调用0；显式reject恢复后只创建完成Run `9de93105-1d66-4cda-95d1-27ed95860734` 并success，最终completion-model总数1。Stop `924fc71f-a20e-41e9-ab95-ab58529d87b8` 的LLM target_count=0/phase no_active_run、后台target_count=2/confirmed=2/unconfirmed=0；之后新task `1eb50939-7bc0-4da6-825f-4f989bb895dc` 正常running，旧摘要不变，再单独取消confirmed。整条覆盖E04及E06追加场景；本轮隔离超时余量不证明生产高负载SLO，且不解除B01。

#### T06 两组合根与真实模型，2026-10-09

- `BACKGROUND_REAL_MODEL_TEST=1 ... pytest tests/e2e/test_background_tasks.py::test_managed_real_models_both_compositions_and_completion_usage` **1 passed，475.93秒**，证据 `/tmp/runtime-background-e2e-20261009-real-model-b/test_managed_real_models_both_0/background-real-model-evidence.json`。模型配置经隔离平台加密保存；不输出源env/token。
- DearFlow task `fce45aac-63a5-4396-a751-713a323d4b4d`、完成Run `a18c393a-52b3-47d9-b59c-1355fc1e258d`；Showcase task `3e8ec343-f842-4ff7-97a8-ef4b498e3260`、完成Run `923d66d0-0b53-472d-8405-45b2b9cad43d`。各源Run在90秒命令仍running时success；命令实际输出 `REAL_BACKGROUND_DONE`，最终succeeded/confirmed。各源Run采集2次模型调用，完成Run分别1次，费用不记回原Run。
- Runtime定向回归 **108 passed/1 skipped**；skip单列，不宣称它通过。此前foreground40项/普通graph与schema/审批/工具policy/准备及预算投影证据保留，非全仓Final。

#### T07 公开授权、精确委托与审计，2026-10-09

- Platform后台与完整delegation：**21 passed，63 subtests，166.21秒**，使用工作树API Python；Python3.14的既有Pydantic warning不作为失败或新依赖升级理由。
- `test_accepted_completion_revoked_model_is_rejected_before_model_and_acl_is_current` **1 passed，332.26秒**，证据 `/tmp/runtime-background-e2e-20261009-revoke-a`：接受queued完成Run后撤模型权限，guard在模型前拒绝、模型调用0；共享read可读但cancel拒绝，跨project拒绝，撤销share后读拒绝。
- 后台与旧Run/Stop/原SDK等扩展回归 **92 passed/1 failed**；`project-1`非UUID fixture失败已在HEAD对照复现，为既有基线问题。它不阻塞本专项隔离正向证据，但不允许宣称该回归全绿。
- 完成身份/模型接续增量 `uv run --frozen --with pytest --project apps/platform-api python -m pytest apps/platform-api/tests/test_background_tasks.py apps/platform-api/tests/test_model_connection_lifecycle.py -k 'completion or background or revoke or disabled or disable or membership' -q --tb=short --basetemp=/tmp/platform-background-identity-20261009-a`：**30 passed，5 deselected，36.76秒**。真实隔离SQLite的用户停用/删除、服务账号停用/删除、credential撤销/到期/revoked_at/替换经`current_actor`拒绝；复用模型参考redeem验证当前模型/Agent/成员资格拒绝。此组不是完整跨服务服务账号E2E，未重复运行不相关5项；pytest用隔离临时依赖，不改锁文件。

#### T08 质量门禁和资源收口，2026-10-09

- 55个改动Python文件 `uvx --from ruff==0.13.2 ruff check` 与 `ruff format --check` 通过。后续只追加验证fixture/测试和文档，受影响文件再次增量检查。
- 部署overlay默认 `${RUNTIME_BACKGROUND_TASKS_ENABLED:-0}`；关闭时继续保留host/daemon/共享私有日志供drain。Compose隔离config校验通过，未修改现役env或运行生产迁移。
- 前端v1接口、capability、Stop摘要、错误样例与F01-F12交接已同步；Runtime接入与运行手册已交付，JWT/SSE整体保留draft。
- 最新发布镜像、旧源码回退、追加HITL/新任务固定Stop/双日志洪泛复验及最后资源盘点已记录到本节，不能记入Final。
- 收口复查：**55个变更Python文件** Ruff check/format均通过；经验入库后 **27个变更Markdown文件** 按 `scripts/check_docs.py::check_file()` 检查 `changed_errors=0`；`git diff --check` 通过。专项11份文档的23个本地链接、4个JSON示例、围栏/空白/冲突标记检查通过；冻结44项与覆盖矩阵44项逐一一致，无缺项或重复。本轮只有可选E2E fixture与文档增量，没有生产源码增量，未重复既有真实模型/镜像/PG/Docker重型用例；本次门禁仍为Phase。
- 资源盘点：带 `runtime.background.verification` 或 `runtime.background.host` 标签的容器均为0；K轮PG/Redis/API/Worker经fixture正常退出，H轮53751和旧B/C轮60736/51499隔离PG已按数据目录fast shutdown；无本专项验证进程遗留。只剩现役 `llmops-db`、`llmops-weaviate`、`llmops-redis`，未停止其他worktree服务，未prune镜像/volume，证据目录保留。
- 经验提案经用户明确确认后，四条回调/迁移回退/Docker日志/执行目录经验写入 `docs/lessons/runtime-service.md`，索引8条；项目仍blocked，JWT/SSE整体不毕业为active。

#### T05 尚未闭环的引擎依赖

- post43 没有按幂等 key 只读回查 Run 的接口。Platform 持久 RunRequests 无 run_id 且 Worker 尚未执行 guard 时，`reconcile_only` 返回 `unknown`，禁止改 key 或再次 POST。撤权/Stop 后仍可能有未确认派发，必须保留 inflight 与清理未确认摘要。
- 正常 ACK、Worker 开始后 guard 回填、以及平台回包丢失后本地已有回执均可恢复；不能将这些证据扩大为“所有 ACK 丢失窗口都闭环”。待交付具体引擎契约与复验步骤。
- 所属任务T01/T05/T08均为blocked；具体原子接受/只读key查询、回执保留和撤权固定清理的协议/发行产物/接线点见 [engine-handoff.md](engine-handoff.md)。当前平台继续按unknown处理，默认关闭新提交。

### Phase 证据覆盖矩阵

本表保留接受回执正式交付前的44项 Phase 覆盖快照，不能替代后端Final。表中 B01 阻塞描述为该阶段事实；后续正式解除与新增联合证据见“接受回执专项正式交付”。其余完整矩阵及F12仍未完成，不把skip/基线失败计pass。

| 验收 ID | 当前证据与边界 | 状态 |
|---|---|---|
| U01 | service非法输入零副作用、tools身份/deny/probe/maintenance、生命周期HITL拒绝零任务 | 阶段覆盖 |
| U02 | PG同key/异摘要、日志删除后回执、Thread/Run/checkpoint namespace隔离 | 阶段覆盖 |
| U03 | PG两OS进程20提交、Thread4/project8/host16、unknown/取消未确认占位 | 阶段覆盖 |
| U04 | 共享docker_workspace_args、真实runner/受保护Workspace；foreground40项回归 | 阶段覆盖 |
| U05 | 签名runner回执+真实Docker exit124/期限/OOM/外部删除/伪state与文本 | 阶段覆盖 |
| U06 | 私有软链/原子UTF-8、两份>10MiB输出、HTTP/Tool上限与实际Docker盘占用 | 阶段覆盖 |
| U07 | CancelledError传播、迟到container写取消意图、foreground重复取消等待 | 阶段覆盖 |
| U08 | 真实PG旧fence拒绝facts/log/delivery；事务等待与续租相关测试 | 阶段覆盖 |
| U09 | PG故障trigger证明终态/outbox/资源回执一起回滚；固定event/key及guard回填；全lost-ACK回查缺失 | blocked：B01 |
| U10 | PG固定Stop/晚到Run、新Thread隔离；空闲Stop真实清理；K轮旧Stop后新任务running且旧摘要保持 | 阶段覆盖 |
| U11 | 伪marker/cron/context/身份/Stop/撤权在factory前拒绝；真实queued完成Run撤模型后零模型调用 | 阶段覆盖 |
| U12 | Runtime/Platform DTO、cursor、三operation、no-store、私有输入拒绝/投影；完整delegation21项/63subtests | 阶段覆盖 |
| I01 | 两组合根真实模型90秒命令未完成时源Run已success，之后查询真实日志/exit/关联 | 阶段覆盖 |
| I02 | PG20提交及真实host16容器；同call重放、容量拒绝与副作用计数 | 阶段覆盖 |
| I03 | 真实create/start ACK丢失同task恢复、控制连接中断、取消晚到handle；没有逐一杀Worker覆盖每个指令边界 | 部分阶段证据，完整矩阵随T08接续 |
| I04 | PG租约/旧fence、两个Linux controller共享daemon/目录、API/Worker独立重启 | 阶段覆盖 |
| I05 | 进程重启、仅调用者daemon连接失联恢复、OOM/外部删除；没有重启宿主机或现役Docker daemon | 部分阶段证据，隔离故障覆盖 |
| I06 | 终态事务回滚、正常ACK、原生ACK丢失后guard回填；Worker未进入guard的只读回查不足 | blocked：B01 |
| I07 | 原生enqueue固定Stop门禁、审批显式拒绝/批准；K轮HITL保持与显式恢复后唯一完成Run通过 | 阶段覆盖；完整提交竞态随T08接续 |
| I08 | PGinflight/迟到Run固定Stop、开始前tombstone与受限清理；无run_id未知派发仍不可确认 | blocked：B01 |
| I09 | 当前用户/服务账号credential撤销/到期等隔离SQLite契约、真实模型/共享read/cancel/cross-project/撤权；非完整服务账号E2E | 部分阶段证据，真实授权契约已覆盖 |
| I10 | HMAC用途/时间/正文/Unicode、scope互换与503安全错误；失响应保持unknown不重发 | 阶段覆盖；恢复全窗口由B01承接 |
| E01 | Showcase真实受管模型、真实Docker90秒命令、独立完成Run/Usage | 阶段覆盖 |
| E02 | DearFlow真实受管模型与同一公共工具链、受保护Workspace | 阶段覆盖 |
| E03 | 独立原生API/Worker完成新Run、实际日志；两模型完成用量计入新Run，原Run不变 | 阶段覆盖 |
| E04 | 空闲Stop、K轮同Thread两项固定清理、旧Stop后新任务running/旧摘要不变 | 阶段覆盖 |
| E05 | source error/原生timeout/cancel与正常success区别，任务清理/通知suppressed | 阶段覆盖 |
| E06 | review显式reject/approve生命周期与K轮edit/HITL保持/显式reject恢复/唯一完成Run均通过；workspace_write真实链路，full_access为组合策略契约 | 阶段覆盖；非全策略实际E2E |
| E07 | 源Run已结束时Stop target_count>0/confirmed，phase no_active_run不代表无后台任务 | 阶段覆盖 |
| E08 | queued完成Run撤模型权限后guard拒绝/零模型；用户与服务账号当前授权隔离契约；未知派发恢复待引擎 | 部分阶段证据；B01阻塞全窗口 |
| E09 | PGfork/namespace重放与回执、probe/维护/完成Run零启动、graph/schema/foreground/Stop/inbox/Usage定向回归；未对所有教学图做实际time-travel E2E | 部分阶段证据，完整回归随T08接续 |
| E10 | F01-F11完成并经Playwright+Chromium真实链路闭环验收(含百炼模型调用、任务流转/取消、ANSI纯文本日志与三档截图)；F12待B01解除 | 前端阶段覆盖完成；F12待B01解除 |
| L01 | 两Linux controller暖启动ACK0.91秒；只有单样本，未声称p95或生产SLO达标 | 实测记录；正式SLO未冻结 |
| L02 | 两份UTF-8洪泛各>10MiB、private<=1MiB/HTTP<=64KiB/Tool<=16KiB；Docker实际日志<=4MiB | 阶段覆盖 |
| L03 | 真实16容器、4项目、4项额度拒绝、16项confirmed、轮询模型0；最终资源盘点另列 | 阶段覆盖；非宿主压力SLO |
| L04 | 1万真实PG回执、索引EXPLAIN/列表p50/max，私有容量/TTL与启动满额仍可对账 | 阶段覆盖；本机观测非生产SLO |
| S01 | 五维scope/operation、当前ACL/cursor、固定回执清理隔离、管理socket不进入命令容器 | 阶段覆盖 |
| S02 | 真实伪state/HTML输出与签名回执，软链/私有日志隔离、guard伪marker拒绝 | 阶段覆盖 |
| S03 | 真实命令env/socket隔离、安全DTO/审计/错误投影；浏览器纯文本渲染与ANSI清洗、HTML转义完备 | 全阶段覆盖（后端+前端） |
| S04 | queued撤模型/共享只读/撤权、固定Stop清理委托；K轮HITL保持通过，未知派发清理缺只读回执 | blocked：B01 |
| S05 | 公开input/config/context/metadata拒绝私有marker，HTTP/history/SSE递归投影定向回归 | 阶段覆盖 |
| R01 | 正式post43双包锁/最终镜像冷构建、LinuxAPI/Worker；PG迁移往返/旧源码普通Run | 阶段覆盖；引擎新契约仍缺 |
| R02 | flag0查询/取消/对账、真实drain、先新迁移downgrade0002再启动旧源码；unknown drain无法全确认 | 部分阶段通过；B01阻塞未知窗口 |
| R03 | PG日志清理保留重放回执、私有TTL/容量/软链、运行手册unknown/drain；不盲删未知资源 | 阶段覆盖；unknown处置依赖B01 |

当前可读状态仍是T02/T03/T04/T06/T07/T09阶段done、T01/T05/T08 blocked。矩阵中的完整故障/竞态和Final回归随引擎正式契约交付后执行；在此之前没有后端Final结论，也不启用现役。

### Phase 前端实施与自动化 E2E 验证（2026-10-10）

前端代码于 Worktree（`wt_27df0f537b6d`）实施完成，严格遵循 `apps/platform-web/docs/` 规范及老王工业级架构标准，达成零外部冗余依赖：

1. **工程质量门禁全绿：**
   - **Vitest 单元测试：** `pnpm --dir apps/platform-web test:run`，全仓 131 个测试套件、710 个测试用例 100% 通过（0 失败）。新增专项单测覆盖领域模型校验、HTTP 契约映射、状态机及组件渲染。
   - **TypeScript 类型检查：** `vue-tsc --noEmit` 退出码 0，全量类型完全契合前后端 DTO 契约。
   - **ESLint 代码检查：** 退出码 0，新代码 0 错误 0 告警。
   - **生产构建打包：** `pnpm --dir apps/platform-web build` 构建顺利生成静态产物（0 错误）。

2. **Playwright + Chromium 自动化端到端闭环验证（4/4 Passed）：**
   - **执行命令：** `pnpm --dir apps/platform-web exec playwright test e2e/background-tasks.spec.ts --workers=1`
   - **执行耗时：** 19.9s
   - **用例 01（真实百炼大模型调用 +「任务」Tab 空状态）：** ✅ PASSED (3.2s)。真实大模型 `qwen-plus` 正常回复，工作区任务面板展开，空状态展示正常。
   - **用例 02（任务列表流转 + 按需日志 ANSI 清洗与截断 + 单任务取消确认）：** ✅ PASSED (3.8s)。状态正交 Badge（运行中/资源回收中/已完成/已送达通知）渲染正常；ANSI 控制符清洗干净并以 `<pre>` 呈现；超长截断容量告警栏正常展示；取消弹窗与副作用警示正常，提交取消后状态正确流转至 `cancel_requested`。
   - **用例 03（LLM 空闲时 Stop 控制台可用与后台停止报告解析）：** ✅ PASSED (5.6s)。LLM 空闲但后台任务存活时，底栏「停止生成」按钮保持可用可达。
   - **用例 04（三档分辨率视觉验收与截图留痕）：** ✅ PASSED (5.3s)。
     - 桌面端（1440×900）：`docs/projects/20261009-agent-generic-production-capabilities/screenshots/1440x900-desktop-tasks.png`
     - 平板端（768×1024）：`docs/projects/20261009-agent-generic-production-capabilities/screenshots/768x1024-tablet-tasks.png`
     - 移动端（390×844）：`docs/projects/20261009-agent-generic-production-capabilities/screenshots/390x844-mobile-tasks.png`

### Phase A/B 非 Docker 兼容独立验收，2026-10-10

此阶段只验 AB01-AB03 的非前端范围与交接，采用用户已批准的 A 主方案+B 精确兜底；不替代 B01、T08 或 T10 Final。在指定99f7 Worktree使用各app独立 `.venv`/`node_modules`，专属环境 `wt_27df0f537b6d`。该阶段前端只交接，后续ABF验证另列；外部模型额度共享，现役未部署、未提交Git。A/B本身未改引擎依赖；当时安装post45、服务锁/部署post43的差异已由下文正式接受回执交付消除。

#### AB01 能力与工具门禁

- `apps/runtime-service` 下 `.venv/bin/python -m pytest tests/background/test_compatibility.py -q --tb=line`：**18 passed，360.84 秒**。两真实组合根 × 六配置验证模型工具可见性、B 后继续、同码非专门异常 Fatal、旧 checkpoint 中断/重建/恢复。模型为 RecordingModel，checkpoint 为 InMemorySaver；synthetic DSN 不访问数据库，消息队列 before_model 用 AsyncMock 隔离无关 inbox。这组不冒充真实 shell 或持久引擎 E2E。
- `.venv/bin/python -m pytest tests/background/test_tools_and_assembly.py tests/background/test_service.py tests/middlewares/test_runtime_middleware.py tests/services/showcase_demo/test_agent.py::test_probe_has_no_io_and_cannot_be_invoked tests/services/dearflow_agent/test_agent.py::test_schema_probe_has_no_model_or_workspace_io -q --tb=line`：**73 passed，136.10 秒**。公共能力/工具路由矩阵、probe 零 IO、权限/maintenance/completion 拒绝、现有中间件与取消保持原语义。
- Platform：`.venv/bin/python -m unittest discover -s tests -p test_background_capabilities.py -v`，**2 passed，2.962 秒**；Runtime 新启动 false、execute/background_execute deny、只读 ACL 均保留查询。
- Web：`pnpm exec vitest run src/modules/chat/composables/useBackgroundTasks.spec.ts src/components/workspace/BackgroundTasksPanel.spec.ts src/services/threads/background-tasks.service.spec.ts`，**3 files / 11 tests passed，41.19 秒**。前端原有 capability 消费按查询显示任务入口，无需复制业务逻辑。

并行安装正式 post45 后复验当前代码：Runtime `.venv/bin/python -m pytest tests/background/test_compatibility.py tests/background/test_tools_and_assembly.py tests/background/test_service.py tests/middlewares/test_runtime_middleware.py tests/services/showcase_demo/test_agent.py::test_probe_has_no_io_and_cannot_be_invoked tests/services/dearflow_agent/test_agent.py::test_schema_probe_has_no_model_or_workspace_io -q --tb=line`，**91 passed，17 warnings，39.84 秒**；Platform 同能力 unittest **2 passed，0.847 秒**。这91项是上述18+73的当前版本合并复验，不重复累计为新用例。

#### AB02 原回执与精确兜底

- 从 `.local-stack/runtime.env` 私有读取 DSN，连接断言 `current_database()` 等于本环境 runtime 数据库，然后仅在子 pytest 进程设置 `BACKGROUND_TEST_DSN`。命令：`.venv/bin/python -m pytest tests/background/test_repository.py -k 'start_replay or disabled_start_after_source_stop or two_processes_cannot or replay_cancel or fence_rejects or fork_and_checkpoint or stop_snapshot' -q --tb=line`，**12 passed，14 deselected，831.72 秒**。每 case 随机 schema，fixture 退出清理；没有加载主库或输出 DSN。
- 覆盖 running/unknown/succeeded × local/docker、flag0/缺当前 host 的原回执；同 key 改 command/timeout/Workspace/skills/protected 冲突；原日志清理不丢去重；无记录后源 Stop 不能恢复；两进程容量、旧 fence、fork/checkpoint 与固定 Stop。Docker 专项用例未开启，deselected 不算通过。
- 初次完全移除启动 ToolNode 的实现使两图重建 checkpoint 测试失败（返回未知工具）；修为保留内部回执入口、只过滤模型可见工具后上述 18 项通过。不会将 unknown 误导为前台重跑。

#### AB03 真实 local 后端链路、前端交接与质量

非前端验收改用专属 API 脚本 `.local-stack/ab-local-api-check.py`：私有读取本环境配置，先断言环境根路径/ID、本环境 Runtime 数据库和 local backend；通过 Platform API 正常登录、创建临时项目、授权图/已配置模型、绑定 Agent、创建 Thread，再提交 Protocol v2 `run.start`。读取真实当前 interrupt ID 并显式提交 `input.respond`，不绕 ACL/HITL、不 stub 模型/Worker/shell。使用已授权 `deepseek-v4-flash`，两个图均一次审批后真实 execute 成功并最终 `success`：

| 图 | Thread | 原 Run → 恢复 Run | 结果 |
|---|---|---|---|
| Showcase | `643547f5-a7ab-4504-8f3e-106ff16b1c5e` | `dc1b2013-6ce5-4329-a443-fb31d2230ab9` → `cd34e163-04e9-45de-ab66-14f53220e662` | `AB_LOCAL_OK`，退出码0，success |
| DearFlow | `3b73a085-1d0a-4aed-9726-311bcc919609` | `b8b147b1-f9d5-41cf-bd0a-081f6683fb9b` → `835485d6-1127-4aaf-b636-1e64745a3f93` | `AB_LOCAL_OK`，退出码0，success |

两图 capabilities 均 query=true/start=false；state 中均只有普通 execute ToolMessage、无 background_execute；真实任务列表均为空。平台测试项目 `6858924f-e993-4210-9f52-54249746be8a` / `1ac9604c-1143-4be9-a639-8ba6663e8216` 在 finally 通过平台接口软删除。脱敏持久摘要见 [API 证据](implementation/ab-local-api-evidence.json)，完整方法/路径/状态保留在本 Worktree `.local-stack/ab-local-api-evidence.json`，不含 token/凭据。

此前新增浏览器测试使用本环境三服务/Worker/已授权模型，无 `page.route` stub；但未通过，现作为 `apps/platform-web/e2e/background-compatibility.draft.ts` 交接，不进入默认 Playwright 收集。诊断只记录方法、路径与 HTTP 状态，不附带 token、请求正文或模型凭据。产品前端源码未改；ABF01-ABF03 的增量开发和浏览器验收见 [前端交接](local-compatibility-frontend-handoff.md)。

已执行的失败轮如实保留：普通 commands HTTP500 来自并行接入 ORM 新增字段与测试库旧 schema 不一致；通过 `scripts/local-stack.sh migrate` 将本环境 Platform 升到 `20261010_0007`，未改主库。随后有 PG 短时不响应、API/Worker 超过启动等待上限但稍后 ready，以及 Platform API 多次热重载。浏览器分别在创建项目400、权限同步暂不可用/未发 commands、Agent 列表加载及等待 commands 时失败，不能算成功链路。新会话后来等待实际授权模型名后能提交；最近浏览器 **1 failed，约1.4分钟**，五轮审批后未达终态。

最近浏览器 Thread `5ce3e8f6-fd80-44eb-a12c-ea412c15497f` 的6个 Run 最终均 `interrupted`，不是重复点击同一 interrupt：PG checkpoint_writes 已有普通 execute 输出 `AB_LOCAL_OK`/退出码0，模型又要求同命令。脱离浏览器使用 `qwen-plus` 的真实 API 复验（Thread `6ab38717-da0f-4aac-8bc8-4a39d6acf815`）同样在3次成功 execute 后又等待审批，主动停止继续批准。保存消息的工具调用 `id=""`、工具结果 `tool_call_id=""`；既有 sanitizer 的实际重放将3份工具输出清洗为0份。`_normalize_ai_message_tool_calls` / `sanitize_tool_call_messages` / `repair_model_tool_calls` 与 HEAD 的 AST 比较相同，本轮没有改这些函数，已定位现有清洗与空 ID 的兼容缺口；没有执行完整旧源码的同模型链路，不扩大为全链路旧版本基线结论。不能归因为前端审批错误、增加审批次数掩盖，或声称该 qwen 模型链路成功。改用已配置 deepseek 后两条后端链路通过；前端接续时显式选同一已验模型，qwen 兼容修复另交 Runtime 模型适配。

- A/B 修改的 Python 文件 Ruff check/format check 通过；新 E2E Prettier check 通过；`git diff --check` 通过。
- 收尾复验：`uv tool run ruff check/format --check --config apps/runtime-service/pyproject.toml` 检查15个A/B Python文件，全部通过；draft与脱敏API JSON的Prettier通过。专项48个本地文档链接及7个新增锚点通过，API证据结构与两条实际成功结果一致。全仓FEATURES检查另发现4个HEAD已存在的无效链接，本轮未修改相关行，不声称全仓文档无误。
- 较宽 Runtime 回归：**186 passed，1 skipped，3 failed**；扩展工具/Dear 回归 **49 passed，2 failed**。两图 schema probe 夹具指向已移除 `fetch_model_connection`，本轮修为当前 `fetch_model_bundle`，必要 probe 已包含上面的 73 passed。`test_real_parallel_repeated_cancel_reaps_only_owned_resources` 单独重跑通过；主/子图 wrapup 断言单独仍失败，并在内存替换为 HEAD 的 `RuntimeConfigMiddleware.awrap_model_call` 后复现 **1 failed**，未改写预算业务。Dear auxiliary SDK budget 测试同旧夹具问题属于范围外未修。较宽回归不声称全绿，Pydantic/context 与 LangChain beta 等既有 warnings 未消除。

#### ABF01-ABF03 前端增量消费与浏览器验收（2026-10-10）

前端增量由本轮完全实施并通过所有单元测试与 Playwright 浏览器验收，达成零外部冗余依赖：

1. **ABF01 能力门禁与响应式状态机：**
   - 在 `apps/platform-web/src/modules/chat/composables/useBackgroundTasks.ts` 接入 `capabilities` 选项，基于 `queryEnabled = computed(() => Boolean(toValue(options.capabilities)?.background_tasks))` 实现硬门禁。
   - 门禁关闭或缺省时：彻底禁请求、停止定时探针、abort 在途探针及日志请求、重置作用域数据，不残留上一会话数据。
   - 门禁开启但启动关闭时（Local）：保留任务 Tab，支持历史任务查询、有界日志阅读与基于 `allowed_actions` 的授权取消。
   - 动态切换与生命周期：能力由 false 变为 true 自动恢复按需加载；能力由 true 变为 false 立即清空作用域；组件卸载（scope dispose）安全中止在途请求并清理定时器；watch 参数安全解构避免 TypeError。
   - 在 `ChatSession.vue` 顶层拉取当前线程 capabilities（带 AbortController 保护）并注入 `useBackgroundTasks`。
   - 单元测试：`useBackgroundTasks.spec.ts` 7 个专项测试 100% 通过（144ms），覆盖 true/false、true/true、false/false、字段缺省、动态变化、切会话、scope dispose。

2. **ABF02 局部恢复提示与安全映射：**
   - 在 `apps/platform-web/src/modules/chat/transcript.ts` 的 `RECOVERY_HINT_MAP` 中补齐 `use_execute_for_short_task: "短任务可改用前台执行，最长60秒"`。
   - 单元测试：`transcript.test.ts` 补充针对 `BackgroundTaskNotStarted` 结构化 JSON 的解析及局部恢复提示断言，18 项单测全部通过（412ms）。

3. **ABF03 真实 Local 浏览器端到端闭环验证：**
   - 升级交接草稿为正式 Playwright 规范 `apps/platform-web/e2e/background-compatibility.spec.ts`。
   - 显式绑定已验证的 `deepseek-v4-flash` 模型，避免 `qwen-plus` 工具调用空 ID 引起重复执行的已知 Runtime 适配问题。
   - 真实前台执行命令 `printf AB_LOCAL_OK`，经真实 HITL 人工审批通过，普通前台 `execute` 真实执行并成功返回 `AB_LOCAL_OK`，Run 终态为 `success`。
   - 验证 ToolMessage 仅包含 `execute`，无 `background_execute`；验证工作区「任务」Tab 正确保留且呈现空态（empty state），后台任务列表为 `[]`，零 pageerror。
   - 执行结果：`pnpm test:e2e e2e/background-compatibility.spec.ts`，**1 passed（58.4s，退出码 0）**。

4. **前端工程质量门禁全绿：**
   - `pnpm lint`：0 错误通过；
   - `pnpm typecheck`（`vue-tsc --noEmit`）：0 错误通过；
   - `pnpm check`（lint + typecheck + build）：全绿通过。

#### 边界与资源

本轮未实现 C、未测试受限生产 Pod/Serverless 或滚动切换 backend；普通 local shell 的可信部署边界不改变。新启动关闭后的对账仍需原 Docker/host/共享挂载，local 节点不能替代它。原 B01 接受回执及其并行平台接线验收由引擎专项收口，不能写入 A/B 完成项。

测试新增 PG schema 已由 fixture 清理，收尾只读查询 `background_test_%` schema 数量为0。浏览器及 API fixture 通过平台接口对本轮项目执行 soft-delete；qwen API 临时项目同样已软删除，不删除其他会话历史或他人数据。Playwright 测试生成的截图和脱敏 API 响应日志保留在测试输出目录。`scripts/local-stack.sh status` 验证服务运行正常。

**A/B范围结论：** AB01-AB03与ABF01-ABF03全部为 `done`；前端增量与真实 Local 浏览器链路已获用户人工真机验收通过（2026-10-11，验证能力门禁、任务 Tab 保留、短任务 execute 审批流执行成功）；该阶段未承担原专项接受回执门禁或全范围Final。随后B01由正式接受回执专项解除，原专项当前 `partial`，T01/T05/T08剩余门禁与T10/F12未收口。qwen空工具ID与较宽预算回归失败保留为范围外限制，不宣称全量或所有模型通过。

### 接受回执专项正式交付（2026-10-10）

[B01](engine-handoff.md) 已解除。GraphHarbor 正式双包 `0.13.0.post45` 已接入本 Worktree 服务锁与 Dockerfile 断言，平台迁移 head 为 `20261010_0007`。引擎源码/发行包、固定只读回查、迁移/并发/故障矩阵及使用方接线 Final 的独立记录见 GraphHarbor 仓库 `docs/projects/20261010-run-acceptance-receipts/verification.md`，入口保留在 engine-handoff.md。

本 Worktree 正式 PyPI 依赖的 `test_lost_native_ack_reconciles_queued_run_without_resubmission` 在各自 disposable PG/Redis 执行：notify **1 passed/249.96s**、stop **1 passed/322.48s**、revoke **1 passed/339.07s**。每场景 2 Run（源+完成）、1 ledger，完成模型调用 1/0/0；ACK 丢失且 Worker 暂停时固定 GET 找回原 Run，Stop 仍 suppressed 并精确清理，撤权公开查询/新执行 403、内部 GET 可读、execution guard 拒绝模型。

脱敏 JSON/JUnit、四产物哈希及安装/锁来源随引擎专项保留；本范围还包括 Platform **132 passed/1 skipped/116 subtests**、Runtime **115 passed**、真实 PG repository **21 passed/5 skipped**、平台 PG 迁移 **1 passed**。skip 未算通过，其他专项既有范围外失败仍保留。B01 完成只解除引擎门禁；T01/T05/T08 未勾选、T10/F12 未验；ABF 前端独立验收保留，新 Linux 应用镜像与现役启用未执行。

### Final 后端验证

尚未执行。T08全部后端门禁通过才填写，范围明确排除同事未完成的前端。

### Final 全栈验证

尚未执行。T10覆盖全部批准范围后按verify-change给出done/partial/blocked/deferred；本轮规划完成不能把功能标done。
