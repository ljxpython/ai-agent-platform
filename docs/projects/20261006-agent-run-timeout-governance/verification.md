# Agent 运行生命周期超时治理 - 验证计划与记录

> 当前partial，仅剩前端T11/F01-F10与联合Final；正式post42发布/锁定、12组平台HTTP、新PID接管及R01-R04匹配回退完成。10-06跨attempt总截止点与恢复前404/高负载轮次保留为历史，现行结果见第7节“正式PyPI接入”Phase。

## 1. 验证环境与证据要求

确定性测试使用现有pytest/fake model、显式预算和可控制时钟；不等待45分钟验证边界。真实链路使用隔离Platform API、GraphHarbor API/Worker、PG、Redis、工作区和独立端口，API/Worker双包同版。本轮恢复后使用PyPI正式post42冻结冷环境，旧本地候选wheel只保留历史。没有对现役实例执行restart/kill/drain。

10-07 HTTP 隔离参数 H=30 秒、G=10 秒，模型 scope 场景 M=0.03 秒，仅执行一次 Worker；真实重启场景旧 attempt H=30 秒/G=10 秒，新 Worker H=20 秒/G=5 秒，并等待旧 deadline 过去后接管。另测 G=0；GraphHarbor 独立硬限测试 H=2 秒，恢复/状态测试采用受控旧 deadline，避免依赖本机秒级初始化时序。HTTP 查询等待上限不延长执行预算。

实际隔离资源：GraphHarbor定向库 `agent_run_budget_20261006_e7dd` / Redis `graphharbor:budget:official:e7dd`；HTTP库 `agent_run_budget_e2e_20261006_e7dd` / `graphharbor:run-budget-e2e:e7dd`。正式冷环境 `/tmp/run-budget-pypi-post42-venv`，原包环境 `/tmp/run-budget-post41-venv`；匹配回退在独立PG实例的 `graphharbor_event_retention_verify` / Redis `graphharbor:run-release:e7dd` 上执行。平台DB与工作区使用临时目录。先前官方候选产物/冷环境见历史Phase，不与发布包混用；不加载部署业务变量、不打印凭据、不操作现役数据。

正式冷环境Python3.13.9，`graphharbor=graphharbor-runtime=0.13.0.post42`、LangGraph1.2.11、LangChain1.3.17、DeepAgents0.7.8、SDK0.4.3、core1.6.0、SQLAlchemy2.0.52。Runtime的pyproject/uv.lock及自身venv已post42，141项依赖check通过；独立冻结环境142项通过，清单见evidence。API自身锁文件保持SDK0.4.2/Python3.14.6，独立85项unittest验证此组合；HTTP/全量API记录使用冻结SDK0.4.3，不能混称同一环境。

每个真实场景保留版本、H/G/M、run_id、thread_id、request_id、当前 attempt 开始/截止时间、领取 owner、最终 Run GET、durable lifecycle、模型/工具调用计数、checkpoint 和资源清理证据。日志不记录 token/连接凭据/私有进程时钟。

缺少凭据、正式包或隔离环境时，如实记未执行/阻塞，不使用 pytest skipped 数量证明通过。模型服从收尾提示需要真实模型效果观察；确定性测试能证明提示实际送达，不能证明任意模型总会按要求总结。

## 2. 单元与组合验证

下表保留验收目标；Runtime 预算/收尾测试及 API 私有契约测试已落地。真实证据与未覆盖部分见第7节；Web部分交同事执行。

| 编号 | 场景与判据 | 拟落位置 |
| --- | --- | --- |
| U01 | 每次 claim 在原事务生成一个 attempt 预算；并发 Worker 不重复领取；事务回滚不留下半份预算 | GraphHarbor 原仓 run_store 单测/真实 PG 组合测试 |
| U02 | retry/reaper/shutdown 下一 claim 获新 H/deadline；旧 deadline 已过仍可继续；正常 drain 归还故障 attempt，租约 generation 不回退 | GraphHarbor Worker 与 repository 测试 |
| U03 | UTC 只在持久边界使用；接管转换为新进程 monotonic；进程内 wall-clock 跳变不影响预算 | GraphHarbor 时钟测试、新增 `apps/runtime-service/tests/runtime/test_run_budget.py` |
| U04 | 未知版本、bool、NaN/Infinity、非法时间、错配身份、G>=H 被拒绝；正式执行缺预算不静默重置 | 新增 `tests/runtime/test_run_budget.py` |
| U05 | soft deadline 前不注入，恰好边界/之后注入；G=0 关闭；连续请求每次有提示但同请求不重复 | 新增 `tests/middlewares/test_timeout_wrapup.py` |
| U06 | 无 system、字符串、结构化 content blocks；保留 cache_control/多模态块；原请求和原 message 不修改 | 同上 |
| U07 | 本 scope 超时产生 ModelCallTimeoutError；provider TimeoutError 不改写；外部 CancelledError 不吞 | `tests/middlewares/test_timeout_wrapup.py`；复用 `test_runtime_middleware.py` 基线 |
| U08 | 真正执行 middleware 嵌套，retry/fallback 的后续调用重新判断 deadline；授权裁剪先于收尾 | `tests/services/reference_agent/test_middleware_order.py` 及图组合测试 |
| U09 | 四正式图覆盖；主/并行子 Agent 同一预算；workflow 重建不重置；并行 Run 不互串 | `tests/services/{dearflow_agent,showcase_demo,reference_agent,workflow_demo}/` |
| U10 | schema/probe 构图不计时、不兑换连接；下一 Run 不继承 checkpoint 时钟；private 值不在 state/history/trace | Runtime 图与 budget 测试，GraphHarbor 序列化测试 |
| U11 | H/G 环境预检、0 关闭、模板映射、官方变量/旧别名、非法配置；在途 attempt H 不变，下一 claim 使用新配置 | `tests/runtime/test_runtime_config_validation.py`、GraphHarbor 配置/接管测试 |
| U12 | 标准/Protocol/resume/Assistant/Thread/cron 私有字段注入无效；公开输出隐藏 kwargs/config 私有数据 | API `test_runtime_gateway_runtime_contract.py`、`test_runtime_gateway_event_redaction.py` 和 GraphHarbor入口测试 |
| U13 | timeout 仍是 timeout；SDK completed 标签不覆盖 status；模型 error、取消与审批可区分 | API/Runtime lifecycle 测试和同事 Web 定向用例 |
| U14 | 相同幂等请求/恢复连接只创建一个 Run；追加消息不能延长已运行预算 | API `test_run_requests.py` 与队列联动测试 |

