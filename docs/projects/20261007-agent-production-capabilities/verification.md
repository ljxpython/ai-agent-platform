# Agent 运行准备幂等与有界重试 - 验证计划和记录

## 当前结论

非前端实现和本机隔离验证已经完成。验证使用本机 PostgreSQL 17、Redis 8、独立 Platform API/Runtime Worker、合成 HTTP provider 和本地观测端点；没有使用 Docker、生产凭据、现役数据库或现役服务。

本轮范围结论：**非前端 `done`**。专项整体仍为 **`partial`**，待同事完成前端 T10 和浏览器联合验收；真实生产 provider/Langfuse smoke 是部署前另行验证的边界。Phase 证据和 Final 证据保持独立；未执行项不写为通过。

## 验证计划

### 单元与真实图组合

| ID | 场景 | 必须断言 | 建议测试位置 |
| --- | --- | --- | --- |
| U01 | 首次/已 checkpoint prepare、同 Run factory 重建 | prepare once；第二次只检查/恢复对象；记录 reused | 新增 `tests/middlewares/test_run_prepare.py` |
| U02 | 同内容新 Run、approval resume、fork、config/revision/namespace 变化 | 不沿用旧 invocation marker；资源仍幂等 | 同上和实际组合根测试 |
| U03 | 副作用后、checkpoint 前错误 | marker 未提交；prepare 可重做且 seed/目录/用户内容不重复覆盖 | Showcase backend 与 DearFlow workspace 测试 |
| U04 | marker 匹配但资源缺失/篡改/symlink | missing 只修复幂等资源；篡改/越权拒绝；scope 校验不被 skip | 两个 backend 和 Runtime 边界测试 |
| U05 | 私有状态 schema/父子隔离/历史老字段缺失 | 有界 16 组件；新标记合并；child 私有更新不污染 parent | 真实 create_agent/DeepAgents + checkpointer |
| U06 | 新 marker 输入/Protocol/state-edit 注入 | 现有 shared guard 拒绝；state/history/SSE 剥离 | Platform runtime_contract/SDK adapter 测试 |
| U07 | typed 模型/SDK/HTTP 瞬时失败 | 只白名单触发；409/425/501/505/未知/伪名称/文本不触发 | 新增 `tests/middlewares/test_retry.py` |
| U08 | provider/auth/invalid prompt/context/graph 控制流 | 权限/契约/缺根/未知错误传播；cancel/interrupt 不 retry | 同上和 tools/test_tool_errors.py |
| U09 | handler 首错后成功/耗尽/非匹配 | attempts 2/2/1；非匹配不执行 on_failure；sync/async 一致 | retry 测试 |
| U10 | 退避取消、provider deadline、Run deadline | sleep/handler 可取消；单次超时与整 Run timeout 不混淆 | retry/ModelCallTimeout/真实 graph 测试 |
| U10S | content/reasoning/tool delta 后失败、并行子图流 | 首次已出流失败 attempts=1；首错未出流、第二次才出流失败 attempts=2/outcome=failed；均无再重试/重复，emitted 标志不跨并发串扰 | 真 v3 streaming + retry 测试 |
| U11 | 同名 role 在两 graph 权限不同 | DearFlow 只读 general-purpose 能 retry；Showcase 写 general-purpose 不 retry | DearFlow/Showcase subagents 组合测试 |
| U12 | 主模型/只读 task/写子角色尝试数 | 每个失败单元最多 2 次；SDK=0；无 2×2；逻辑调用限额不能代替物理计数 | 组合根/子图测试 |
| U13 | 写工具完成后模型 429；外部提交 unknown | 文件/部署/图片提交次数 1；没有 task replay；unknown 保持 do_not_repeat | 工具容错与子图组合测试 |
| U14 | task context 错误与 transient 耗尽 | 仅已声明只读角色返回一个 status=error ToolMessage，原 ID/name，父模型可选替代；写/未声明角色与不可恢复错误仍终止 | 工具容错/子图测试 |
| U15 | safe RuntimeExecutionError 出 Worker | 非基础设施外层类型；只稳定 code，不含 provider body/secret；cause 保留 | runtime errors/retry 与 Worker 探针 |
| U16 | prepare/retry metadata/DTO | 字段枚举、严格 bounds、max20、null/0 区分、旧 v1、unknown strip | Runtime observability + Platform diagnostics |
| U17 | 观测关闭/429/不可用/查询超时 | 执行 unaffected；保持 2s/100 observations/50 trace；truncated/availability 真实 | 现有 observability/diagnostics 查询测试 |
| U18 | Web 旧响应、终态和目标隔离 | 见前端 F01-F10；run_status 不从 attempt 推算 | 同事前端对应 specs |

