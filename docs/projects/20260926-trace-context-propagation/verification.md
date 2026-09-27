# 跨服务链路追踪 - 验收与验证记录

## 当前状态

T1—T8 已实施。本期按已批准的新 API/当前 Runtime 组合验收；Phase 与 Final 分开记录。用户确认性能只记录实测数据，不设置临时 SLO。

## 自动化验收矩阵

| 编号 | 输入/场景 | 必须断言 |
|---|---|---|
| V01 | 普通、超长、恶意 x-request-id/x-trace-id；W3C 关联头 | 内部仍为新生成 32 位小写十六进制；不回显/记录外部原值，不以 W3C 头建立关联 |
| V02 | 成功、401/403、422、安全 500、SSE 握手 | 进入应用编号范围的响应头/错误正文/context 一致；代理提前拒绝及 CORS 直接预检除外；浏览器能读取两头 |
| V03 | 并发项目请求、普通异常、CancelledError、流迭代 | 无串号，后请求不继承旧上下文；取消继续传播；token 创建/重置同任务 |
| V04 | 网关初始 read、scoped run/审批/取消；Catalog 独立签发 | 解码 JWT 两字段与当前请求一致，Runtime 现有校验通过；内部转发头一致；每请求闭包独立 |
| V05 | 无 HTTP 上下文的 Catalog、build_forward_headers 各调用方 | 非 HTTP 调用无伪造关联；仅外部头时不向下游回退使用；当前调用方可正常运行 |
| V06 | 幂等提交重试、reserve 冲突及失败 | request_id 不同、submission_id 相同、无额外 Run；reserve 前无虚假关系或派发事件 |
| V07 | 首请求超时/响应丢失后重试；接受后 mark 失败；复用详情读取失败 | unknown 不等于未执行；已知 Run 不抹除；保存全部尝试；不武断把首请求当执行来源；命令摘要/context_hash 不变 |
| V08 | 单/多 interrupt 审批恢复 | 实际 Run/parent_run_id/interrupt_key 准确，不改审批权限及恢复语义 |
| V09 | 取消 ACK、拒绝、超时 | 目标 Run 与 accepted/rejected/unknown 准确；ACK 不宣告 Run 已取消 |
| V10 | 新 metadata 与精确组合查询 | 两白名单均通过；新生成request_id可查；run_id三字段OR，参数间AND；total与列表一致 |
| V11 | 相同编号/Run 出现在不同项目、无项目权限身份、仅提供编号 | 授权项目过滤和关联过滤共同生效；无跨项目数据或计数泄露 |
| V12 | 缺单边时间、反向区间、恰好/超过 7 天、时区混合、非法 UUID/控制字符/长度 | 按 plan 第 8 节验证，非法公开 422，恰好 7 天允许，request_id 单独查不强制窗口 |
| V13 | 握手失败、start 发送失败、正常 EOF、空流 | 失败无 opened；成功 start 才打开；已打开连接最多一条 closed |
| V14 | 断连、上游异常、坏帧、主动关闭、未知取消、重复清理、线程跨 Run | 六种原因分类准确；frame_rejected 不被 finally 覆盖；不解析正文、不隐式取消、不固定线程流 Run；已发 200 不改记 499/500 |
| V15 | 日志抛错、metadata 合并失败、审计 DB 写入失败 | 两个观察动作尽量独立；原业务结果不变；不重发、不吞取消、不泄露原文；既有 HTTP 审计不增加独立派发行 |

测试优先扩展已有 unittest/项目测试，避免重复建框架；必要时集中新增：

- apps/platform-api/tests/test_request_correlation.py（V01—V03）
- apps/platform-api/tests/test_runtime_correlation.py（V04—V09、V13—V15）
- apps/platform-api/tests/test_audit_correlation.py（V10—V12、V15）

`test_request_correlation.py`、`test_audit_correlation.py` 已创建；其他场景沿既有测试文件扩展，未创建重复测试框架。

## Phase 自动化执行入口

从仓库根目录、已安装锁定依赖的 API 测试环境运行；仅使用隔离测试数据。以下既有用例必须回归：

