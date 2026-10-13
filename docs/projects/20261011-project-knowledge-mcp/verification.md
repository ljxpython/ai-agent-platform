# 项目知识 MCP - 验证计划与记录

**当前状态：非前端与通用多格式验收完成；仅原业务题集B02仍blocked，前端接续。** 2026-10-13由[承接专项](../20261013-knowledge-documents-platform/verification.md)完成Ubuntu PDF/Office/图片真实链与非前端Final，环境B01已解除。下文2026-10-11数据保留当时的验证与缺条件边界，不作为最新状态；前端浏览器由同事继续。

执行日期：2026-10-11。P/K实际目录见[README](README.md)；证据保留在本Worktree `.local-stack/evidence/`、`.local-stack/knowledge/`，私有配置不导出。已有测试名称、skip、只读源码核验与合成资料结果分别标注，不替代真实业务验收。

## 验证环境

| 项目 | 本次实际值 |
| --- | --- |
| 平台测试时基线HEAD | `116cc26f02911ea3d1318663ed5d740c6f6933c5`，测试包含其上的本次工作目录改动；交付分支为 `feat/project-knowledge-mcp` |
| 知识工程测试时基线HEAD | `c7eeb6d647b093b9b577e32a61988bd3e26c30dc`，测试包含其上的本次工作目录改动，使用原工作目录及独立venv；已提交并推送 `568b8b73f8cfd86e111928c2ff12971a3d487fc0` |
| 本地资源 | `wt_39abb85e02a2`；原生PG、专属Redis、Runtime local，无Docker |
| HTTP与模型 | 两项目Bearer/namespace、Streamable HTTP；miaomiaoai `deepseek-v4.1-flash`，独立Ollama `nomic-embed-text`/768维 |
| 知识端版本 | FastMCP3.2.0、LightRAG1.4.12；Docling/RAGAnything为未安装的documents extra |
| 消费端版本 | 仓库锁定langchain-mcp-adapters0.3.2及正式GraphHarbor post45，未升级平台锁 |
| 样本 | alpha两个同名Markdown＋beta一个Markdown；另有失败/新版本样本。均为本任务合成、无业务敏感资料 |

知识端抽取曾因DeepSeek thinking输出无正文而失败，补 `LLM_EXTRA_BODY_JSON={"thinking":{"type":"disabled"}}`、本地8192输出预算后新版本入库/发布成功。旧失败索引保留且未发布；该配置不改变平台模型默认策略。

## 验证计划与矩阵

| 编号 | 验证范围 | 实际结果与证据边界 |
| --- | --- | --- |
| V01 | 真实HTTP discovery、FastMCP认证/工具注解、官方Adapter | 通过：两scope HTTP、只读工具与官方Adapter契约；不是stdio代替HTTP。G0只完成文本模式，documents安装阻塞另列B01 |
| V02 | query/top_k/额外scope、路径/symlink、Bearer | 通过：安全/HTTP/stdio用例及部署检查；无授权401、空白/超长/非严格整数/额外project参数被拒，跨scope状态not_found。错scope在discovery前拒绝，provider计数0 |
| V03 | 平台可信binding、伪造、fork、旧Thread/服务账号 | 通过：新5项binding测试、真实Thread/Protocol/state/patch伪造矩阵、两项目/两类身份、fork重新签发；旧Thread不自动迁移、未绑定普通Chat仍可用 |
| V04 | 单次检索、ready locator、同名、错误/无命中、content/artifact | 通过：K计数断言一次aquery_data/零aquery、精确opaque locator；真实同名来源与官方Adapter文本/artifact一致。错误不转no_hit，不编造页码/下载URL |
| V05 | 大中文/escape/坏类型/额外metadata、F04及历史 | 通过：最多8条、800字符、12KiB；官方HTTP大结果再经F04预算800，缩完整字段并同步artifact；极小预算safe JSON error，未外置半截JSON |
| V06 | 双scope并发、缓存/生命周期、读写锁、发布/重启 | 通过：独立workspace/cache、初始化失败/取消与清理异常、全部engine关闭；损坏manifest/部分index拒发布；读锁拒写、签名改变拒绝、新版本和两原索引重启后同值 |
| V07 | 两主图装配/deny/Plan/schema/offload/子图、当前权限 | 通过：两图×6模式组合；非法tool call仍被执行门禁拒绝，禁止模式discovery/provider0；子图不获知识工具。平台签名/当前权限契约覆盖执行边界，普通用户/服务账号撤权另有真实Worker链；未另改队列/定时/resume机制 |
| V08 | 两项目×DearFlow/Showcase完整Worker/模型链 | 通过：4条API→Worker→DeepSeek→MCP→片段→回答/历史，事实可核对、A/B不串，目录/defaults/实际装配一致 |
| V09 | 公开JSON/SSE/history、异常/断网/取消 | 通过：真实SSE回放/公开输入与历史无私有binding/Key/path/raw_data；受控HTTP错误/坏响应/断网保持ToolMessage error；真实检索中Stop后观察6秒无迟到结果 |
| V10 | 同事前端F01–F10、三视口/主题/刷新/撤权 | 本轮排除：已交4份真实Worker＋6份官方Adapterfixture、环境/步骤/话术；实际浏览器由同事F1B回传，不标已通过 |
| V11 | 代表性业务资料/30题/无答案与恶意资料 | blocked：本机3份合成md的20题有答案命中20，跨项目0；10题无答案可召回近似片段，不能判全部no_hit。另有真实无答案不编造及恶意片段不执行证据；不能替代10–20份业务PDF质量门槛 |
| V12 | 性能样本、deadline/Stop、发布回退与禁用 | 小语料本机边界通过：p50 5.8845s/p95 10.892s、并发2；真实新版本/旧token401/旧scope保留、MCP/Embedding重启、deny/unbound普通Chat/原历史。基础附件/记忆/Plan沿现有回归，未做生产负载或业务PDF解析性能 |

