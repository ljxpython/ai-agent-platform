# 后端补验、候选接入与发布

2026-09-15：用户批准完成剩余后端工作；**最终post30后端实施／验证与前端交接完成**。本文保留post29验证及发现缺陷后的post30修复过程，最终补验在末尾；前端浏览器和默认切换后置。

## 本轮修改

以下GraphHarbor路径相对`/Users/lijiaxin/PyCharmMiscProject/graphharbor`：

| 文件／函数 | 行为及原因 | 当前证据 |
|---|---|---|
| `libs/langhost/src/langhost/protocol_api.py:protocol_commands` | input.respond使用`{interrupt_id: response}`，支持并行中断准确恢复；沿用来源Run kwargs.version | 旧实现双并行中断无法恢复；修复后官方／GraphHarbor分别回答alpha与beta，得到alpha:ALPHA、beta:BETA |
| `libs/langhost/src/langhost/streaming.py:_event_frame` | stream_subgraphs=false同时检查外层namespace及lifecycle data.namespace，避免目标子事件漏过滤 | 新增`test_run_stream_subgraphs_false_excludes_target_scope_lifecycle`，全量与真实HTTP过滤通过 |
| `tests/acceptance_app/v3_graphs.py`及`v3.langgraph.json` | 新增两层嵌套、父捕获子错误、并行中断、慢图参考场景；仅使用官方图，不含平台业务 | `run_v3_matrix.py`双端真实HTTP通过 |
| `tests/acceptance_app/run_v3_matrix.py` | 深层namespace、父捕获失败后成功、并行中断分别恢复的真实验收入口 | 两端退出码0，报告`artifacts/v3-matrix-{official,graphharbor}.json` |
| `tests/javascript/v3-lifecycle.mjs` | 增加子图output与messages投影消费 | 双端及实际wheel通过，限制见下文 |

官方依据：本轮再次查询Docs与Reference，`Command.resume`支持中断ID映射。冻结官方版本在父节点内部ainvoke并捕获异常时未输出子failed；保留实际流，以父结果caught和根completed验收，不伪造子事件。state.tasks可能保留已完成任务的interrupt历史，待处理任务须结合result判断。

复跑：GraphHarbor仓库执行`.venv/bin/python tests/acceptance_app/run_v3_matrix.py --url http://127.0.0.1:31397 --output artifacts/v3-matrix-graphharbor.json`，官方使用31398。复用原官方0.13.0冻结依赖与独立数据库。首次新API启动期间请求遇到502，服务就绪后重跑通过，未改业务超时绕过。

## B3/B4补验完成

- `run_v3_matrix.py --transport`：两层namespace与depth过滤、重复订阅、Run SSE关闭／开启子图、live/replay逐事件相等、Last-Event-ID续读、metadata与heartbeat控制帧通过。已有真实PostgreSQL过期cursor测试也在本轮全量通过。线程订阅以数据库持久事件回放，无官方内存ring buffer过期限制；不为模仿内存限制主动丢历史。
- 真实Worker SIGKILL：Run `8db03f64-7a67-4cf5-a275-1895f197728c`，线程`21623b7f-f28b-4ed9-af3a-951575826aa6`。执行中杀掉独立验收Worker，重新启动后观察running→pending→running→success，持久lifecycle为running/running/running/completed；没有failed或重复completed，结果仅一条slow-done。证据`artifacts/v3-worker-kill.json`。没有杀业务Worker或停止共享PostgreSQL。
- Server完整回归：**159 passed、18 skipped，67.49秒**；源码／scripts ruff check与format全通过；五个相关源文件mypy通过。参考图另3 passed，0.76秒。
- JS SDK两端：子messages与output、cause、失败、中断恢复、工具input/output原始事件通过。GraphHarbor还收到10个checkpoints与1个custom事件。
- **公开SDK限制如实保留**：SDK1.9.28工具投影在两端均产出2个相同ID的handle；原始tools事件只有一对，非重复执行。官方0.13.0在该SDK订阅方式下未返回checkpoints/custom（0/0），GraphHarbor是10/1。官方运行时用`REQUIRE_CHECKPOINTS=0`明确记录基线缺失，GraphHarbor必须通过这两项断言。不得宣称这些客户端行为已完全无差异；D交接核对平台SDK1.10.2与已有patch，不在Server删除正确事件。
- FakeMessagesListChatModel不产生文本增量，原测试无法用于验收消息流；已用官方FakeListChatModel逐token流测子messages。带工具测试另用确定性ToolModel，通过真实create_agent产生工具事件，没有注入协议字典。