表中短路径的 Runtime 测试均相对 `apps/runtime-service/`；API 测试相对 `apps/platform-api/tests/`。

## 3. 集成与真实链路矩阵

| 编号 | 触发步骤 | 必须观察到的结果 |
| --- | --- | --- |
| I01 | 正常短任务，经平台创建 Run 并订阅 | 无收尾提示；原有回答、审批、工具/产物和 success 行为保持 |
| I02 | 可控制模型/工具推进到 H-G，随后再调用模型 | 捕获真实模型请求包含一次收尾指令；可在 H 前正常结束；报告不伪称所有目标完成 |
| I03 | 单次工具或模型跨过软窗口，之后没有模型请求；另测慢 factory | 不能要求最终总结；Worker 在 H 触发取消，原生 timeout 唯一落库，factory/子任务已计入 H |
| I04 | M<H 的慢模型/provider TimeoutError，与 M>H 的慢模型分别执行 | 前两者未被图内策略恢复时单 attempt error，不 Worker 重跑；后者 Worker timeout，来源与终态不混同 |
| I05 | 同 Run 注入可恢复数据库故障，等待退避再领取；另测次数耗尽 | run_id 不变；新 attempt 采用新 H/deadline，从当前 Run checkpoint 继续，已完成节点不重执行；实际故障次数到上限 error |
| I06 | Run 开始后停止隔离 Worker，等待旧 deadline 过去再由新 PID 接管 | 同 run_id 从完整 checkpoint 继续，获得新 attempt H；不会因旧 deadline 到期直接 timeout |
| I07 | 接近当前 H 时 SIGTERM，另测反复正常 checkpoint drain | drain 最多当前剩余 H；后续 claim 新预算；正常 handoff 不占故障 attempt，旧 owner/generation 不能写新执行 |
| I08 | 到 H 前后与用户 cancel 并发，多次重复 cancel | timeout 或 interrupted/cancel_requested 首个合法终态获胜；唯一 durable 终态，无互相覆盖 |
| I09 | HITL 到 interrupted，人工等待超过 H 后 resume | 等待不被误杀；原 Run 保持 interrupted/hitl_interrupt，恢复创建新 run_id/预算；禁止自动批准 |
| I10 | 排队时间超过 H；另测 Thread 下一回合和新 cron occurrence | 首次 pending 不耗 H；开始后各 Run 独立计时，新回合不继承旧预算 |
| I11 | 并行启动三个 Thread，包含主 Agent + 两个子 Agent | 根/子共享截止点，各 Thread 独立；一个 timeout 不取消其他 Run，父取消传播到其子任务 |
| I12 | SSE 断流/410/重连/关闭浏览器后到 H，再 GET/rejoin | 连接不重置/取消 Run，无新提交；timeout 可持久回查，消息/完整 checkpoint/已提交产物可恢复 |
| I13 | 收尾时补充消息入队，分别制造已消费/未消费/ACK 未知 | 回执保留，不刷新预算；未消费/未知不假报成功、不自动重复提交，FIFO沿既有队列专项 |
| I14 | async 模型、workspace Docker/local 执行、远端请求分别在到期时取消 | 支持路径无残留；外部未知明确记录；忽略取消或阻塞事件循环的路径不得以 timeout 终态掩盖资源仍运行 |
| I15 | 使用正式增强 wheel 冷安装，查询 schema 后再执行 | 不依赖参考源码/本机资源，API/Worker版本一致；预算与middleware实际生效 |
| I16 | 降低/提高新 Worker H，接管旧 Run；测试无预算的升级遗留 Run | 本 attempt H 不变；下一 claim 使用接管 Worker 的 H；遗留 Run 生成新 attempt 预算，不按 created_at 追溯累计时长 |

Runtime 原有 durable 入口保留；本轮精确预算、重启及平台 HTTP 场景实际落在仓库根 `scripts/verify_run_timeout_budget.py`，测试图为 `apps/runtime-service/tests/acceptance_app/run_budget_probe.py`，没有新建 `tests/durable/test_run_timeout_budget.py`。测试图不放进业务 Agent 注册。

## 4. 前端与安全验收

前端由同事执行 [交接文档](frontend-handoff.md) F01-F10，至少通过一条浏览器 `platform-web -> platform-api -> Runtime Worker -> timeout -> Run 查询/恢复` 全链路。桌面 1440px 与移动 390px 核实状态条、停止按钮、审批卡片、消息/产物与输入状态；没有前端实现变动也必须回归。

安全验收覆盖权限未放宽、resume 不能改预算、Thread/Assistant/cron/metadata 伪造、私有字段 GET/list/history/SSE/trace 泄漏、模型错误不带 secret，以及收尾不得免审批或跨项目取消。优先复用当前错误 envelope、ACL 和网关白名单；这是运行参数边界测试，不扩大为鉴权系统改造。

性能只测新 claim JSONB 更新、预算解析、模型 prompt 追加与取消清理开销，并与相同环境基线比较，记录实测值及测试负载。软收尾无需新增轮询、每 token 数据库写或独立清扫定时器；没有获批 SLO 不编造生产性能门槛。