### 业务质量门槛（仍有效，B01/B02解除后执行）

10–20份无敏感、代表性文本PDF，至少包含同名资料/长片段/近似问题/多文档关联；标注30题：20题有答案、6题资料无答案、4题提示注入/越界诱导。20题正确资料Recall@8至少80%，来源精确映射ready文档，跨项目或错误归属为0；无答案不得编造项目依据，恶意资料不得扩权或执行片段指令。模型/索引版本、实际document_id/chunk_id、失败样例和答案依据留证。

扫描PDF/复杂版式/多模态与大规模负载未作为本机支持项。现有线程附件DOCX/PPTX能力不能推导成知识服务同等支持。

## Phase 验证记录

2026-10-11，执行人：本轮AI。以下16条对应tasks的16项完成任务；细节在后续证据区，未向Final区搬运Phase结果。

| Task | 已执行的最小验证 | 结果 |
| --- | --- | --- |
| P01 | P/K/D源码、锁文件、调用者/权限/来源核验；官方LangChain MCP/Adapter接口依据 | 通过，只读盘点；D未改 |
| P02 | 用户明确批准方案与本地源码启动，三层职责/最小范围落笔 | 通过，人工授权来自会话，AI未自行批准 |
| P03 | 现有Web组件/SDK投影位置、F01–F10/V01–V12职责和契约 | 通过，交接设计；不计浏览器通过 |
| P04 | 文档/导航/任务/CONTEXT/FEATURES/CHANGELOG状态和新增链接核验 | 通过，44条全仓文档检查问题及旧链接另列；本次两真实目录为用户要求 |
| G0 | 两namespace真实HTTP/只读discovery、官方Adapter实际ToolResult/ToolError；frozen documents安装尝试 | 文本Gate通过；PDF兼容性明确blocked而非忽略 |
| S1 | K认证/严格参数/路径/symlink/stdio/HTTP、无授权401、跨scope状态拒绝 | 通过，包含真实部署严格输入检查 |
| S2 | 单次检索计数、opaque locator/同名、no_hit/error/取消、真实两scope来源 | 通过；来源与正文来自同一次结果 |
| S3 | 生命周期/manifest/部分index、清理失败不掩盖原异常；真实读锁/失败发布/版本/重启 | 通过；K完整24项＋部署6断言；PDF仍blocked |
| A1 | 新5项binding与fork/ACL/配置、两项目真实新Thread，PG无DDLmerge升级 | 通过，其他受管binding保留、旧Thread不批量迁移 |
| A2 | 真实伪造/SSE/history矩阵、普通用户/服务账号撤权；委托修复后的鉴权相关91项 | 通过，撤权后新Run/state403且provider0 |
| R1 | 公共MCP加载、官方HTTP/冲突/非readOnly/断网、错scope零discovery | 通过；调用者及旧测试导入已同步 |
| R2 | 安全来源/额外metadata/坏类型/大结果、content/artifact/F04组合 | 通过；6份协议fixture为实际Adapter产物 |
| R3 | 两主图×6模式组合、非法调用双门禁、子图不扩权、defaults/catalog | 通过，12项组合；禁止模式provider0 |
| L1 | 资源登记幂等/冲突/外来监听/所属选取4项、shell语法、真实knowledge重启 | 通过；统一启停只管理本环境，保留数据 |
| F1A | 4份live＋6份受控fixture采集、正文/artifact一致、无配置秘密、前端话术/路径 | 通过；实际前端F1B不计本轮 |
| V1A | 相关单元/契约、11项真实Worker链、30题合成质量、版本/重启/禁用/Stop/历史 | 本机文本范围通过；全仓基线与B01/B02如实保留 |