## E2/E3确定性性能与回退

新增外仓`tests/acceptance_app/run_v3_performance.py`。同一v3_edge图、相同values请求、分别预热一次后交替v2/v3各20次；独立API/Worker，非真实模型，40次全部success。原始样本`artifacts/v3-performance.json`。

| 中位指标 | v2 | v3 |
|---|---:|---:|
| 首事件（metadata） | 18.12ms | 19.12ms |
| 流结束 | 380.71ms | 388.60ms |
| EOF后读取持久终态 | 11.55ms | 13.90ms |
| 事件数 | 4 | 26 |
| SSE字节 | 311 | 19688 |
| API+Worker采样最大RSS | 285804KiB | 285928KiB |

v3总时长约增加2.1%，此样本未发现明显时延退化；它返回完整typed事件，v2请求只返回values，字节约63倍，不能承诺省流或提速。RSS是每轮后采样值，不是分配峰值。另以10ms并发HTTP轮询观察持久终态，EOF相对首次观察的中位差v2 -7.64ms／v3 -10.02ms：负值来自轮询延迟，**不能解释为提交前发终态**；提交顺序用真实事务失败测试保证，不伪造精确commit计时。

每个v3后均有新v2成功；最后读取早先v3 Run仍含lifecycle，入口回退不改历史版本。源码默认未切换；消费者默认切换仍属前端后置门禁。

## B5发布完成、C1升级（post29阶段记录）

- 两包**0.13.0.post29已发布PyPI**，先runtime后CLI，四个远端产物SHA256与本地一致；未创建分支、commit或push。按本次用户授权使用本机发布凭据，凭据未进入文档／命令参数。
- 发布前实际wheel在独立Python3.11环境启动API31396和Worker，完整HTTP矩阵／传输以及官方JS SDK通过。干净环境langchain-core1.6.3也完成此链路，补齐之前只有导入检查的缺口；参考官方对照环境仍为1.6.0。
- `apps/runtime-service/pyproject.toml`与`uv.lock`锁步post29，`uv lock --refresh-package graphharbor --refresh-package graphharbor-runtime --upgrade-package graphharbor --upgrade-package graphharbor-runtime`只升级两包。首次读取PyPI旧索引缓存报无版本，刷新后成功，不修改索引地址或放松版本。
- `uv sync --frozen`与`uv lock --check`通过，Runtime API/Worker按本地栈脚本重启。真实平台验收继续进行。

| 远端产物 | SHA256 |
|---|---|
| graphharbor wheel | 47dea16fbf15ef16b349d5c214f991e29aa6dcf7ff47b215737ce818bca50baa |
| graphharbor sdist | c5064fc93190eba97145fc90b76801db43097dbe47a8c452f6de5a1949af0e77 |
| graphharbor-runtime wheel | 3c527e222020fb3164e899636058c2681a01f5867b166f509b6cd30f3546db17 |
| graphharbor-runtime sdist | a381e0d46d2ade9875861c4fa3e86113fb41ffb73af6061b21e275acf6ae806b |

## C2平台入口核对完成

- `modules/runtime_gateway/presentation/http.py`公开create、stream、join与join-stream；没有公开runs/wait入口，因此不新增一个仅为版本迁移服务的API。
- `RuntimeGatewayService.stream_thread_run`先调用create_thread_run，经launch_runtime_run统一校验版本、幂等与授权，再join已创建Run。join从Server持久kwargs读取版本，不受浏览器任意覆盖。
- run.start也进入同一创建流程；旧默认v2、显式v2/v3、非法版本拒绝、版本不进入业务context都已验证。SDK adapter保留既有HTTP补偿路径，不给不接受version的SDK create硬塞参数。
- `apps/platform-api/tests/test_run_requests.py:test_stream_creation_preserves_version_and_join_uses_saved_run`新增stream入口覆盖。Run请求**23项通过，3.053s**；`test_runtime_gateway*py`**41项通过，2.551s**。已授权checkpoint来源Run版本继承及幂等恢复测试保留。

## C平台post29真实回归