## 5. 回退验收

- [x] R01：正式post42 HTTP `disable-reminder` 实际请求无收尾指令，G=0仅关闭提示；增强Worker硬限保持。
- [x] R02：正式包真实SIGTERM/新PID/新attempt通过；匹配回退时drain退出0、暂停新提交，再切换API和Worker，未混跑并承诺新版语义。
- [x] R03：旧Runtime源码从基点导出并配post41双包，真实Reference Agent组合根在独立API/Worker进程中复验普通/取消/HITL成功；新Runtime不能只降依赖。
- [x] R04：回退后同Run从checkpoint继续，已完成prepare节点不重执行；pending Run后续执行、history和已提交工作区产物保留，无Schema migration。直接产物见 [rollback JSON](evidence/run-budget-pypi-post42-rollback.json)。

## 6. 命令入口

以下为可复现入口。Runtime正式锁文件已post42，可 `uv sync --frozen`；正式冷环境验证显式Python和PYTHONPATH，防止导入主checkout的旧editable源码。命令不包含现役操作；涉及清库的HTTP/回退入口只能使用独立测试实例。

Runtime 定向验证：

```bash
# 工作目录 apps/runtime-service
PYTHONPATH="src:tests" PYTHONDONTWRITEBYTECODE=1 /tmp/run-budget-pypi-post42-venv/bin/python -m pytest -q -p no:cacheprovider tests/runtime/test_run_budget.py tests/middlewares/test_timeout_wrapup.py tests/middlewares/test_runtime_middleware.py tests/services/reference_agent/test_middleware_order.py
PYTHONPATH="src:tests" PYTHONDONTWRITEBYTECODE=1 /tmp/run-budget-pypi-post42-venv/bin/python -m pytest -q -p no:cacheprovider tests/runtime/test_runtime_config_validation.py tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_execution.py tests/services/dearflow_agent/test_subagents.py tests/services/showcase_demo/test_agent.py tests/services/workflow_demo/test_agent.py
ruff check src/runtime_service/runtime/run_budget.py src/runtime_service/middlewares/timeout_wrapup.py src/runtime_service/middlewares/model_call_timeout.py
```

HTTP验收入口在仓库根执行，需预先准备上述专用库/Redis及正式双包冷环境。脚本会清空专用验收库并启停临时Worker，只能使用固定测试库和前缀，不能换成现役环境。PG/Redis连接由验收环境注入，勿打印凭据：

```bash
# 工作目录仓库根，DATABASE_URI/REDIS_URI 已指向专用验收资源
GRAPHHARBOR_REDIS_PREFIX="graphharbor:run-budget-e2e:e7dd" PYTHONPATH="apps/runtime-service/src:apps/platform-api/src:scripts" PYTHONDONTWRITEBYTECODE=1 /tmp/run-budget-pypi-post42-venv/bin/python scripts/verify_run_timeout_budget.py
```

API 定向验证与全量入口：

```bash
# 工作目录 apps/platform-api；采用已有 unittest 测试范式
PYTHONPATH="src" .venv/bin/python -m unittest discover -s tests -p 'test_run_timeout_contract.py'
PYTHONPATH="src" /tmp/run-budget-pypi-post42-venv/bin/python -m pytest -q tests
```

匹配回退入口，仓库根执行；DATABASE_URI仅可指向独立localhost测试实例的固定验收库。`<legacy-runtime-src>` 为基点 `0bc15df1840c83750d821c93fb65600d0d483fa4` 导出的旧Runtime源码，`<post41-python>` 为安装旧双包的Python，不创建分支/worktree：

```bash
GRAPHHARBOR_REDIS_PREFIX="graphharbor:run-release:e7dd" /tmp/run-budget-pypi-post42-venv/bin/python scripts/verify_run_timeout_rollback.py --current-python /tmp/run-budget-pypi-post42-venv/bin/python --legacy-python "<post41-python>" --current-source apps/runtime-service/src --legacy-source "<legacy-runtime-src>" --output /tmp/run-budget-pypi-post42-rollback.json
```

GraphHarbor本次复用取消专项正式四产物，不再构建/上传同版本候选文件。原仓预算、生产、持久化、checkpoint变更安全与公开契约测试只能在专用PG/Redis运行；官方探针 `scripts/verify_official_worker_timeout.py` 采用锁定worker与隔离graph/DB sink，不等同官方生产分布式E2E。Web命令见交接。

## 7. Phase 验证记录

### 详细前端交接与经验库 2026-10-07

- 用户要求详细交接并批准经验沉淀。核对当前Web的service/composable/组件与锁文件，交接明确三处必改：可见timeout状态、post42目标Run停止确认、已核实success才触发推荐。停止可以用单次JSON wait=true；恢复、审批、队列和权限复用已有实现。
- 本轮9份受影响文档使用`check_docs.py`的self_check/check_file定向通过；Markdown代码围栏/行尾空白与本次相对链接检查通过。25处现有源码、测试及fixture引用确实存在，`e2e/run-timeout-governance.spec.ts`尚不存在且正确标为待同事创建；经验库条数为5，与索引一致。`git diff --check`通过，未提交/建分支。
- 全仓`python3 scripts/check_docs.py`仍报告34处其他文档的既有本机绝对路径；FEATURES的3个既有失效链接（旧Web变更记录、deployment-guide、operator-handoff）已用HEAD正文对照。本次新增交接链接有效，未扩大修改这些范围外条目。
- 本轮仅更新文档与用户批准的发布协作经验，未修改Web源码，未运行Vitest/Playwright或启动、升级共享服务。T11/F01-F10与T12联合Final仍未完成；不能将文档验证写成浏览器通过。

### 非前端文档与静态收口 2026-10-07