### 单元、协议与部署证据

| 执行 | 实际结果 | 证据 |
| --- | --- | --- |
| K完整tests（最终源码） | 24 passed，10.42s | `.local-stack/evidence/knowledge-unit-final.log` |
| API知识/Plan/委托/预算/fork/工具限制六文件 | 59 passed，334 subtests passed，30.34s | `.local-stack/evidence/api-knowledge-unit-final.log` |
| Runtime工具治理/Plan/知识结果/官方HTTP/两图组合/MCP/F04七文件 | 74 passed，47.34s | 本轮终端执行记录；包含12项两主图组合 |
| Runtime委托修复相关诊断/usage/message-read/platform-auth/run-control/auth | 91 passed，14 skipped，9.04s | 本轮终端执行记录；skip不计通过 |
| local-stack知识登记/进程归属 | Ran 4 tests，0.075s，OK；shell语法通过；真实command故障自检2场景只清本次新进程、保留已有Embedding | `.local-stack/evidence/knowledge-resource-unit.log`、`knowledge-startup-failure.json`（受控shell，不发真实signal） |
| 两项目HTTP并发及隔离 | alpha2文档/beta1文档；4.183s/4.442s，同值正文/structuredContent，无越界 | `.local-stack/knowledge/http-smoke.json`；认证/注解同时由HTTP测试覆盖 |
| 部署/维护六项 | 全6断言true；失败及新namespace保留 | `.local-stack/knowledge/deployment-check.json`；公开安全摘要[deployment-evidence.json](deployment-evidence.json) |
| 最新源码服务重启后查询 | 两scope均ok、alpha2/beta1来源、项目事实隔离 | `.local-stack/knowledge/post-restart-query.json` |
| 静态门禁 | API全src及本次测试、Runtime全src及本次测试、K本次异常处理、worktree脚本/测试Ruff；P/K diff检查通过 | `.local-stack/evidence/knowledge-api-lint.log`、`knowledge-runtime-lint.log`及本轮终端记录 |

本次模型/知识/测试身份的5个私有值在P/K的95份改动/新增文件扫描中命中0；原凭据误回显风险仍按实施记录提示用户轮换，扫描不能撤回既有工具输出。定向生命周期/LLM配置复查8项通过（0.09s），为完整24项的子集，不重复加总。

部署六断言包括：服务读锁拒writer、空文本失败不能publish、严格输入/跨scope文档状态、安全签名拒变、新namespace独立token及旧token401/旧scope保留、MCP与Embedding重启后两原索引doc/chunk/preview同值（排除随机source_id）。不是通过删除/回滚数据库获得成功。

最终复查监听与健康：Runtime API/Worker、Platform API/Web、专属Redis、知识MCP/Ollama均运行，Runtime ready与API health均yes。PID以所属环境登记为准，服务保留供同事联验。

### 真实Worker与模型链（11项）

执行 `tests/e2e/test_knowledge_platform.py`，11 passed in 163.16s；日志 `.local-stack/evidence/knowledge-platform-live.log`。所有服务、Worker、DeepSeek和Embedding均真实运行，使用本任务测试身份/项目，无mock替代授权链。

| 场景 | 实际断言 |
| --- | --- |
| alpha/beta×Showcase/Dear（4项） | 一次知识tool call，正确登录路径/时长/锁定事实，来源同值，跨项目state403；history保留原source_id |
| deny与unbound（1项） | 普通Chat成功、provider增量0；deny后原历史来源仍可读 |
| 普通用户/服务账号撤权（2项） | 先有授权真实检索成功，再撤成员/grant；新Run/state403，provider增量0；finally恢复测试grant |
| 检索途中Stop（1项） | 观察到知识调用后取消，6秒后消息同值，无迟到知识ToolMessage |
| Worker重启＋fork（1项） | 原消息同值/provider增量0；fork历史保留、重新签binding后真实query成功 |
| 公开输入/SSE（1项） | 16个Thread/Protocol伪造组合＋state/patch拒绝；已有Run SSE回放不露私有binding/Key/path/raw_data，provider增量0 |
| 未提供事实（1项） | 查询ISO27001颁发日期后Agent明确资料未提供；未猜日期、仅知识工具 |