本表均在平台已安装post29且API／Worker已重启后执行。入口是 `apps/runtime-service/tests/services/dearflow_agent/test_platform.py:test_platform_creates_and_completes_dear_run`。每次使用独立测试项目；模型用例串行，清理只恢复本次启用的测试模型，不禁用用户原来启用的模型。

| 场景 | 结果 | thread／Run证据 |
|---|---|---|
| 文件与恢复：澄清→Worker重启→checkpoint一致→execute审批→发布审批→下载内容／SHA256，各次恢复保持v3 | 1 passed，47.67s | thread `2f417cf3-e049-4f89-bd24-472782d20002`，source `b41ca3f0-0891-46dd-adbc-346ebfe9680d`，final `3d0ece54-7f5d-4236-a932-648e8bfc0726` |
| Ultra同名双task、cause关联、独立子scope、两结果与根隔离、最终回放 | 1 passed，14.58s | thread `1bf7eaf7-5f7a-4ba1-9834-2ac06031a02c`，Run `e45c8f49-bef7-43bd-8633-f2e9bd0e9b27` |
| 父Run取消，真实持久interrupted | 1 passed，6.40s | thread `dbd1a910-577f-4f01-aca2-be5668291b22`，Run `cc55848a-5832-4f0e-a32e-2e993a8f6e01`；子协程随父取消另有本轮组合测试，不将ACK当子进程证明 |
| Pro真实研究：澄清、write_todos、search_web／fetch_page、队列补充唯一consumed、写报告／审批发布、来源URL与下载SHA256 | 1 passed，58.41s | thread `67f908d2-31f8-4464-9dea-9a79b8c6b6f0`，source `4dec0c56-bfca-47c4-959a-639c4b4f6d08`，final `ace68cea-6cb7-4c78-abca-8a97e0c7018b` |
| 默认未指定版本，仍成功走v2 | 1 passed，6.93s | thread `42d497b5-30cc-4fc3-9e39-1d27565ae1bb`，Run `936c1662-7eee-4db3-bf97-e9d966e6129d` |
| Langfuse回读双子观测与真实GENERATION usage、父子链、策略／技能／推理metadata | 1 passed，17.13s | trace `3aba7a901cd3b76c925bf3ab2745267c`，两个general-purpose均找到真实token usage；不推算独立子任务费用 |

文件场景其余resume Run：`e44bddac-c716-47bc-81d7-8cbd19761ee7`、`ed9a5174-5d15-4a15-8cf3-bf0ac8ad48f3`、`1e11b66f-179b-4046-b95c-c85d7db72fab`。研究resume：`6bdfe496-d9b7-4ba3-a116-3b19c6505169`、`6914fea7-dde7-484d-848d-51d017b52a21`。每次暂停都检查v3回放。

本轮真实双任务首次失败：测试未请求stream_subgraphs却断言子lifecycle。旧实现泄漏子事件，修复过滤后此错误预期暴露。现已在test_platform.py构造subagent请求时显式加入 `stream_subgraphs=True`；不恢复Server泄漏。随后真实双任务通过。

组合回归：`.venv/bin/python -m pytest -q tests/services/dearflow_agent tests/observability/test_langfuse.py --tb=short` → **67 passed、6 skipped，75.56s**；skip为需显式启用的真实场景，本表另外执行，不混加通过数。已存在的Pydantic序列化警告、LangGraph v3 beta警告和SWIG弃用警告保留，不代表测试失败。

模型／MCP装配升级回归：`.venv/bin/python -m pytest -q tests/services/test_mcp_probe.py tests/runtime/test_modeling.py --tb=short` → **9 passed，8.57s**。MCP此处为装配／探测契约测试，不宣称外部所有MCP服务逐个实连通过。

复跑时以 `DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_STREAM_VERSION=v3` 为公共环境变量，分别追加 `DEAR_PLATFORM_FILES_TEST=1 DEAR_PLATFORM_RESTART_TEST=1`、`DEAR_PLATFORM_SUBAGENT_TEST=1`、双任务加 `DEAR_PLATFORM_CANCEL_CHILDREN=1`、`DEAR_PLATFORM_RESEARCH_TEST=1`；执行 `.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s`。默认v2去掉版本变量；Langfuse另执行 `DEAR_SUBAGENT_TRACE_THREAD=1bf7eaf7-5f7a-4ba1-9834-2ac06031a02c .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_subagents.py -k live_subagent_trace -s`。