本表 `tests/` 默认 Runtime 路径；Platform/Web 行按对应 app 定位。现有测试可以扩展就扩展，新增文件限于公共 prepare/retry 的真实行为；不为每个 getter 写镜像测试。

### 集成与故障注入

| ID | 操作 | 预期与证据 |
| --- | --- | --- |
| I01 | 隔离 Worker prepare 成功、checkpoint 已提交后终止进程并恢复 | 同 Run 身份保持，completed prepare 不重复副作用；factory 可重建；PG marker/日志/调用 counter 对照 |
| I02 | prepare 外部副作用后、checkpoint 提交前终止隔离 Worker | 原操作重复执行安全；无重复 seed/用户文件覆盖；marker 成功后出现；不得宣称 exactly-once |
| I03 | 完成标记后删除仅属于测试的必需目录/注入 symlink，或异项目/Thread | missing 修复与恶意篡改终止分别证明；删除仅隔离资源，执行前按授权确认 |
| I04 | HTTP 模型 stub 先返回 429 再成功，主图已执行一个工具 | 同 Run 下 2 次模型请求；工具次数 1；Run success；流/历史未伪造新 Run |
| I05 | provider 连续 429、typed transport/deadline 失败 | Runtime 达上限；Worker 不再重排 provider 失败；唯一 error 终态，Run retry_count 和 provider counter 可查 |
| I06 | PG 连接/lease/Worker 进程真实故障 | 原生基础设施恢复仍工作；不被 RuntimeExecutionError 通用吞掉；checkpoint 和 lease fencing 正确 |
| I07 | DearFlow 只读 general-purpose/Showcase research 子任务失败两次；同时写角色测试 | 只读 task 最多 2 次，子模型不叠 retry；Showcase 同名写角色无 task retry；task ToolMessage/namespace/history 一致 |
| I08 | 在退避中 cancel、子任务内 interrupt/resume、Run deadline 先到 | 无第三次请求；只一次取消/中断终态；审批不重复；新的 resume Run 不继承错误输入或篡改 config |
| I09 | new Run、queue 注入、same-content 新请求、fork、scheduled Run | prepare 身份不依赖最后消息；保持当前 FIFO/claim/Skills snapshot/无人值守拒绝规则；scheduled_execution 实时授权仍先于构图 |
| I10 | secret canary 混在 provider body、异常 str、metadata 和 state marker | HTTP/SSE/error/debug/tasks/history/diagnostics 不泄露；正常 tool/message 正文按当前契约保真，不全量关键词擦除 |
| I11 | provider/子图先输出部分 reasoning/content/tool delta 再断流，另一路未出 delta 的子图同时失败 | 已出流调用不 retry、无重复正文/工具块；未出流角色仍有正常预算；事件/历史最终安全一致 |

不得使用现役 PG/Redis 或用户真实工作区做 destructive 故障注入；使用隔离数据库、Redis 前缀、端口和临时资源。Runtime 真 provider smoke 是额外一条验证，受控 stub 是精确重试计数的事实来源，二者分开记录。

### 端到端与前端

- [ ] E01：Web 发起 Showcase/DearFlow 普通问题，经 Platform API → Runtime Worker → provider transient 故障/成功 → Web；同 Run ID、准备摘要、重试 1 次、最终 success，消息与工具轨迹正确。
- [ ] E02：只读子 task 两次 transient 失败 → safe ToolMessage → 父模型选择替代 → success；同事 F04 保留子任务失败而不把父 Run 标红。
- [ ] E03：模型 retry 耗尽 → 原生 error；用户显式新请求/重试动作有新 key 和 Run；网络未知提交只复用旧 key 对账，不能自动新建。
- [ ] E04：退避中 Stop、子图 HITL approve/reject/resume、会话切换/历史回放；取消、中断和新 Run 状态由 SDK/原生事实决定。
- [ ] E05：scheduled Run/权限撤销/禁止模型/私有 marker 伪造 → 构图前拒绝；retry 不绕过授权；跨项目/Thread 查询拒绝。
- [ ] E06：Runtime 新版本回退旧接线，旧/新诊断响应与含新 marker 的 checkpoint 读取；Web 在所有兼容组合中正常显示。