- 平台相关源码/测试/验收脚本Ruff check通过，31份format check通过；GraphHarbor双包源码/测试及官方探针Ruff check通过，70份format check通过。
- Runtime、Platform API与GraphHarbor的 `uv lock --check` 均通过；Runtime仅两个GraphHarbor包升级，API锁文件不变。两仓 `git diff --check` 通过。
- 平台16份、GraphHarbor11份专项/受影响文档定向checker通过，项目本地相对链接存在；README/plan/tasks/verification/CONTEXT/FEATURES状态一致。未扩大修复既有全仓路径/链接问题。
- 本轮再查PyPI四文件哈希一致，证据 `pypi-post42-verification.json`；正式冷安装49个GraphHarbor Python文件逐字匹配独立仓库当前源码，证据在该仓G07的 `evidence/pypi-source-match.json`。旧候选哈希不代表发布文件。
- 进程检查仅见共享现役和系统PG/Redis，本次临时API/Worker及独立PG/Redis均退出。当前共享8123进程来自其他worktree，读取其虚拟环境metadata仍post41；本会话没有重启该服务，不能作前端post42联调环境。
- 当前worktree detached HEAD，基点 `0bc15df1840c83750d821c93fb65600d0d483fa4`，无新分支/提交/推送。剩余实施Task逐项核对为T11与依赖它的T12联合Final；没有其他本轮非前端block。平台Final未执行，不替SSE/JWT草案毕业。

### T10/T13/T12 正式PyPI接入与非前端验收 2026-10-07（恢复后）

用户确认另一专项结束并要求继续；post42已由取消专项正式发布。先查询两个PyPI版本的四文件SHA256，与 [发布清单](evidence/release-artifacts.json) 一致；没有重复上传、使用旧候选文件覆盖同版本或重新读取发布令牌。

- Runtime仅将两个GraphHarbor包从post41升post42，锁文件仅对应版本及产物信息变化，其余依赖版本不漂移。`uv sync --frozen` / 141项依赖check通过；独立Python3.13.9冻结冷环境142项依赖check通过。生产依赖不含langgraph-api。
- 正式包 `scripts/verify_run_timeout_budget.py` 二轮完整12组退出0，原始日志含结果JSON，见 [HTTP日志](evidence/run-budget-pypi-post42-http-e2e-r2.log)。首轮因验收脚本误将原生cancel的202用于平台ACK而退出1；按平台既有 `200 {"ok":true}` 修正断言后二轮通过，没有改变平台公开响应。

| 场景 | 结果 | 真实run_id / 证据 |
| --- | --- | --- |
| short | success | `aa9de36d-a2f1-4a6f-9204-f878dcbd79bf` |
| wrapup | success，实际模型请求有收尾提示 | `6ecb4cf6-835e-4fc3-aacf-9da8b8e4485f` |
| slow | timeout | `8e8ad5e8-7611-4f12-8a95-28b40bae5759` |
| model-timeout | 单attempt error | `4869ea23-d7be-48b5-8949-5de73d1d1441` |
| hitl-new-run | 人工等待超过H，resume新Run success | `13151343-fa3b-4461-b850-5f1b82a03531` |
| restart-fresh-attempt | 同Run新attempt H=20 timeout，旧H=30已过 | `875b0bbd-3481-47ec-887f-c4638f589d1c`；PID `11475 -> 12285` |
| three-thread-isolation | 一个timeout、两个success互不取消 | HTTP日志对应三个Thread |
| sse-disconnect-rejoin-next-run | passed，无重复Run，后一Run新预算 | `2db29999-595b-4ad8-923e-6bf9436dea22` |
| cancel-timeout-race | passed，首次合法终态唯一 | deadline前/当时/后，重复cancel |
| queued-message-does-not-renew-budget | passed | 排队Run尚无预算，领取后独立计时 |
| disable-reminder | passed，G=0没有提示 | 真实请求内容断言 |
| http-private-budget-rejection | passed | top-level/config/input注入400 |

每个inspect同时断言租约释放、durable终态恰好1条、私有预算不在公开Run/事件、完整checkpoint和已提交文件可回查。SSE故意断开时日志有一次SQLAlchemy连接关闭的CancelledError诊断；后续同Run回查/rejoin/下一Run均通过，保留诊断，不将其隐藏或算成测试失败。

- 匹配版本回退脚本 [verify_run_timeout_rollback.py](../../../scripts/verify_run_timeout_rollback.py) 第六轮退出0，见 [回退JSON](evidence/run-budget-pypi-post42-rollback.json) 与 [日志](evidence/run-budget-pypi-post42-rollback-r6.log)。API/Worker为真实独立进程、独立PG/Redis；使用两版真实Reference Agent组合根、确定性fake model和测试Auth，不需要供应商key。旧源码通过git archive导出到临时目录，无新分支/worktree。
- 先当前源码/post42成功run `8803dd37-c0c0-447b-bd75-28acfe9110a5`；SIGTERM/drain退出0、暂停提交、切换旧源码/post41后，同run `e9fd1e38-5d4c-4cf0-9e06-aea029d680b6` 从checkpoint继续，prepare节点不重执行；pending `e3733be2-1b8e-4030-955d-8b059110bc4a` 随后执行。history/产物保留，无Schema migration。
- 回退后普通run `77583f93-b76c-4eee-b944-f6c08c563289`、取消 `8e5e6943-cce4-4c8b-adda-5660c7ddb4cc`、HITL `62c39b5a-c6fc-4953-aab7-8fdbce8d33a6` / resume `2b67e0d0-86a0-4c99-acb1-67ab8737a0da` 通过。早期回退夹具因缺dependencies/测试Auth身份/签名secret失败，补齐脚手架后通过；这些轮次不冒充实现缺陷或通过。