```bash
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_catalog_delegation.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_run_requests.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_audit_http_resolution.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_cors_middleware_order.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_core_error_handling.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_gateway_event_redaction.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_gateway_sdk_adapters.py"
```

新测试创建后按各自文件运行 unittest discover；SQLite 与 PostgreSQL 要实际执行相同 repository 过滤用例，不能仅比较 SQL 编译字符串。PG 只用现成隔离测试库/已有 schema，不执行本专项 DDL；记录驱动、DB 版本和测试数据量。

Final 运行 API 现有完整测试、项目既有 lint/类型门禁及相关 Web 错误消费/CORS 验证；不得为跑验证擅自启动带迁移的 local-stack start。环境准备参考[本地开发](../../quickstart/local-dev.md)，启动/部署须另有授权，本轮不执行。

## 真实链路验收

前提：已有可用平台测试环境、授权测试用户/项目、既有 Runtime worker、已启用并成功导出的现有观测。记录 API/Runtime/GraphHarbor 版本及 worker 身份、观测导出状态；不保存 token、密钥、模型输出或工具参数。至少两个隔离项目用于权限检查。

| 编号 | 操作 | 证据与通过条件 |
|---|---|---|
| R1 | 通过平台真实提交，并保留响应头；使用同一幂等键重试 | 两次请求编号不同；审计 request_id 查询分别返回同一 submission/thread/run；不重复创建 Run |
| R2 | 在既有 Runtime worker 确认该 Run 实际执行 | 记录真实 worker/Run 对应证据，不能用直接调用 Runtime 或 mock 代替平台链路 |
| R3 | 从已导出的观测找对应 Run | 受信 request_id/platform_trace_id 与实际执行来源一致；观测记录定位信息可复核，不凭相近时间推断 |
| R4 | GET /api/audit 以 submission_id + created_from/created_to 查询 | 查到同提交全部已记录尝试；允许 unknown，明确不保证进程崩溃时记录完整 |
| R5 | 真实审批与取消请求；以 run_id 反查 | run_id/target_run_id/parent_run_id 命中关联请求；当前身份权限仍生效；取消 ACK 与实际终态分别取证 |
| R6 | SSE 断开并重连，线程流跨 Run | 新连接新 request_id，原 Run 正常延续；打开/关闭及原因正确，无隐式取消或持久绑定错误 Run |

精确查询示例（通过既有登录态/认证方式调用，不在证据中保存凭据）：

```text
GET /api/audit?project_id=<authorized-project>&request_id=<response-request-id>
GET /api/audit?project_id=<authorized-project>&submission_id=<uuid>&created_from=<ISO8601>&created_to=<ISO8601>
GET /api/audit?project_id=<authorized-project>&run_id=<actual-run>&created_from=<ISO8601>&created_to=<ISO8601>
```

缺真实环境、权限、worker 或观测导出条件时写“未验证”及具体阻塞；mock 通过不能替代 R1—R6。

## 性能门禁

- 在隔离 SQLite/PG 数据中覆盖代表性 7 天窗口和跨项目数据量，记录数据规模、查询计划及延迟分布。2026-09-27 用户确认本期仅留实测数据、不做 SLO 达标判定。
- 关联查询无索引若不达标，另行评审索引方案，本专项不执行 DDL。不得以去掉授权/时间过滤换取性能。
- 新API与当前Runtime组合验证已接受Run仍可执行、后续现有操作正常且没有额外重发/重签；Runtime/GraphHarbor不变，无数据库变更。不测试旧API产物或历史审计格式。

## Phase 验证记录

### 2026-09-27 T1—T8 阶段补验

