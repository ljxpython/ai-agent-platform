# 平台助手后端配置与复验

## 1. 实现位置与复用关系

用户请求先经 Platform API 登录和项目授权，原生 Thread/Run 网关把可信身份、模型和预算交给 Runtime。Runtime 的一个 create_agent 按需调用工具；内部读取经带用途和时间戳的 HMAC 回调返回 Platform API，再用独立只读连接、资料发布目录或已有诊断接口取数。工具结果进入原生会话，证据授权回执进入 API 数据库，审计只保存关联和查询指纹。

| 位置（相对仓库根） | 职责 |
|---|---|
| `apps/runtime-service/src/runtime_service/graphs/platform_assistant.py` | 图入口，三个 langgraph 配置注册 |
| `apps/runtime-service/src/runtime_service/services/platform_assistant/agent.py` | create_agent组合根；复用身份、模型、隐私、预算、超时、追踪及消息队列 |
| 同目录 `tools.py` | SQLDatabase适配、信息/查询工具、日志/资料/公开搜索；不持有业务数据库密码 |
| 同目录 `approval.py` | 显式 business_write_tools 强制 HumanInTheLoopMiddleware |
| `apps/runtime-service/src/runtime_service/tools/research.py` | 从既有DearFlow提取的共享公开检索传输，旧调用者继续复用 |
| `apps/platform-api/src/platform_api/modules/platform_assistant/` | bootstrap、权限、数据库、日志、资料、回执与内部路由 |
| `modules/runtime_gateway/application/service.py` | 历史访问校验、列表过滤、禁止助手fork，其他会话沿原协议 |
| `modules/observability/router.py` | 旧日志URL复用新授权边界 |
| `migrations/versions/20261116_0012_assistant_evidence.py` | 授权回执表，非第二套会话或审批存储 |

没有新增服务、DeepAgents、子Agent、shell、助手Workspace或执行沙箱；GraphHarbor负责持久checkpoint。平台自身会话/审计持久化是系统写入，不是授予模型业务数据库写权限。

SQL复用锁定的 langchain-community SQLDatabase、InfoSQLDatabaseTool 和 QuerySQLDatabaseTool，执行端适配平台授权。没有直接暴露上游不受控SQL连接，也没有为每个业务问题写固定SQL。API仅新增sqlglot依赖做语法树校验；社区包存在上游弃用警告，本期保留锁定依赖，不扩展为依赖迁移项目。

## 2. 本地启动和启用

先读 [Worktree规范](../../standards/worktree-development.md)，只用当前目录的 local-stack；禁止回退主工作区数据库、依赖或端口。

```bash
bash "scripts/local-stack.sh" init
bash "scripts/local-stack.sh" deps
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" start
```

已有环境直接按规范管理对应服务。使用当前 Worktree 的 `.local-stack/platform.env` 配置 `PLATFORM_API_PLATFORM_ASSISTANT_ENABLED=true`。默认 false，不会因代码部署自动开放助手。local-stack 启动API会执行所属库迁移；其他环境按既有发布迁移流程升级至 `20261116_0012`，不要用 create_all 替代生产迁移。

Runtime需同步图目录，`platform_assistant` ready；项目存在启用的受管模型。沿既有配置提供 Runtime→Platform 模型回调地址 `PLATFORM_RUNTIME_MODEL_CONFIG_URL` 和 `PLATFORM_RUNTIME_DELEGATION_SECRET`。助手内部读取从同一回调Origin派生固定路径，不另配置任意模型可控URL。密钥不进入前端、文档、工具输入或Git。

配置后按需：

```bash
bash "scripts/local-stack.sh" restart-one platform-api
bash "scripts/local-stack.sh" restart-one runtime-api
bash "scripts/local-stack.sh" restart-one runtime-worker
```

初始化时 bootstrap 返回图目录不可用或模型不可用则先修配置，不在助手中绕过启用策略。个人助手项目只允许执行本助手，其他业务项目权限不会被自动授予。

## 3. 全部获准数据库的接入

用户批准全部已接入且当前用户有权读取的数据，不限制几个固定查询。本期执行适配是 **PostgreSQL**；多个数据库/多个schema配置多个数据源。MySQL、Oracle等未实现连接适配，不能把“数据范围全部开放”写成“所有引擎均已支持”。

`PLATFORM_API_ASSISTANT_DATABASES` 为JSON对象。示意值（不可直接照抄密码或UUID）：