| 回归范围 | 实际结果 | 保留证据与限制 |
| --- | --- | --- |
| Runtime定向 | 125 passed/1 failed/3 skipped，唯一失败为Docker未启动 | `run-budget-pypi-post42-runtime-phase.log`；Docker启动后唯一用例重跑1 passed，见 `runtime-docker-recheck.log`，不相加伪造全量数字 |
| API SDK0.4.3定向 | 84 passed/23 subtests | `run-budget-pypi-post42-api-phase.log` |
| 停止确认投影/脱敏 | 19 passed/13 subtests | `run-budget-pypi-post42-cancel-projection.log`；true/false与lease_fenced保持，私有预算过滤 |
| API自身冻结环境 | SDK0.4.2/Python3.14.6，85项unittest通过 | `run-budget-api-own-lock-phase.log`；五文件覆盖预算/SDK适配/脱敏/Run契约/幂等，API锁文件未变 |
| Runtime全量 | 617 passed/2 failed/34 skipped/51 deselected/42 warnings，224.41秒 | 两项 `tests/test_terminal.py` PTY回显/文件时序失败；旧源码相同两项复现，见terminal baseline |
| API全量 | 326 passed/2 failed/16 skipped/654 subtests/1 warning，103.59秒 | 两项workspace真实双服务测试仍断言去除script，与既有HTML沙箱行为不同；旧Runtime源码相同两项复现，见workspace baseline。执行早于新增停止确认测试 |

表中日志均在 [evidence](evidence/README.md)。旧源码对照没有执行本次改动；没有修无关PTY或改变HTML安全契约，也没有宣称全仓全绿。早期MCP服务、双服务向量和安装定位三项环境限制在本轮已解除；skip/deselected不计通过，重叠定向集不相加。

性能证据 [microbenchmark](evidence/run-budget-microbenchmark.json)：每项10000次，load约7.398/10.200/12.374；预算解析8.061us、裸handler0.200us、软窗口前0.542us、窗口内prompt追加42.731us。仅进程内微基准，未测供应商/DB吞吐或生产SLO；收尾无需新增轮询/每token写库。确定性fake-model证明提示送达，不保证任意真实模型遵从或外部操作被撤销。

T10/T13与T12非前端门禁done；本记录仍为Phase，完整平台Final必须等待同事F01-F10。现役8123/2142/3000没有升级或重启；本会话只升级当前worktree依赖，不提交/推送。历史暂停、404及高负载失败保持在下方原阶段记录。

### T10 发布前检查 2026-10-07（用户暂停）

用户已授权从本机 `~/.my_best/.env` 使用发布令牌；仅核对键名，未读取令牌值、执行上传或更新平台锁。随后用户确认另一会话仍实施 GraphHarbor 取消传播并要求暂停。以下均为Phase证据，不能记为最终发布或整体完成。

- 当前GraphHarbor源码预算/取消定向：31 passed、2 warnings，日志 `/tmp/run-budget-release-worker-preflight.log`；与后续回归有重叠。
- `uv lock --check`、双包锁步检查、源码Ruff/format、mypy（38文件）通过；官方Worker探针4项通过，锁定版本和SHA256与T13一致。
- 兼容基线脚本因文档迁移后旧路径失败；仅修正实际矩阵/排除项路径、矩阵双包版本到post42，保留原官方协议核验日期。修正后 `check_compatibility_baseline.py` 通过；声明检查不等于重新通过全部官方协议。
- 完整隔离回归首轮260 passed、8 skipped、13 deselected、4 failed：2个Cron用例要求专用库/前缀，1个旧批量取消200断言应为204，1个trace测试替身没有停止确认数据。补齐REST的204/202断言，并让trace测试复用no-op隔离已在其他用例覆盖的持久停止确认。
- 第二轮独立PG/Redis、除专用Cron模块外：261 passed、8 skipped、13 deselected、4 warnings，71.79秒，日志 `/tmp/run-budget-release-graphharbor-regression-r2.log`。Cron在其要求的独立库和前缀单独执行：3 passed、2 warnings，8.00秒，日志 `/tmp/run-budget-release-cron-regression.log`。skip不计通过。
- 低负载HTTP使用冻结的超时候选环境，已有short/wrapup/slow/model-timeout、HITL新Run、真实Worker接管、三Thread隔离和SSE回查的局部输出；在取消竞态过程中按用户指令SIGINT退出254，未产出完整12组汇总，日志 `/tmp/run-budget-release-http-e2e.log`。不是当前持续变化的取消传播源码的完整验收。
- 当时平台HTTP脚本误按原生GraphHarbor202调整取消断言，尚未最终联验；恢复后按平台200 ACK更正并通过完整矩阵，见上方新Phase。临时双包未上传，另一会话继续改源码；本轮恢复使用最终正式PyPI产物。
- 本会话临时API/Worker、测试PG/Redis和命令会话已退出；未触碰共享8123/2142/3000服务。保留未提交代码、候选产物和日志，等待用户恢复。

### T13 官方 Worker 对齐 2026-10-07

以官方 `langgraph-api==0.13.0` 为证据：每 attempt 新 H；Worker 硬限 timeout 不重试；用户/provider TimeoutError error；正常 handoff 不占故障次数。官方 `worker.py` SHA256 为 `cd6775e2267d9bd4cb6fdc83fd0c133311dc7ccf1d7776e12ad335973f3a33cd`。源码/文档边界见 [对照](langgraph-worker-parity.md)。