## E3在途回退、D/E4交接

实际wheel运行v3慢图期间新建v2，两者成功；v3保留原版本及lifecycle回放。v3 Run `2b278d76-c2de-4088-82c3-15f00e50b62b`，thread `d316a453-ce82-4054-87b4-908733f9eff6`；新v2 thread `77be0332-6de8-4b98-b982-91bdac5c636c`。证据外仓 `artifacts/v3-inflight-rollback.json`。没有改历史数据或全局默认。

已新增 [前端交接](../frontend-handoff.md)，列出Dear、共享Chat、overview、workspace与Python／HTTP消费者、当前锁版本／patch、最小适配位置和浏览器清单。D交接及E4消费者清点done；D代码／浏览器、E1与E4实际默认切换由用户明确后置。本文不能用后端验收代替浏览器验收。

## 失败验收发现的配置缺陷：post30修复

真实平台将config.recursion_limit设置为1仍成功，复现Run `cf8e5bf6-0228-43bc-8027-66876233967f`、`5e9946b8-d2c3-4116-b9ab-e59dc0d2627d`。核对 `ProductionWorker.run_once`：已合并assistant／thread／run的configurable、metadata和tags，但重建RunnableConfig时没有传递顶层recursion_limit，因此工厂和图实际收到默认值。不是模型不遵守提示，也不是v3隐藏失败。

- 官方Docs／Reference确认recursion_limit属于顶层RunnableConfig，达到上限由原生GraphRecursionError处理。
- 修复外仓 `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/production_worker.py:ProductionWorker.run_once`，按既有assistant→thread→run优先级将明确设置的recursion_limit传给工厂与执行器。不增加通用任意config透传，不允许客户端覆盖运行身份。
- 外仓 `libs/langgraph-runtime-pg/tests/test_production_contract.py:test_worker_preserves_recursion_limit`：真实PG／Worker与原生两节点图，三组测试覆盖assistant默认、thread覆盖、run最高优先；验证实际成功／GraphRecursionError、唯一持久终态。**3 passed，7.35s**。
- 平台test_platform新增opt-in `DEAR_PLATFORM_FAILURE_TEST=1`：使用真实图的步数限制触发失败，检查Run error、根lifecycle.failed与错误文本，不能有completed。不增设业务失败工具、不人为修改数据库终态。
- 此缺陷与本轮失败验收直接相关，属于GraphHarbor通用运行配置边界。post29不可变，修复锁步发布post30；后续最终发布／平台证据追加在这里。

post30最终Server全量 **162 passed、18 skipped，86.98s**，ruff源码/scripts、68文件格式、Worker mypy及版本检查通过。实际wheel安装到独立Python3.11环境后，HTTP矩阵与JS SDK再次通过；真实HTTP步数上限Run `addf701e-69d6-47a7-b641-cb7dda5c0cd8`（thread `c40dfb78-f38c-4087-bbe0-6a476e44c460`）正确error／failed。矩阵 `artifacts/v3-matrix-post30.json`；默认心跳15秒，测试慢图由2秒改为20秒，不再依赖缩短生产心跳的环境参数。

两包post30已发布PyPI，远端四产物hash已核对一致，详见外仓 `docs/release-notes-0.13.0.post30.md` 与 `artifacts/v3-post30-dist/sha256.json`。平台pyproject／uv.lock仅升级两包，uv sync --frozen与lock --check通过，API／Worker已重启且安装版本均为post30。

平台第一次post30失败验收已经产生真实error／failed，但测试假设所有入口error是字符串，遇到Run SSE原有结构化error报AttributeError。现按此入口读取message，兼容字符串；线程Protocol字符串适配与Run SSE扩展不混为一谈，已补前端交接。这是测试断言修正，不改Server错误事实。

post30平台最终补验（每项独立执行，不合并历史测试数字）：