4条主链安全样本已交[fixtures](fixtures/README.md)，包含实际Thread/Run/ToolMessage/答案。停止/撤权/SSE与其他证据留 `.local-stack/evidence/knowledge/`。测试provider计数来自本任务服务日志，不对生产供应商建立新监控机制。

### 性能、质量与运行边界

- 3份合成Markdown30题，20题有答案命中20（Recall@8=100%），跨项目来源0。10题无答案中检索可返回近似片段，不据此声称no_hit率/回答正确率；真实Agent无答案另有1条Worker证据。原结果 `.local-stack/knowledge/retrieval-quality.json`。
- 这30次顺序查询的p50=5.8845s、p95=10.892s；并发2的另一次HTTP样本为4.183s/4.442s。均是小语料本机样本，不是生产SLO、冷/热标准压测或业务PDF性能结论。
- 一次资源快照：实际MCP监听进程RSS265600KiB，Ollama主监听RSS22376KiB，corpus约1160KiB、独立模型目录267900KiB。不是进程树峰值或负载期间峰值；时间/PID原证据 `.local-stack/knowledge/resource-snapshot.json`。
- K初始化/单次检索各60秒、关闭30秒有界；Runtime沿官方HTTP超时与现有执行预算/取消。Stop防迟到写入已验，外部已提交Embedding/关键词LLM可能继续计费，不承诺远端立即结束。
- 读锁/不可变发布保护查询与离线写入。新版本、旧版本恢复和停用deny已真实验证；原附件/记忆/Plan沿现有非外部单元/契约回归，本轮未新增知识CRUD、个人记忆或在线写路径。

## 扩大回归检查与基线失败

扩大检查是V1A的Phase证据，不是“全仓全绿”。以下失败已保留，未把skip/deselect或0测试算通过，未顺手重构无关业务。

### Runtime

初次非外部全量：17 failed / 1506 passed / 151 skipped / 61 deselected，377.45s。原日志 `.local-stack/evidence/runtime-unit.log`。其中5项服务账号/credential签名问题本轮修复，修复后相关91项通过、14项按既有条件skip；没有重跑全仓后自行算出1511 passed。

其余12项在HEAD源码＋HEAD测试快照真实复现（12 failed / 8 passed，83.02s），证据 `runtime-head-baseline.log`：旧model monkeypatch目标已不存在1项、子任务cancel超时2项、Reference middleware顺序1项、PII容量2项、Workflow预算1项、媒体fake参数5项。额外Docker fake fixture单独运行失败也在HEAD复现，`runtime-head-docker-fixture.log`；没有启动实际Docker。

既有 `tests/integration/test_loop_detection_worker.py` 引用不存在的 `scripts.verify_execution_budget`，全量收集时明确ignore，不将其当通过。本次未补这个无关脚本。

### Platform API

初次unittest全量：Ran 408，3 failures / 3 errors / 16 skipped，178.802s，日志 `api-unit.log`。其中credential委托契约error随Runtime修复复验通过；其余基线：

- resilience两个fake upstream缺get_thread_state，HEAD复现（`api-head-resilience.log`）。
- 网关inventory缺4个既有后台route、Thread ACL测试少标题seed期望字段，HEAD复现（`api-head-baseline.log`）。
- SQLite completion UUID列NUMERIC与模型Uuid类型差异：HEAD原双head首先阻止升级；只加本次无DDLmerge后同类型差异仍复现（`api-head-merge-baseline.log`），不是新知识表错误。真实隔离PG升级已成功。

扩大pytest七文件：23 failed / 68 passed / 334 subtests passed，37.90s（`api-knowledge-regression.log`）。23失败全部来自既有 `test_run_acceptance.py` 的fake thread缺thread_id；用HEAD源码及HEAD tests重跑该文件23 failed / 9 passed，7.08s（`api-head-run-acceptance.log`），失败node ID集合完全一致。去掉该已确认基线文件后的六个相关文件59 passed / 334 subtests passed，30.34s。