- 官方隔离 worker 探针四项通过：provider 超时 error、硬超时 timeout、旧 deadline 后新 attempt 成功、attempt 4 被默认上限拒绝；不替代官方生产数据库/分布式差分。
- GraphHarbor 专用 PG/Redis 五集回归：`116 passed, 4 skipped, 4 warnings in 231.38s`，日志 `/tmp/run-budget-official-regression-r2.log`。4 个 skip 来自既有 SDK 夹具缺项；4 个 warning 为 v3 流协议实验提示，均不算新增能力证据。
- 真实 checkpoint 测试调用顺序为 `first, second, second`，首节点未重执行。六次正常 drain 归还 attempt，随后按 2/5 次配置故障上限 error；generation 始终递增，旧 owner 写入被拒绝。
- 改动三模块 mypy（follow-imports=skip）通过；六个源码/测试/官方探针 Ruff check 与 format check 通过。无 asyncpg 类型桩仅做窄 import-untyped 标注，DBAPIError.orig=None 显式守卫。
- 首轮回归 `114 passed, 4 skipped, 1 failed` 的唯一失败是旧测试把普通 ConnectionError 当 DB 故障；按官方分类改用 psycopg OperationalError 注入后上述二轮通过。早期 0.35 秒硬限被本机初始化耗尽的夹具改为 2 秒，仍验证 factory/执行/drain 不加时。
- 后续补指定历史 checkpoint 的恢复分支：先查询最新 checkpoint，确属本 Run 才移除原 checkpoint_id 并以 None input 继续。普通/指定 checkpoint 两种路径均 `first, second, second`；含重试预算/DB 异常边界定向 `4 passed, 10 deselected, 2 warnings in 85.88s`，日志 `/tmp/run-budget-official-checkpoint-final.log`。与116集重叠，不相加。
- 本机高负载（当时 1 分钟 load average 813）使原 5 秒恢复测试和首次 HTTP 8 秒短任务撞硬限；这两轮未通过、不作为能力证据。状态测试改受控旧 deadline、恢复 H=60；HTTP 先 schema 构图并用 H=30/G=10。真实慢 factory/执行/drain 的 H=2 证据保留，生产时长不变。
- 最终候选双包重构建；新隔离环境确认 Runtime 模块与最终源码逐字一致，SDK仍锁0.4.3。一次安装误解析新依赖后已用原142项冻结清单同步回锁定依赖，未用该中间组合验收。最终 wheel SHA256：CLI `f0bdd00ba7361dbbb45803ab54a88aaab3d9e2b6625499d3fb243ffed40e57d7`，Runtime `066e3ee102817ac201576d7952e45621c6cbdd978e2fa9b62f3f28f33dffc6ae`。

- 最新冷环境 Runtime `test_run_budget.py/test_timeout_wrapup.py`：`32 passed, 5 warnings in 5.32s`（SWIG弃用）；API unittest超时契约3项通过。PYTHONPATH均显式指向本worktree，未混用旧editable源码。
- 最终双包模块逐字核对当前源码，版本graphharbor/runtime=post42、LangGraph1.2.11、SDK0.4.3、LangChain-core1.6.0、SQLAlchemy2.0.52；没有正式发布/接入。10-07 PyPI双包post42再次实际返回404。
- **最新平台HTTP blocked：** 首轮日志 `/tmp/run-budget-official-http-e2e.log`，H=8普通short最终timeout；第二轮 `/tmp/run-budget-official-http-e2e-r2.log`，schema预热且H=30后short仍在factory打开前到期，run `a5f4f1b6-9b55-4d78-8f0c-8aa92e08b728`。两轮均退出1，未完成12组矩阵/真实重启；不将其写成通过。高负载下当前环境不能给出短时序链路证据，需要低负载隔离PG/Redis复验。同名版本旧wheel或10-06旧设计HTTP不能替代。
- 两仓diff检查通过；平台本次14份文档checker/21个项目链接、GraphHarbor9份checker与项目链接通过。对索引全链接扩查另发现既有FEATURES3条/profile1条失效链接，本轮未扩大改动。未完成项目不触发其他标准毕业。

上述为恢复前T13/G07的partial/blocked判断，临时进程已退出；恢复后正式包HTTP/锁定及匹配回退已通过，见本节最新Phase。旧候选哈希不作为当前发布哈希。

### 10-06 历史阶段说明

以下保留原实施时真实结果。涉及“跨 attempt 不续期”“模型自动 Worker retry”“旧 deadline 后不打开图”的条目已被 T13 取代，不能用于现行验收；Runtime/API/资源清理中与修订无冲突的证据继续有效。

### T01 人工评审 2026-10-06

用户明确完成评审并授权推进到仅剩前端；批准范围见 README.md。已核对 GraphHarbor 正式源码。

### T02 持久预算与Worker 2026-10-06

正式源码定向16 passed；预算/生产/持久化/公开契约合计 `100 passed, 4 skipped, 4 warnings`。真实PG/Redis覆盖首次冻结、retry/reaper/shutdown保留、到期不打开图、慢factory/drain不加时、模型次数先耗尽error和预算先耗尽timeout。4个skip属上游SDK夹具缺项，不算通过。

### T03 受信预算解析 2026-10-06

`tests/runtime/test_run_budget.py` 验证不可变对象、版本/bool/NaN/Infinity/UTC/身份/窗口、schema允许缺预算而正式执行拒绝。包含在Runtime定向 `109 passed, 1 skipped` 中；HTTP探针进一步证明读到post42 Worker预算，不以测试注入替代Worker证据。

### T04 通用收尾 2026-10-06

`tests/middlewares/test_timeout_wrapup.py` 验证窗口边界、结构化/多模态/cache_control保留、去重和真实create_agent请求；HTTP wrapup与G=0场景通过。soft提醒是实际请求内容，不是“模型必定服从”的证明。

### T05 超时来源 2026-10-06

模型scope/provider原TimeoutError/外部取消测试通过；GraphHarbor真实重试证明次数与预算两种终态。HTTP model-timeout连续两次scope过期最终error，slow由整体预算最终timeout，未新建Worker错误分类框架。

### T06 四图及主子组合 2026-10-06