| 场景 | 结果 | thread／Run |
|---|---|---|
| 原生步数限制失败、根failed回放、无completed | 1 passed，3.42s | `a50f7953-41d7-496e-83ce-8361b2437269`／`19167262-59b1-459e-97fe-80968edeb04e` |
| 显式v2双task与根子隔离，无v3 lifecycle泄漏 | 1 passed，22.57s | `c1a70bdf-3c49-4aa6-8835-30c5aad7b379`／`8fa48ed2-7f12-42a9-97fc-72506b9aeefc` |
| 文件完整交付与Worker重启，所有resume保持v3 | 1 passed，134.80s | thread `46ff345d-0c50-45cb-8098-f13db14e4344`，source `0cec7589-e932-4bcd-a911-9dadf69bfc15`，final `cbfa2620-fdca-4675-8735-d86d4c20f855` |
| Pro研究、队列补充、来源URL、报告审批发布与下载SHA256 | 1 passed，154.00s | thread `c380b7e8-7671-4022-acd0-65ee929c7fe7`，source `477dc6d0-9cba-457e-b2ff-a5977464656e`，final `0c1edfe2-7fb4-4055-bc22-fdf73de2243c` |
| v3同名双task、ALPHA/BETA、cause关联、根子隔离与回放 | 1 passed，32.69s | thread `206e3db1-ce88-4f05-a3aa-742383902842`，Run `3005a2be-75d9-4937-b4c1-60ecc975f045` |
| v3父取消，持久interrupted | 1 passed，9.90s | thread `7e00475c-3350-4df5-866f-ceb5e1155660`，Run `84c831bb-523f-43e6-9fe1-fa3b73cebc39` |
| 默认未指定版本仍为v2，新Run成功 | 1 passed，13.16s | thread `e28a0066-d802-4f6c-b79f-f23b84079803`，Run `7ded94ba-331a-474e-98f5-cf34042e72b8` |
| post30双子Langfuse真实父子链、GENERATION usage、策略metadata | 1 passed，30.90s | trace `2b744a92e6072b293d1791c7550b3e62`，对应thread `206e3db1-ce88-4f05-a3aa-742383902842`，两子均有实际usage |

post30文件resume另含 `ee089edf-2cef-4505-9353-a595bb4006fb`、`2fcd6d7b-027f-404e-90a4-0cb9eb0baea1`、`7087d580-d684-4c30-9ea3-830ca8d89368`。本次耗时含真实模型、Docker与Worker重启，不与确定性Server性能基线混算。

post30研究resume另含 `13cda468-b420-4ca8-9ca6-6e3c99c8d12a`、`034ee979-8528-4e22-b633-2fb59288655e`，每次暂停检查v3回放。无需提高测试步数限制绕过失败，默认平台config继续按原规则执行。

post30平台组合回归命令：`.venv/bin/python -m pytest -q tests/services/dearflow_agent tests/observability/test_langfuse.py tests/services/test_mcp_probe.py tests/runtime/test_modeling.py --tb=short` → **76 passed、6 skipped、17 warnings，127.98s**。测试文件ruff通过（使用外仓已安装ruff，Runtime环境没有ruff可执行文件）；两仓库git diff --check通过。警告类型与前述相同，无新增失败。

post30双任务补验中Run `a80dcfe6-4010-49a1-a518-eb86eeb4e090`正常产生两个task，其中BETA成功，ALPHA子模型将“这是委派验收，直接回答代号”理解成不应遵循的规则覆盖并拒答，导致内容断言失败。检查真实task参数／返回后确认不是scope丢失或步数限制错误。将测试任务改为正常知识问题“希腊字母表第一／第二个字母的英文大写名称”，继续严格断言ALPHA/BETA、两task、cause与根子隔离，不放宽成功条件、不修改Agent生产提示词。真实模型仍存在输出波动，不能以一次通过声称长期可靠性。

研究产物额外只读校验 `test_completed_research_delivery` **1 passed，2.48s**：同一post30研究thread／final Run，验证完整工具集合、唯一消费消息、来源URL及产物哈希。命令环境为 `DEAR_COMPLETED_RESEARCH=8141d1b7-fe8a-4e68-9548-082ed7ae1a57,c380b7e8-7671-4022-acd0-65ee929c7fe7,0c1edfe2-7fb4-4055-bc22-fdf73de2243c`。

最终文档收口：README／tasks／verification／plan、FEATURES、Dear P3与两份前端交接、外仓兼容矩阵／post29与post30发布记录已同步；每个前端未实施项保留deferred，不计为后端欠项。8份项目文档相对链接检查通过。独立验收API31396/31397、官方31398与独立Worker已停止，平台常驻API／Worker保留post30。没有改前端代码，没有commit／push。