| Task | 执行与结果 | 限制 |
|---|---|---|
| T1 | `test_request_correlation.py` 2项通过；12条并发请求及后请求均有独立内部编号；取消传播后 ContextVar 无残留。安全 500/CORS 由现有错误契约与全量测试覆盖 | 代理提前拒绝不在应用编号范围 |
| T2 | `test_runtime_delegation.py`、`test_runtime_delegation_contract.py` 与完整 API 回归通过；当前请求的初始/scoped claim 和转发头同号 | 不改变 JWT operation/TTL |
| T3 | `test_runtime_catalog_delegation.py` 与 SDK 调用方回归通过；非 HTTP 路径不生成虚假编号 | Runtime/GraphHarbor 不改 |
| T4 | `test_run_requests.py` 27项通过；重试同 submission、mark 失败后同幂等键、审批 parent/interrupt、取消 ACK/拒绝/unknown及观察失败均有断言。现役旧隔离 Run 的审批/取消可按 run_id 精确反查 | ACK 不等于取消终态 |
| T5 | `RUN_LOCAL_TRACE_POSTGRES=1` 执行 `test_audit_correlation.py` 6项通过；SQLite/PG 用同一过滤断言，PG 事务回滚；白名单、控制字符/窗口/UUID 422及项目审计权限通过。`test_audit_stream_status.py` 2项通过：已发200保持200、审计写入失败不改变响应 | 不新增索引/迁移 |
| T6 | `test_runtime_gateway_event_redaction.py` 12项通过；握手 start 失败无 opened、坏帧优先、EOF/空流、主动关闭、异常、确认断连、未知取消及单次 closed；日志观察失败不改变流内容。现役执行中 Run 的线程流断开重连200且不固定 Run | 一次502发生在测试编辑触发的 API 热重载期间，不计业务样本 |
| T7 | `PLATFORM_ERROR_CONTRACT_REAL=1` 真实测试2项通过；R1—R4、R6同一隔离项目实测；R5通过现役旧隔离审批/取消记录的授权 API 反查。PG 17.11/SQLite 3.50.4 的性能数据见下 | 当前 Runtime 终态清除 `lease_owner`，worker 身份须结合进程和 heartbeat 复核 |
| T8 | 实施记录、任务与总览状态已同步；文档检查和最终工作树核对见 Final | 不执行 Git 提交或部署 |

**真实性能样本：** PG 既有 `audit_logs` 112135 行，request_id 30次中位 0.577 ms / p95 1.105 ms，计划使用 `ix_audit_logs_request_id`；项目+7天+run 三字段 OR 查询中位 1.276 ms / p95 1.834 ms，使用 `ix_audit_logs_project_id` 后 JSON 过滤。SQLite 内存 10000 行、20项目、run 值1000种，同类查询30次中位 2.442 ms / p95 7.911 ms，计划使用项目索引并为排序建临时 B-tree。无批准 SLO，不宣称达标；测试数据未写入业务库，PG 过滤测试事务已回滚。

**真实链路定位：** 2026-09-27 平台两次请求 `0b9c86fa5de14900a68e577d9f62eb27`、`6d392f8c39964201a710de02cc225ecc` 映射 submission `8c52c864-0860-43fc-bdcd-0cbad4950895`、Run `c786612f-f9b0-4810-863b-6251992bd823`；PG 审计按编号及 submission+窗口均返回对应尝试。Runtime 持久 Run 状态 `success`、有 heartbeat；验证时本地唯一 worker launcher PID 38768、子 Python PID 38784 存活；Langfuse trace `77cf961ec70884670c0c38e9c2712422` 的可信 metadata 匹配 Run 和提交请求。无编辑干扰的 R6 复测中，第二个 Run `45aeec01-77cc-46d6-87a1-e24325c97738` 在断流重连后成功；线程流请求号 `2b2fb0bf212c41b5aaa0cb22d2836a25`、`b5e3877dc74a45df835210ba75692e19` 各有一条 opened/closed，原因 `client_disconnect` 且无固定 Run ID。项目 executor 用相同 request_id 查审计返回403。真实测试创建的隔离 Thread/项目已由测试清理。