```json
{
  "business-reporting": {
    "dsn": "postgresql://assistant_ro:<由密钥管理注入>@db.internal:5432/business",
    "project_id": "<业务项目UUID>",
    "schema_name": "assistant_data",
    "tables": [],
    "project_roles": ["project_admin", "project_editor", "project_executor"],
    "user_ids": [],
    "revision": "reporting-v1"
  }
}
```

- `tables=[]`：发现该只读账号在指定schema内所有获准表/视图，不是开放平台管理员账号的全部权限。也可列出特定表。
- project_roles / user_ids 至少命中一项；仍须当前有效项目成员。多个项目可分别映射各自只读视图/账号，避免把同一全集连接随意分配给普通成员。
- 第一版配置schema和表名采用小写字母、数字、下划线，schema及表名最多63字符；数据库管理员可用规范命名的只读视图适配已有异形名称。
- 每次连接检查：非superuser、无createdb/createrole/replication/bypassrls/角色成员资格，schema无CREATE，可读表无INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER。
- SQL事务强制READ ONLY，search_path固定pg_catalog；AST将真实表限定到获准schema，CTE按词法作用域识别。禁止多语句、写CTE、DDL、INTO、锁、角色切换、跨schema和不支持的函数。支持SELECT/集合操作、过滤、JOIN、聚合、常用窗口和日期函数；不是任意PostgreSQL管理语言执行器。
- 行/列范围由数据库RLS或经审核的只读视图定义；视图和自定义类型由管理员负责审查，不用模型写WHERE来承担权限隔离。
- 改变数据范围、行列策略或资料可见语义时必须同步升级revision；移除数据源/用户授权及revision变化会阻断引用过旧资料的历史。数据库外部权限变化不能仅靠旧配置推断，应同时撤销平台映射或更新revision。

只读角色配置原则：独立LOGIN角色、只授当前数据库CONNECT和查询schema USAGE/表SELECT，无角色继承、无建表或管理权限；默认transaction_read_only也设on。不能把应用数据库DSN直接填给助手。本地集成已另外验证即便关闭默认readonly，底层表授权仍拒绝INSERT。

工程默认限制在容量验证前固定：单查询2秒、锁等待500ms、连接建立3秒、每进程最多4个同时读取、最多100行/64,000字节结果。表目录每页100项，默认展示前20表结构，按table_names选最多20表，字段最多500条/关系100条，并标记截断。多进程的总并发是进程数乘4；这不是数据库集群全局配额或生产SLA。

## 4. 文档与研发源码发布

没有自定义文档目录时，读取仓库 `docs/assistant/manifest.json` 及其六篇短指南，分别介绍平台入门、Agent、聊天、知识库、评测与设置。只维护这份面向用户的正文，不再保留 Python 内置副本，不扫描全仓。自定义发布目录仍采用明确清单：

```json
{
  "revision": "release-20261117",
  "files": [
    {"id": "getting-started", "title": "快速入门", "summary": "项目入口和前端操作", "path": "getting-started.md"}
  ]
}
```

配置 `PLATFORM_API_ASSISTANT_DOCUMENT_ROOT` 可覆盖默认目录。`search_documents` 不传ID时返回最多32篇的ID/标题/简介目录，传 `document_id` 时从头读取该篇当前正文，最多300行/16,000字符。`query/line` 仅保留调用兼容，不再控制用户指南关键词排名或阅读起点。返回正文行号、SHA256、revision和truncated；超限须拆短或明确缺失，不能声称已读完整文档。

Runtime 沿每轮原 `authorize` 回调获取目录，临时追加到本轮模型系统消息，不新增分类模型或持久目录缓存。目录读取失败时普通聊天仍可继续。指南revision只作来源标记，更新正文或标记均不阻断旧会话；下一次操作咨询重新读当前内容。工具撤权、当前项目/会话授权继续校验，不提供历史指南快照或自动改写旧答案。

源码使用独立 `PLATFORM_API_ASSISTANT_SOURCE_ROOT` 和同格式清单，`PLATFORM_API_ASSISTANT_SOURCE_USERS` 为明确获准用户UUID的JSON数组。只有.py/.ts/.vue/.js/.sql可读；文档仅.md/.txt。两类资料均拒绝绝对路径、隐藏路径、越目录和软链接，单文件最多500KB。源码仍按文本查询，单次最多5文件、每文件80行/8,000字符；不套用指南新窗口。源码结果带相对path、revision、行号、hash，不能请求任意宿主路径。