DearFlow、Showcase、Reference、Workflow真实fake-model组合、主/并行子Agent共享、workflow重建、HITL恢复及schema验证通过。预算/收尾/schema/主子取消/真实Docker定向合计 `53 passed, 1 skipped`；与109集有重叠，不能相加作总数。未启用的真实供应商用例不算通过。

### T07 配置与冷启动 2026-10-06

预检和公开模板测试通过，H/G默认/非法/关闭/边界验证完成；根stack API与Worker传同一新变量。候选wheel环境实际启动API/Worker，首次H=30、新Worker H=600仍使用原deadline，未改现役配置或锁文件。

### T08 API边界 2026-10-06

API全量 `321 passed, 23 skipped, 606 subtests passed`；递归预算注入拒绝、GET/history/SSE脱敏、completed不覆盖timeout，以及权限/幂等既有契约通过。HTTP以平台认证和项目归属通过Run创建/回查、相同幂等键只创建一个Run，伪造内部预算返回400；23个skip不算通过。

### T09 取消与资源 2026-10-06

local shell取消/工具回归 `15 passed`，新增取消测试确认进程组退出且子进程不在取消后写入文件；真实Docker和主子取消包含在53集。HTTP每次回查同时断言租约已释放、durable终态恰好1条、私有预算不在公开结果/事件、已提交文件与最后完整checkpoint仍可读。远端供应商操作是否被撤销仍为unknown，不声称全量保存。

### T10 非前端隔离验收与发布阻塞 2026-10-06

本地post42双包wheel/sdist构建、冷安装与版本签名核对通过。`scripts/verify_run_timeout_budget.py` 首轮完整HTTP验收退出码0，日志为 `/tmp/run-budget-http-e2e.log`，末尾JSON含12组结果。真实链路为 Platform API -> GraphHarbor API/Worker -> 测试graph -> PG checkpoint/事件 -> 平台回查；测试图可控制模型，不需要外部供应商凭据。

| 场景 | 实际结果 | 对应证据 |
| --- | --- | --- |
| short | success | run `4d15d613-34bb-4f04-be56-3307e179ac29` |
| wrapup | success，实际请求有提示 | run `d931b741-43dd-47bc-abb3-e2f9be4a4336` |
| slow | timeout，终态1条 | run `0a321bd0-78dc-4da6-a1cb-ada11887157d`，thread `69f736fa-6a93-4627-9071-dae9b21f9357` |
| model-timeout | error，原预算不刷新 | run `2f03271d-5dae-48d6-8d89-162165e882d6` |
| hitl-new-run | interrupted后等待超过H，resume新Run success | run `deba1ec2-ca48-41ab-8708-d508005bfbe5` |
| restart-no-renewal | timeout，旧/新deadline相同、到期不再次构图 | run `e81d1534-bfbd-44f0-8df5-0c1e0c24f2b6`；Worker PID `60590 -> 62050` |
| three-thread-isolation | passed | 一个timeout、两个success，互不取消 |
| sse-disconnect-rejoin-next-run | passed | run `43513ca9-37a9-48c9-9b15-18cf014ca62d`；重连前后仅1个原Run，后一Run新预算 |
| cancel-timeout-race | passed | deadline前/当时/后三次竞态，重复cancel，唯一合法终态 |
| queued-message-does-not-renew-budget | passed | 排队Run未冻结预算；前Run timeout后新claim单独计时 |
| disable-reminder | passed | G=0实际模型请求无收尾提示 |
| http-private-budget-rejection | passed | top-level/config/input注入均400 |

**发布阻塞：** PyPI `/pypi/graphharbor/0.13.0.post42/json` 与 `/pypi/graphharbor-runtime/0.13.0.post42/json` 实际返回404。未上传；锁文件仍post41。需维护方正式发布后锁定、从PyPI冷安装复验；本地wheel不冒充该门禁。

### T12 非前端全量门禁现状 2026-10-06

Runtime冷环境全量首轮为 `614 passed, 5 failed, 34 skipped, 51 deselected`，**不是全量通过**。未通过项不涉及本次预算逻辑，但仍保留在完整验收待办：

| 未通过项 | 实际限制/原因 | 当前处理 |
| --- | --- | --- |
| MCP真实测试服务 | 测试子进程未能启动服务 | 环境前提失败，未用skip冒充通过 |
| 双服务context/answer vectors | 硬编码 `apps/platform-api/.venv/bin/python`，当前worktree无此专用venv | 主checkout安装不作为本worktree证据 |
| 隔离Python包定位 | 冷venv只装依赖、未安装当前Runtime项目；子进程不继承pytest的pythonpath | 当前定向/HTTP验证显式PYTHONPATH指向本worktree |
| 两项PTY终端用例 | `wait_output`匹配命令回显过早，断言文件时尚未写完 | 既有测试时序问题；本次local shell取消有独立用例证据，不改无关PTY实现 |

R01关闭提醒和真实SIGTERM/drain已通过；post41回退冷环境确认没有增强预算参数，但完整Runtime/依赖组合回退尚未通过R02-R04门禁。未执行真实供应商效果观察、生产性能基准或浏览器F01-F10，不将这些写成通过。新增逻辑无独立轮询或每tokenDB写入，未擅设生产SLO。

环境修正记录：API新契约首轮被主checkout的editable安装导向旧源码，已改显式PYTHONPATH重跑；socket数据库URI在依赖URL规范化中不兼容，改专用localhost库。两者未影响现役库/进程。

### 收尾定向复验与文档检查 2026-10-06