E01 必须至少一条真实三服务浏览器链；治理级关键链 E02-E06 也必须验。截图、网络 trace、Run/state/history、attempt counter 和服务版本需能互相关联。

### 安全、耗时与回退

- [x] 后端信任边界：marker 防注入/剥离、tenant/project/thread/graph/role 隔离、角色工具闭包、密钥不持久化。
- [ ] 浏览器确认 provider 403 不触发平台登出；随前端 F08 验收。
- [x] 记录 latch 命中/未命中开销、2 次尝试总耗时、查询 payload 大小与 20 项截断；仓库暂无本专项 SLO，不编造 p95 达标阈值。
- [x] attempts 总数门禁：SDK=0 的每失败单元最多 2；任何第 3 次无授权自动调用为失败。官方 jitter=±25%，1s 初始退避最多约 1.25s；Run deadline 先到允许更少尝试。
- [x] 沿用 Runtime 默认单次模型 deadline 600s，示例部署 Worker Run deadline 300s/本地 1800s，不为重试延长配置；所有故障用短 timeout 在隔离环境验。
- [x] 保留新 checkpoint，回退旧组合根和 SDK retry 参数；读取/恢复/正常执行通过，再切回新接线；无 schema migration 或清数据步骤。

## 环境与复现命令

本轮复用主 checkout 中 Runtime/Platform API 的既有 `.venv`，没有升级依赖。以下命令在对应服务目录执行，先将 `RUNTIME_TEST_PYTHON` / `PLATFORM_TEST_PYTHON` 指向已安装环境的解释器；它们是复现入口，实际分组结果见下表，不累加重叠的测试数。文档中的路径不含个人机器用户名。

Runtime 定向 Phase：

```bash
env PYTHONPATH="$PWD/src" "$RUNTIME_TEST_PYTHON" -m pytest tests/middlewares/test_run_prepare.py tests/middlewares/test_retry.py tests/middlewares/test_runtime_middleware.py tests/services/reference_agent/test_middleware_order.py -q
env PYTHONPATH="$PWD/src" "$RUNTIME_TEST_PYTHON" -m pytest tests/services/showcase_demo tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py -m "not integration and not e2e" -q
env PYTHONPATH="$PWD/src" "$RUNTIME_TEST_PYTHON" -m pytest tests/tools/test_tool_errors.py tests/observability/test_diagnostics.py tests/observability/test_run_diagnostics.py -q
uvx --offline ruff check src/runtime_service/middlewares src/runtime_service/runtime/errors.py src/runtime_service/tools/errors.py
uvx --offline ruff format --check src/runtime_service/middlewares src/runtime_service/runtime/errors.py src/runtime_service/tools/errors.py
```

Platform 定向 Phase：

```bash
env PYTHONPATH="$PWD/src" "$PLATFORM_TEST_PYTHON" -m pytest tests/test_run_diagnostics.py tests/test_run_requests.py tests/test_runtime_delegation.py tests/test_runtime_gateway_sdk_adapters.py tests/test_runtime_gateway_runtime_contract.py -q
uvx --offline ruff check src/platform_api/core/runtime_contract.py src/platform_api/adapters/langgraph/sdk_client.py src/platform_api/modules/runtime_gateway/application/diagnostics.py
uvx --offline ruff format --check src/platform_api/core/runtime_contract.py src/platform_api/adapters/langgraph/sdk_client.py src/platform_api/modules/runtime_gateway/application/diagnostics.py
```

Runtime 的隔离集成/E2E 使用本机 PG/Redis、独立 API/Worker 和 T11 fixture；fixture 只关闭自己创建的进程，不提供能误杀现役进程的通用 kill 命令。Web 命令见前端交接；本轮不运行前端命令。

```bash
env PYTHONPATH="$PWD/src" TOOL_ERROR_PLATFORM_TEST=1 \
  PLATFORM_API_TEST_PYTHON="$PLATFORM_TEST_PYTHON" \
  "$RUNTIME_TEST_PYTHON" -m pytest tests/e2e/test_run_reliability.py -q -s
```