发布负责人须去掉代码中的真实密钥和不应公开的业务资料。扩展名白名单不能保证任意.py文件都无秘密。源码权限撤销后，引用过源码的旧助手会话不再可读；改版本也触发重新开会话。

## 5. 日志与诊断

优先使用既有 `get_thread_run_diagnostics` 校验目标Thread/Run。首次读取和历史复核统一从目标Thread记录取得真实项目，重载目标项目当前成员角色并核对Thread ACL；助手会话自己的ACL另行保留。返回平台Trace与模型Trace的不同字段，保留available/partial/disabled/unavailable。

授权目标后，读取网关使用独立请求上下文按目标项目、当前角色与策略重新构建Runtime委托，不能沿用助手项目委托。原助手请求不改，读取和拒绝仍在审计范围内；证据归助手会话，目标项目单独记录。

证据外层 `scope.project_id` 是助手会话项目，诊断/日志的 `scope.target_project_id` 是排查目标项目，两者不同不表示冲突。`observed_at` 只是读取时间；`data.run_time.created_at/updated_at` 从获准Run快照投影，才是运行时间信息。没有新增原始错误正文、完整配置或堆栈返回通道。

有目标Run时优先用已验证platform_trace_id，缺失后用诊断来源的correlation.execution_request_id，再缺失按已验证Run编号检索；不接受模型指定执行请求编号，不把诊断响应顶层request_id当成旧Run请求。每条结果仍须匹配结构化目标项目、Thread、Run及所选关联字段，缺少资源字段直接丢弃，不扩大为项目调查。返回correlation_type区分platform_trace_id/execution_request_id/run_id。默认窗口来自获准Run的created_at前5分钟至updated_at后5分钟。时间缺失、无时区、逆序、扩展后超过24小时或仅给一端时间时返回 `assistant_log_window_required`；显式窗口最多24小时，返回实际 `query_start/query_end`。

diagnostics沿授权网关用metadata.run_id过滤、limit=1读取最新checkpoint，并再次核对Run绑定。persistent_state只包含任务名/已知错误码、实际中断/审批布尔、最多200条消息的类型计数和checkpoint标识；任务/中断有界，截断时不将未观察到写成确定不存在。消息计数是累计状态，不是Run增量，side_effects保持unknown。不返回原始错误、消息、参数或堆栈。状态来源失败与追踪来源失败分开；401/403仍拒绝整次读取。

availability_scope=current_trace_query_client及historical_collection=unknown明确顶层可用性仅表示当前追踪查询客户端，不能证明过去是否采集。request_id_scope=diagnostic_query_not_execution明确顶层request_id只属于本次诊断请求。每轮authorize还提供当前身份/项目的capabilities，数据库空只说明no_readable_sources；日志只给别名和not_checked状态，不泄漏路径或宣称已查通。

无Run调查须当前成员且在 `PLATFORM_API_ASSISTANT_LOG_USERS`（用户UUID JSON数组）中，可按项目、服务、含时区时间窗口和Trace查询，仍默认最近1小时、最长24小时。目标Run日志空或诊断未配置不授予扩大项目检索范围的权限。

日志来源任选现有Loki或管理员指定的固定文件。`PLATFORM_API_ASSISTANT_LOG_FILES` 是 `{"platform-api":"<绝对日志路径>"}`；配置文件时使用文件来源，不再同时查Loki。每文件最多扫描尾部512KB/100条候选，返回总计最多100条且日志条目合计64KB。跨项目、仅在正文碰巧出现Trace、非结构化或不匹配服务/时间的日志被丢弃。普通用户还逐条校验日志thread_id的当前ACL；按Run读取必须同时匹配目标thread_id/run_id。Trace可以来自客户端传播，不能单独承担授权，缺少资源关联的记录仅向明确获准的项目日志调查者开放。

允许返回的字段限于service/level/event/span_id/duration_ms/status_code/error_code/code/thread_id/run_id/project_id/trace_id/platform_trace_id/request_id，不返回原始自由文本、请求体和凭据字段。字段来源也必须遵守应用日志规范；结构化标识不是存放secret的地方。始终说明partial和覆盖范围，未命中不能解释为没有故障。