**R5 现役旧隔离样本：** 已有授权测试项目 `5a5b7239-43e3-40e6-bba3-e64d96057607` 的真实取消 Run `6d106bc9-97e0-41df-afb8-8169142a90bb`，`GET /api/audit?run_id=...` 返回创建与取消两行，取消行含 `target_run_id`、`operation=run-cancel`、`outcome=accepted`；审批恢复 Run `0561a389-515f-4385-a7c8-70d617ca8cbe` 返回 `parent_run_id=ce7adb5c-8264-4a9c-a252-15c84ba76664`、真实 `interrupt_key`、`operation=approve`。本轮仅只读反查，没有撤权或修改旧样本。

### 2026-09-27 SSE 编号回调交叉验证

- 错误响应专项的 `test_runtime_gateway_event_redaction.py` 8项通过：成功发送 start 后才记 opened；发送 start 失败无 opened；坏帧 closed 原因 `frame_rejected`。本地真实 Run SSE 返回200及数据帧，平台日志 `runtime.stream.opened/closed` 同时含响应 `x-request-id=44c9d72acb084483a3c7b09c3283dbce`、实际 Run ID `e3d5e635-e57b-4c97-89ef-5e5ddef4c050`。
- 同一真实栈的两个提交请求编号经平台审计指向同一 submission/Run，Langfuse trace `556f410a54c5eb54450e0a6629a4e821` 含匹配的可信请求 metadata；仅证明这一条 R1—R3 正向路径，不替代 worker 身份、审批/取消/重连、PostgreSQL 和性能完整验收。详情见[错误响应 Phase 证据](../20260926-error-response-contract/verification.md)。

### 2026-09-26 API 基础实现

- `test_cors_middleware_order.py` 1项、`test_security_boundaries.py` 5项：通过；内部请求号不接受外部关联头，CORS暴露编号头。
- `test_runtime_delegation.py` 18项、`test_runtime_catalog_delegation.py` 15项：通过；Gateway/Catalog阶段签发关联与Catalog凭据行为。
- `test_run_requests.py` 26项：通过；提交回调的accepted/deduplicated/unknown及观察失败不重发。
- `test_audit_http_resolution.py` 9项、`test_audit_correlation.py` 3项：通过；SQLite JSON过滤、项目条件、7天窗口与HTTP 422。
- `test_audit_stream_status.py` 1项：通过；已发HTTP 200的审计状态不改记500。审计迭代器未必观察到上游最终异常，结果/关闭原因仍待SSE统一路径验证。
- `test_runtime_gateway_sdk_adapters.py` 19项：通过。未运行PostgreSQL、并发取消全矩阵、SSE关闭、真实worker/观测或性能验收；V01—V15不能据此整体勾选。

### 2026-09-26 文档与静态核查

- 已核对当前工作树：Catalog service/test、Runtime memory/test、smoke/stream 脚本等既有修改保留。
- 已重新静态核对内部编号、委托入口、reserve/mark、两处审计白名单及实际流/审计关闭路径。
- 发现并纳入 T5：现有 audited_body_iterator 在取消/异常时改写状态为 499/500；目标为保留已发送状态。
- 文档检查：python3 scripts/check_docs.py、git diff --check 均通过（退出码0）；四份追踪文档的结构、T1—T8全未勾选和相对链接已检查。6份既有非文档工作区文件按SHA-256复核保持不变。
- 链接检查范围限制：docs/FEATURES.md 原有“切线程澄清”记录指向 apps/platform-web/docs/changes/20260923-fix-zombie-clarification-on-thread-switch.md，缺少相对docs目录的上级前缀。本轮新增/修改链接均有效；该无关旧链接未修改，不能宣称FEATURES全页链接全通过。
- 业务自动化/集成/真实链路/性能：均未执行。无Runtime worker或导出通过证据；旧版本回退门禁已取消。

后续每个 Phase 单独记录日期、任务、命令、环境、退出码、证据及限制；不得写进 Final 充数。

## Final 验收记录

### 2026-09-27 Final

**完成度：`done`（本期已批准的新 API/当前 Runtime 组合）。** T1—T8 均为 `[x]`，README、plan、tasks、verification、CONTEXT 和 FEATURES 的本期状态一致。无生产部署或 Git 提交由本次验收执行。