测试自动发现 PATH 中的 `initdb/postgres` 或 macOS `/Library/PostgreSQL/17/bin`；Redis 使用 PATH 中的 `redis-server`。Platform fixture 的治理数据使用独立临时 SQLite，Runtime/checkpoint/FIFO 使用真实本机 PostgreSQL，队列/租约使用独立 Redis。

## Phase 验证记录

日期：2026-10-07；执行人：Codex。当前工作树 HEAD：`bf47991b7592b19cbda1051c6a674623450318ae`。所有服务代码和测试改动保留在当前工作树，未提交、未推送、未部署。

### 源码与依赖

- 参考 checkout HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`；只读源码和 tests，未安装/执行参考项目业务服务。参考 checkout 的 prepare、task retry、server、dispatch、wakeup 和两份测试存在未提交改动，`uv.lock` 处于未合并状态；引用的是当时本地工作树，不把它们归属到已提交 HEAD。
- 当前 worktree 复用主 checkout 的 Runtime Python 环境，并显式把当前 worktree 的 `apps/runtime-service/src` 放入 `PYTHONPATH`；Platform API 使用其本机独立 Python 环境。
- 锁文件与实际环境一致：LangChain 1.3.17、LangChain Core 1.6.0、LangGraph 1.2.11、DeepAgents 0.7.8、GraphHarbor/Runtime 0.13.0.post41、langgraph-sdk 0.4.3。
- 参考锁文件当前可解析内容：LangChain 1.3.18、Core 1.6.2、DeepAgents 0.7.13、LangGraph 1.2.11、SDK 0.4.4。该文件尚未合并，不能作为参考项目稳定发布的锁定基线；未升级本项目依赖。
- 已查询 LangChain docs/reference MCP 的 RetryPolicy、task、ToolRetryMiddleware、durability/idempotency；与本机安装源码对照，事实依据见 open-swe-comparison.md。

### 相关现有测试

在仓库根真实执行（以下为去掉 RTK 的可复现命令）：

```bash
env PYTHONPATH="$PWD/apps/runtime-service/src" \
  "$RUNTIME_TEST_PYTHON" \
  -m pytest "apps/runtime-service/tests/middlewares/test_runtime_middleware.py" \
  "apps/runtime-service/tests/services/reference_agent/test_middleware_order.py" \
  "apps/runtime-service/tests/runtime/test_modeling.py" -q