旧URL保留并需要登录、项目及当前Trace权限；助手关闭后该修复仍有效。前端唯一页面调用者及迁移要求见 [交接第8节](frontend-handoff.md#8-旧日志页面迁移)。

日志响应新增source=fixed_files/loki、availability=available/empty/unavailable/partial。配置的文件不可读会返回来源错误，不再静默伪装空结果。2026-11-17当前本地私有.env已配置platform-api/runtime-api/runtime-worker三个固定文件，不修改用户权限、业务库或模型凭据；无project_id/Thread/Run等字段的Runtime记录仍不返回。旧Run在当前文件窗口内未命中，只说明有界覆盖不足，不能证明过去没记录。当前追踪查询仍disabled/not_configured，但持久状态可读；真实Loki和生产采集未验证。

## 6. 审计、历史与审批维护

每次实际资料读取记录 `assistant.read.<operation>`，包含可信用户、项目、助手Thread/Run/tool_call、目标Thread/Run、数据源、查询SHA256、结果和耗时。外层HTTP另记platform_assistant.* / observability.logs.read，覆盖来源拒绝等入口结果。SQL字面值、结果正文、源码、日志和密钥不进入新增查询审计。

`assistant_evidence` 保存最小授权回执与版本，不复制原文。最终答复引用会生成record_citations审计，列出核实ID及未核实数量；这记录显式引用，不能证明模型内部全部推理来源。公开搜索回执是授权/调用关联，实际URL和摘要保存在该会话工具消息中。

普通审计沿既有失败可用策略，结果audit_recorded=false明确表示未成功入账；不承诺可靠outbox。授权回执保存失败时拒绝返回资料，因为不能留下无法复核的历史。会话删除及Runtime retention完成回调均走thread_access.remove，清理相应回执；通用审计留存沿平台现有规则。

后续加入业务写工具必须在可信后端组合根的business_write_tools显式传入；本期为空。原生HITL持久等待approve/reject，不能通过会话full_access跳过。业务工具执行时重新鉴权并按真实业务设计幂等；不把模型建议当已修复。

## 7. 验证与复现

日常确定性测试在服务目录运行（使用各自.venv）：

```bash
# apps/platform-api
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_observability_api.py tests/test_thread_fork.py tests/test_run_requests.py tests/test_thread_acl.py -q
# apps/runtime-service
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_r0_baseline.py tests/services/dearflow_agent/test_research.py -q
```

真实PostgreSQL测试显式选择当前Worktree：API `tests/test_platform_assistant_postgres.py`、Runtime `tests/test_platform_assistant_persistence.py`，设置 `ASSISTANT_LOCAL_POSTGRES_TEST=1`。后者会在当前登记Runtime库建立专属assistant_approval_test schema，跨四个独立进程验证暂停、无选择、批准/拒绝/撤权和旧ID重放，不发布测试图。

API PostgreSQL夹具需管理员先准备当前登记Platform库：

- `assistant_fixture.agents(id,name,project_id)`、`runs(id,agent_id,project_id,status,cost)` 合成底表。
- `assistant_data.agents/runs` security_barrier视图，仅暴露合成目标项目；另一项目secret行不在视图内。
- 专属无写权限角色：只读这两个视图，禁止底表。可见Demo对应两条运行，success/error各一，cost为1.25/2.75。
- 将仅本机保存的 `{ "dsn": "<该只读账号连接>", "project_id": "<合成项目UUID>" }` 写入 `.local-stack/assistant-fixture.json`，文件权限600，不入Git。

测试会核对路径和数据库名称属于当前environment.json。没有夹具时显式skip，不能填入主环境连接“凑通过”。真实API→Runtime联调客户端见前端交接；本次运行ID、输入输出和测试数字见 [验证记录](verification.md)及implementation。

## 8. 关闭、恢复与发布边界

设置 `PLATFORM_API_PLATFORM_ASSISTANT_ENABLED=false` 并重启API：bootstrap/读取返回assistant_disabled，新模型调用前授权也失败；现有非助手功能保持原协议。需要彻底禁止创建新助手Run时，同时停用项目图/Agent。历史读取仍按当前资料权限；撤权旧会话隐藏/403。

本地已演练关闭助手并撤源码权：bootstrap/read 503、旧源码历史403、其他会话state200、已授权旧日志200、匿名旧日志401；随后恢复配置。迁移downgrade不删除授权回执，应用回滚保留表，不以回滚代码为由恢复旧日志匿名行为。

2026-11-16原交付已由用户确认并合并；2026-11-17新增优化仅在当前工作区实施，没有Git交付或生产部署。生产发布、真实数据源凭据与视图、追踪后端部署及人工验收仍独立于本地开发。本轮API、真实模型签名读取与浏览器夹具的边界见[新增实施证据](implementation/03-guide-and-diagnostics-optimization.md)，不能代替完整GraphHarbor联合验收。