| 验收项 | 最终证据 |
|---|---|
| V01—V03 | 12条并发、恶意外部编号、取消传播及后请求 ContextVar 隔离；安全 500/CORS 及 HTTP/SSE 同编号由现有错误响应契约和真实测试覆盖 |
| V04—V05 | Gateway 初始/scoped、Catalog 独立签发及转发调用方由既有委托/双端契约和 API 全量测试覆盖；非 HTTP 调用无虚假编号 |
| V06—V09 | 幂等重试、unknown、mark 失败、单/多 interrupt 审批关系、取消三种结果由 `test_run_requests.py` 及真实审计反查覆盖；没有新增 Run 或将 ACK 当终态 |
| V10—V12 | 写/读双白名单、SQLite/PG 实际 JSON 查询、项目过滤与 total、权限403、请求422、七天边界和 Unicode Cc 拒绝通过 |
| V13—V15 | SSE start 失败、EOF/空流、坏帧、上游异常、确认断连、未知取消及单次 closed 通过；真实两次线程流关闭为 client_disconnect；已发200审计状态及观察回调失败回归通过 |

| 真实场景 | 最终证据 |
|---|---|
| R1 | 两个不同 request_id 对应同一 submission/Run；同一幂等键无额外 Run；审计按两个编号和 submission+时间窗均能查回 |
| R2 | Runtime 持久 Run `c786612f-f9b0-4810-863b-6251992bd823` 为 success、含 heartbeat；本机唯一 worker launcher PID 38768/子进程38784在测试时存活，实际执行与本机 worker 组合核对 |
| R3 | Langfuse 导出 trace `77cf961ec70884670c0c38e9c2712422`，可信 metadata 的 Run 与 request_id 匹配，非时间近似推断 |
| R4 | `GET /api/audit` 带 `submission_id`、`created_from/to` 返回两次已记录尝试；unknown 可保留，不保证崩溃场景完整 |
| R5 | 现役旧隔离审批/取消真实记录通过授权 API 用 `run_id` 反查；恢复关系含 parent/interrupt，取消含 target/outcome；新隔离项目 executor 同编号查询403 |
| R6 | 两次线程流断连重连各有新编号与 opened/closed，均 `client_disconnect`，日志不固定 Run；第二个 Run 执行中立即重连200，断流后该 Run 成功且无隐式取消 |

**自动化与质量：** 最后一次完整 API `pytest -q tests` 为 307 passed、16 skipped、613 subtests passed，退出码0；其后只新增两个测试，已分别在 SSE 定向12项与审计状态定向2项中通过，本机 PG 定向6项、并发/取消2项也通过。Runtime 两个鉴权文件47项通过；Web 相关 Vitest 11项通过。新增测试完整 Ruff 与格式检查通过；相关 Python 文件 `E4,E7,E9,F`、`python3 scripts/check_docs.py`、本专项范围 `git diff --check` 均退出码0。全量测试的16个 skip按既有条件保留，不计为通过；测试密钥长度警告和 WebSocket 弃用警告不属于本专项失败。

**性能：** PG 17.11 既有112135行，request_id 中位/p95 为0.577/1.105 ms，项目+7天+run关联为1.276/1.834 ms；SQLite 3.50.4 隔离内存10000行为2.442/7.911 ms。均为30次本机样本，查询计划见 Phase。用户已确认本期只记录数据，没有已批准SLO，故不做“达标”判断；不据此引入索引或执行DDL。

**边界和问题：** 一次执行中订阅的502与 WatchFiles 因测试文件编辑触发的平台 API 热重载同窗；停止编辑后相同场景重跑200、Run 成功，该502不计业务缺陷。终态会清除 Runtime `lease_owner`，R2 的 worker 身份靠本机单 worker 进程、Run heartbeat/终态及导出共同核对，没有永久 worker ID 行。观测关闭、进程崩溃、生产容量和旧版本混用不在已批准本期闭环保证内。Runtime/GraphHarbor 源码、配置、依赖和数据库结构未因追踪修改；没有迁移、生产部署或本次验收发起的 Git 提交。