unittest命令曾带不存在模块而报错，前面的24项成功只计已执行部分；另有unittest执行pytest函数文件显示0测试，该输出不作为任何通过证据。以上问题不修改知识契约，不掩盖全仓门禁未绿。

### 静态与文档基线

`scripts/local_stack_processes.py`有4项原有BLE001/S110；本次新增导入已整理，未清理无关错误。知识登记脚本和其测试Ruff通过。

全仓 `scripts/check_docs.py` exit1：44条，42条既有问题＋本专项README的2行真实本机目录。用户明确要求说明worktree/知识源码目录，因此这2行按用户要求保留并记录例外，未改checker。FEATURES有4个HEAD既有失效目标，本次不顺手修；新增链接、围栏、引用文件/符号与状态一致性定向检查通过。

定向核验最终覆盖21份改动Markdown/40个新增本地链接/10份fixture；13个实现文件的20个引用符号存在，Phase16行与tasks16完成卡相等。增补JWT/SSE及规范导航后已重新核验，结果留 `.local-stack/evidence/knowledge-docs-targeted-final.json`（早期18份/35个链接结果另留）；未把用户要求的两目录例外说成checker全绿。

## 复验命令

文档不带RTK前缀；实际本轮shell执行均通过RTK。进入对应源码目录，用本服务独立环境和frozen锁；地址从登记读取，不套用主工作区。

K完整测试：

```bash
uv run --frozen --group dev python -m pytest "tests" -q
```

Platform API相关六文件（pytest能收集unittest类与pytest函数）：

```bash
PYTHONPATH=. uv run --frozen python -m pytest "tests/test_plan_mode_gateway.py" "tests/test_knowledge_mcp_bindings.py" "tests/test_runtime_delegation_contract.py" "tests/test_execution_budget_projection.py" "tests/test_thread_fork.py" "tests/test_tool_restrictions.py" -q --tb=short
```

Runtime相关七文件：

```bash
uv run --frozen pytest "tests/runtime/test_tool_governance.py" "tests/services/test_plan_mode_graphs.py" "tests/tools/test_knowledge_result.py" "tests/tools/test_knowledge_http_contract.py" "tests/services/test_knowledge_composition.py" "tests/services/dearflow_agent/test_mcp_tools.py" "tests/middlewares/test_tool_output_budget.py" -q
```

真实平台验收（会创建本任务测试Thread、临时撤grant/策略并finally恢复、重启所属Worker；需要本环境当前样本/测试身份及模型额度）：

```bash
KNOWLEDGE_PLATFORM_LIVE=1 uv run --no-sync --frozen pytest "tests/e2e/test_knowledge_platform.py" -q -s
```

知识启停/版本回退按[deployment-runbook](deployment-runbook.md)，前端同事按[frontend-handoff](frontend-handoff.md)。不在其他worktree执行本任务私有runner。

## Final 验证记录

未执行统一全栈Final。当前V1B仍受真实兼容环境/资料阻塞，F1B由前端同事接续；上面的扩大回归、真实Worker链及重启都是本轮Phase证据，不搬入Final或宣称可合并/生产发布。补齐条件后先更新tasks/状态，再按治理门禁收口。

## 完成度判定与Block请求

- **本轮文本非前端范围：done。** 16项可执行任务完成，部署/协议/安全/真实模型/持久性证据齐，服务与前端交接可用；相关测试通过，全仓旧失败另外如实留痕。
- **专项总体：blocked。** B01为Intel macOS x86_64/Python3.13没有锁定Torch2.11 wheel，frozen documents安装/dry-run实际exit2；证据 `.local-stack/evidence/knowledge-documents-install.log`。已采用独立基础环境完成文本链，未擅自降低Python/核心锁或引入Docker。需可访问ARM Mac或受支持Linux环境/指定运行方式完成PDF与Office输入验证。
- **B02：blocked。** 缺10–20份代表性业务资料及30题标注/预期来源；已用3份合成md/真实模型做可执行隔离、无答案和提示注入验证，无法代替业务质量。需用户给资料路径、标注问题/目标来源及允许使用的模型环境。
- **F1B：本轮排除。** 用户指定同事负责前端开发/浏览器，交接与转发话术已交付；这不是把本轮可执行后端事项推迟。

README/plan/tasks/CONTEXT与本记录同为blocked；Phase16条与完成卡16项相等。JWT/SSE仅补本次证据并刷新核验日期，原门禁未齐且blocked不触发毕业；Worktree规范本来active。经验提案由最终汇报提出，等待用户确认后才写lessons。