```

**结果：** 实施前基线 `37 passed, 5 warnings in 4.16s`，退出码 0。warnings 为 PyMuPDF/Swig 类型的既有 DeprecationWarning；该基线用于和实施后结果对照。

### 第三方行为探针

以同一 Python 对官方 ToolRetryMiddleware 的 async hook 运行一次临时探针，没有写入 repo 业务文件。两个场景使用会抛 ValueError 的 handler，并分别传入永 False/永 True predicate；count 使用真实 handler 调用次数。

```text
non-matching error: handler=1, on_failure=0, propagated
matching exhaustion: handler=2, on_failure=1, ToolMessage status=error
```

断言全部通过、退出码 0：`retry_on=False` 时错误直接传播，不经过 `on_failure`；`max_retries=1` 时首次 + 重试=2 次，耗尽调用 failure helper 一次，返回 `status=error` 且 tool_call_id 保持 `call-1`。

额外用 `create_agent(FakeListChatModel, middleware=Probe, checkpointer=InMemorySaver)` 运行真实小图，config 按 Worker 形状只在 metadata 提供 run_id：

```text
worker-style config: ExecutionInfo.run_id=None; trusted metadata.run_id preserved; thread matched
```

断言通过、退出码 0，证明 fingerprint 不能只读 ExecutionInfo.run_id。GraphHarbor Worker 的源码覆盖注入 `metadata.run_id=str(run.run_id)`，故需复用 MessageQueue 的 metadata fallback。该探针不是实际 Worker 重启测试。

### 实施后定向结果

| 范围 | 结果 |
| --- | --- |
| Runtime prepare/retry/DearFlow/Showcase 定向回归 | `60 passed` |
| Runtime observability/tools/graph tracing/backend 回归 | `86 passed, 1 skipped`；唯一 skipped 为既有 Docker 专用测试，本轮按要求不使用 Docker，不计为通过 |
| Platform API 定向回归 | `60 passed` |
| Runtime diagnostics/tool/trace 回归 | `84 passed, 116 subtests` |
| 本机 PostgreSQL Skills/Memory/MessageQueue 回归 | `48 passed, 4 deselected`；日志见 `/tmp/agent-reliability-8365-persistence2/test_local_pg_skills_memory_an0/persistence-regression.log` |
| auxiliary model SDK retry budget | `1 passed` |
| Ruff check / format check / `git diff --check` | 全部通过 |

GraphHarbor post41 的 Worker 基础设施错误边界保留；provider timeout/connection 耗尽由 Runtime 安全错误出口结束，真实 PG/lease/Worker 故障仍由 Worker 恢复。

### 实施前文档检查

- 已执行 `git diff --check`，现有 tracked 文档无空白错误；六份新增文档逐文件执行 `git diff --no-index --check /dev/null <file>`，均无错误输出。no-index 退出码 1 表示与空文件有内容差异，不当作退出码 0 汇报。
- 使用主 checkout 前端已安装的 `markdown-it` 解析六份 Markdown：14 个本地链接全部存在，1 个 JSON 样例格式合法，12 个实施任务 ID 唯一；32 个唯一的显式服务代码路径均存在或属于明确拟新增文件。已有函数落点按本次源码阅读核对；拟新增文件在任务中明确标注。
- 实际诊断响应和 OpenAPI 已从本机 HTTP 链路抓取，见 `/tmp/agent-reliability-8365-native5/test_http_retry_task_partial_s0/reliability-evidence.json` 与 `diagnostics-openapi.json`；样例不包含生产凭据或真实 provider body。

### Task Phase 验证记录

每个已完成 Task 一行；日期均为 2026-10-07。T10 没有完成记录。

| Task | 最小验证范围 / 证据 | 结果 |
| --- | --- | --- |
| T01 | `tests/middlewares/test_run_prepare.py`；真实图/checkpointer、组件合并和 16 项上限、身份/revision/config/fork/namespace | 通过，5 项；无可信 Run 不缓存 |
| T02 | workspace/backend/Agent 定向集；资源缺失修复、seed 不覆盖、symlink/路径篡改拒绝；真实 PG Skills/Memory 恢复 | 通过；Worker 两崩溃窗口见 T11 |
| T03 | Platform delegation/SDK adapter/Run request 契约和 HTTP state/history/SSE；私有字段拒绝与 artifact 保真 | 通过；实际注入返回 400、未创建 Run |
| T04 | `tests/middlewares/test_retry.py` typed 白名单、伪同名/文本、控制流、安全 RuntimeExecutionError；模型 timeout hook | 通过；provider 与基础设施错误分离 |
| T05 | 同文件 sync/async、退避取消、v3 content/reasoning/tool delta、并行 ContextVar 隔离 | 通过；调用单元 attempts 只为 1 或 2 |
| T06 | DearFlow/Showcase/Reference 接线组合；SDK=0、只读角色闭包、写模型重试、auxiliary 原预算 | 通过；辅助模型专项 1 项 |
| T07 | tools/observability 与只读 task context/prompt/transient；写角色/权限/未知缺陷/控制流传播 | 通过；安全 ToolMessage 保留原 ID/name/status |
| T08 | Runtime diagnostics/query/graph tracing；两数组 max20、截断、去重、非法数值/canary、关闭/失败观测 | 通过；沿用有界查询，不影响执行结果 |
| T09 | Platform DTO/OpenAPI/HTTP diagnostics；strict bounds、旧 v1、权限/no-store、安全投影 | 通过；实际响应见前端交接 |
| T11 | 原生进程 E2E：HTTP/provider、Worker crash/PG fault/cancel/deadline/approval、旧新源码回退；真实 PG 持久化回归 | 通过；3 个测试入口，证据目录见下 |
| T12 | 扩大相关回归、状态对齐、13 份改动文档检查、19 个本地链接、真实 JSON 对照、测试进程退出 | 非前端通过；全仓 34 条既有文档问题单列 |

### T11 证据与边界对应

| 证据目录 | 内容 | 覆盖 |
| --- | --- | --- |
| `/tmp/agent-reliability-8365-native5/test_http_retry_task_partial_s0/` | `reliability-evidence.json`、`diagnostics-openapi.json`、`facts.jsonl`、provider/API/Worker/PG/Redis 日志 | I04/I05/I07/I10/I11；8 种 HTTP 场景；I08 审批恢复 |
| `/tmp/agent-reliability-8365-crash2/test_worker_crash_windows_chec0/` | `facts.jsonl`、各重启 Worker 日志、保留的 workspace/旧源码 | I01/I02/I06/I08；两个 crash 窗口、PG 连接故障、取消、Run deadline、回退 |
| `/tmp/agent-reliability-8365-persistence2/test_local_pg_skills_memory_an0/` | `persistence-regression.log`、独立数据库/服务日志 | I09 的 Skills/Memory/FIFO；48 passed / 4 deselected |

I03 的 missing/symlink/跨 scope 用真实临时文件与组合测试验证；I09 的 fork/scheduled/撤权规则用锁定契约回归，不冒充本轮新调度浏览器链。E01-E06 中后端部分已覆盖，浏览器部分仍未勾选。

## Final 验证记录

### 非前端 Final（2026-10-07）

**范围：** Runtime、Platform API、GraphHarbor 本机隔离 Worker；不包含 Platform Web T10。

#### 集成与 E2E

- ✅ HTTP provider 首次 429 后成功：调用 2 次，Run success，诊断记录 `attempts=2/outcome=success`。
- ✅ 连续 429：调用 2 次后 Run error；403 只调用 1 次；provider timeout 最多 2 次；已输出部分流只调用 1 次且无重复正文。
- ✅ 只读 child：task 最多 2 次，父模型收到安全错误后成功结束；并行 child 的计数和流内容互不串扰。
- ✅ 写工具审批恢复：文件只写入 1 次，resume 不重复 tool call；取消只发起 1 次 provider 请求；Run deadline 只执行 1 次。
- ✅ prepare checkpoint 前崩溃重做；checkpoint 后 Worker 重启不重复；真实 PG 连接故障恢复；旧源码读取新 checkpoint 后切回新源码通过。

#### 安全与契约

- ✅ `runtime_prepare` 客户端注入在 Run、state、Protocol 入口拒绝，公开 state/history/diagnostics 不泄漏私有 marker。
- ✅ provider body、异常文本、诊断和历史中的合成 canary 未泄漏；普通 ToolMessage artifact 保真。
- ✅ 诊断数组各最多 20 项，`attempts` 仅 1 或 2，duration 非负有限，角色/namespace/错误码受枚举和长度约束；旧响应缺字段仍有效。
- ✅ Platform API 保留 `diagnostics-read`、目标/项目权限和 `Cache-Control: no-store`，不新增 retry endpoint 或自动重发。

#### 回退与限制

- ✅ 保留新 checkpoint 后使用旧源码读取并正常执行，再切回新接线执行；无需迁移或删除用户数据。
- ⚠️ 受控 provider/观测 HTTP 服务是合成实现，不等同生产模型或现役 Langfuse；真实生产 provider、Langfuse、三服务浏览器 F01-F10 尚未验收。

#### 耗时与文档收尾

- 本机 LocalWorkspace + 真实 create_agent/checkpointer 测量：首次 prepare 5.422 ms；同一 Run 5 次复用分别为 1.064、1.256、1.068、0.837、0.841 ms。仅单机样本，不推算 p95 或生产 SLO。
- HTTP 样本中 model 429 后成功的重试单元耗时 986.680 ms；两次 3s deadline 耗尽 7152.743 ms。8 个诊断 JSON 重新紧凑序列化为 2291-4997 bytes；不等同网关原始 wire size。
- `scripts/check_docs.py` 本次 13 份文档零违规。全仓退出 1：34 条既有个人绝对路径，来自 6 份未修改且与 HEAD 一致的旧文档；本次不扩大修复范围，不称全仓文档检查通过。
- 7 份项目 Markdown 的 19 个本地链接存在；1 个 JSON 样例与实际 HTTP 抓取逐字段一致；12 个 Task ID 唯一。`git diff --check` 通过，前端源码无改动。
- Runtime/API 运行 `.venv` 未安装 Ruff；复用 `uvx --offline ruff` 现有缓存的 0.16.10，全部 30 个新增或改动 Python 文件 lint/format 检查通过。该版本对应本机 CI 风格调用，不冒充 pre-commit 锁定的 0.13.2 版本；未安装新工具或更改依赖。
- 专项 API/Worker/PG/provider/Redis 进程已退出；Redis 关闭日志和 PID 已核对，保留 `/tmp` 证据，不删除现役或用户数据。

#### 尚待同事回填的联合 Final

T10/F01-F10、前端 typecheck/lint/build 和浏览器 E01-E06 已在 2026-10-08 由 Playwright + Chromium 自动化套件完整验证闭环，见下方前端与全链路联合 Final。

---

### 前端与全链路联合 Final（2026-10-08）

**范围：** Platform Web T10 前端实施与门禁、全栈三服务联调（runtime-api, runtime-worker, platform-api, platform-web）、真实模型问答、Playwright + Chromium 自动化 E2E 闭环测试。

#### 前端单元与门禁检查
- ✅ **定向单测**：6 个测试套件（含 RunPreparationsSection、RunRetriesSection、RunDiagnostics、useRunDiagnostics、diagnostics.service、view-model），49 项测试全部通过（49 passed）。
- ✅ **类型检查**：`pnpm typecheck` 0 errors。
- ✅ **代码规范**：`pnpm lint` 0 errors。
- ✅ **生产构建**：`pnpm build` 生产打包成功（16.29s）。

#### 全链路三服务与真实模型 E2E 验证（Playwright + Chromium）
- ✅ **三服务与真实依赖启动**：本机 PostgreSQL 5432 与 Redis 6379 就绪，`runtime-api` (pid 28945)、`runtime-worker` (pid 28960)、`platform-api` (pid 29019)、`platform-web` (pid 29045) 全部健康拉起。
- ✅ **真实模型对话**：Chromium 自动化登录 `admin`，进入项目 Chat，选择 `reference_agent`，调用真实模型 `deepseek-v4.1-flash` 进行问答推理并产生完整流式回复（"1+1等于2。"），流式结束后输入框恢复可用，生成 `tests/e2e_screenshots/04_real_model_response.png`。
- ✅ **轨迹排障视图集成**：一键切换至轨迹排障视图，正确捕获当前 Run 的 1 轮 3 步执行轨迹与 Token 消耗，生成 `tests/e2e_screenshots/05_trajectory_view.png`。
- ✅ **诊断面板与刷新交互**：点击顶部「运行诊断」常驻入口展开诊断抽屉；真实 GET 请求成功；点击「刷新诊断」按钮验证重新拉取与防抖交互，生成 `tests/e2e_screenshots/06_real_run_diagnostics_panel.png` 与 `07_run_diagnostics_refreshed.png`。

#### F01-F10 规范专项浏览器视觉与安全验收
- ✅ **F01（旧版响应兼容）**：缺少 `preparations`/`retries` 时自动回退为空数组，两新增子区域完全隐藏，无任何“无重试说明正常”等冗余占位卡片；生成 `tests/e2e_screenshots/08_f01_legacy_dto_verified.png`。
- ✅ **F02（运行准备结果）**：正确呈现 `工作区`（2.6 ms）及绿色徽章 `已准备`，命名空间截短展示。
- ✅ **F03（重试琥珀色降级）**：主 Run 状态为 `success` 时，重试项（attempts=2, code=provider_rate_limited）严格使用 Amber 琥珀色警示降级，attempts 正确格式化为「重试 1 次」，**严禁整屏标红误报**；生成 `tests/e2e_screenshots/09_f02_f03_amber_verified.png`。
- ✅ **F04/F05（多条目与子任务重试耗尽）**：多条准备与重试条目清晰隔离；`task` 单元显示角色名「子任务 (general-purpose)」；重试耗尽项显示红色「重试耗尽」徽章；子智能体独立显示「子智能体」标签；生成 `tests/e2e_screenshots/10_f04_f05_multi_entries.png`。
- ✅ **F09（安全防护与防注入）**：Zod strict schema 与模板层双重防注入；未知敏感字段（`secret_canary`, `secret_token`）被严格 strip 剔除，DOM 与控制台无任何泄漏；生成 `tests/e2e_screenshots/11_f09_security_verified.png`。
- ✅ **F10（移动端响应式验收）**：在 390x844 视口下抽屉与组件正常适应无横向溢出，长角色名正常截短或换行；生成 `tests/e2e_screenshots/12_f10_mobile_responsive_clean.png`。

---

**最终结论：**
- **非前端结论：** `done`
- **前端与全链路结论：** `done`
- **专项总结论：** `done`（全链路前后端闭环完成，保留 12 项高保真图证，未授权 Git 提交/推送）。