- Runtime显式候选环境重跑预算、收尾、配置、DearFlow执行、Reference顺序、Showcase和Workflow：`89 passed, 1 skipped, 5 warnings in 294.38s`；5个warning是PyMuPDF SWIG弃用，未作为失败或新增能力证据。与前述定向集重叠，不相加。
- 本次测试换行修正后，`test_local_cancellation_kills_shell_and_children` 单独复跑 `1 passed, 3 deselected, 5 warnings`，取消后子进程无写入。
- API `python -m unittest discover -s tests -p test_run_timeout_contract.py`：3项通过；从本worktree显式PYTHONPATH导入，未误用主checkout源码。
- 相关Runtime源码/测试/验收脚本Ruff check通过，format check显示26份已格式化；API/私有预算/验收探针等10份format check也通过，两个集合有重叠。仅修正本次新增取消测试的换行，没有扩展功能范围。
- 平台仓和GraphHarbor仓 `git diff --check` 均通过。本次平台12份文档定向checker通过，项目15个本地相对链接存在；GraphHarbor本次7份文档路径/格式/链接检查通过。
- 全仓 `python3 scripts/check_docs.py` 返回1：仍为实施前34条既有本机绝对路径问题，本次没有新增。实施中出现的2条专项绝对路径已修正，不借此改动其他项目文档。系统无 `python` 命令，实际使用 `python3` 执行checker。
- 工作树复核：当前e7dd为detached HEAD，基点 `0bc15df1840c83750d821c93fb65600d0d483fa4`；没有新增分支、commit、push或PyPI发布。完整Final仍未执行。

### 2026-10-06：规划基线

| 检查 | 实际结果 | 证据边界 |
| --- | --- | --- |
| 源码/版本核对 | 已完成，见 open-swe-comparison.md | open-swe 有本地修改/冲突；锁定安装源码 post41，不是依赖增强的发布包 |
| 现有模型 timeout 定向测试 | `3 passed, 13 deselected, 5 warnings` | 仅现有 `test_runtime_middleware.py -k model_call_timeout`；warnings 为 PyMuPDF SWIG 弃用，不证明新收尾/持久预算已实现 |
| 编辑前全仓文档检查 | 失败：34 条既有本机绝对路径 | 位于既有 open-swe/deerflow 分析和 followup/scheduled 项目文档，本轮不修改这些无关文件 |
| 新增/修改文档定向检查 | 通过：8 份文档 | 使用现有 checker 的 self_check/check_file，覆盖本项目 6 份文档、FEATURES 与 CONTEXT |
| 项目相对链接与格式 | 通过：15 个本地链接、6 份项目文档 | 项目内链接及两个索引指向该项目的链接存在；无尾随空白/冲突标记，文件末尾换行有效 |
| 文件符号/diff 范围 | 通过 | 组合根/Worker/网关/前端既有符号已核对，新符号与测试标“拟新增”；git diff --check 通过，git status 仅有 8 份本轮文档 |
| 编辑后全仓文档检查 | 仍失败：同样 34 条既有绝对路径 | 本次 8 份文档没有新增问题；不顺带修复其他项目/知识文档 |

以上是实施前的规划基线，只描述当时阶段；实施后的真实新增能力和隔离证据以本节T02-T12记录为准，不用基线替代增强能力验收。

模型基线实际执行的是主 checkout 的已安装 Runtime Python，从本工作树导入 `src/tests`，未在该工作树安装依赖。可复现等价入口：

```bash
# 仓库根；将 <runtime-venv> 替换为已有、版本匹配的 Runtime 虚拟环境
PYTHONPATH="apps/runtime-service/src:apps/runtime-service/tests" PYTHONDONTWRITEBYTECODE=1 "<runtime-venv>/bin/python" -m pytest -q -p no:cacheprovider "apps/runtime-service/tests/middlewares/test_runtime_middleware.py" -k "model_call_timeout"
```

新增规划文档不得将上述 Phase 基线写成 Final done。

## 8. Final 验证记录

**完整 Final 已执行并通过（done，2026-10-08）。**
用户已在真实浏览器环境（http://127.0.0.1:3000）完成端到端联调验收；本地 3 个服务已安全停止；所有任务项全部闭环。

- **项目四态：** done；T01-T13、T11、T12 全量通过，无遗留未决项。
- **前端（T11）：**
  - F01-F10 规范对齐完成，单测（108/108）、vue-tsc（0 errors）、lint 与 production build 打包全绿；
  - 核心包含：`ChatAgentStatusBar.vue` 超时黄色警示胶囊、`stopping` 转圈、`stop_unconfirmed` 核实按钮、`ChatComposer.vue` 停止期间全面封锁输入与提交、`useChatSession.ts` 单一事实源与双通道停止确认防死锁。
- **端到端用户验收与排队死锁根治（T12）：**
  - 用户在真实会话中发现并排查了切回历史对话时的未决待确认死锁与黄框横幅闪现问题；
  - 治本解决了 `storageKey` 响应式漂移导致的幽灵未决锁残留，补充了 `queuedRuns` 与 `service.runs(threadId)` 历史列表双重自愈机制；
  - 增设【放弃并恢复草稿】逃生通道，解除了正常排队时的误警示；
  - 用户在浏览器实际交互验证中明确确认“这块我验收通过了”。
- **正式依赖（T10/T13）：**
  - post42 四产物正式 PyPI 发布与哈希核对一致，Runtime 依赖锁定与冷安装通过；
  - 12 组 HTTP 场景（软收尾/硬限/模型error/HITL/多Thread隔离/SSE/取消竞态/G=0/防注入）与真实 SIGTERM 新 PID 接管通过。
- **回退/全量：**
  - R01-R04 匹配版本回退验证通过；
  - 四项既有外围失败（PTY 回显时序与 HTML 预览断言）已与旧源码对照确认无关联，未改动无关代码。
- **服务状态：**
  - 本地所有服务（Web 3000、API 2142、Runtime 8123）已全部安全停止，端口与子进程已安全释放。
  - 准备按规范合入主工作区分支 `feat/langgraph-v3-delta-evaluation`。
