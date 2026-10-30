# Phase 5：信息保留、请求测量与结构化交接

## 范围与状态

2026-10-29，用户批准后在既有隔离Worktree实施T5.1–T5.6。当前实施中；本记录不代表原题质量验收通过，不进入Final。主目录仅维护文档，应用源码在`/Users/lijiaxin/.codex/worktrees/subagent-baseline-20261028/ai-agent-platform`。已有改动不重置；本轮前置哈希保存在所属`.local-stack/v25-before-manifest.json`。

## 已实施的最小改动

- `observability/usage.py:_request_profile()`：在模型callback记录system/user/assistant/tool/other计数、字符/字节、Schema大小和哈希；不输出正文或参数。不改变公共Usage字段；来源不能识别时保留unavailable。结构化response_format一并测量并进入显式费用预留估算，估算不冒充供应商计费实数。
- `middlewares/filesystem.py`：提示文字计入总限宽，修复200行×100字符在4800上限下返回10237字符的缺陷；移除仅凭归档提示跳过guard。复用SDK保存与内容哈希路径；grep/glob/ls允许外置，read_file不再次外置，Command和非文本块保留。
- `middlewares/tool_output_pruning.py`：源码默认门槛300→8192字符；压力时旧大结果保留最多5120字符实质首尾和回读位置，没有可读归档时明确需重读原来源。纯投影不计事件，仅实际请求变更计数。隔离env仍需校准，隔离env已校准：动态外置阈值、24000字符展示上限、8192字符压力剪枝门槛。
- `dearflow_agent/prompts.py`：足够的现有可见证据可直接复用，仅缺原文/限定/支撑或冲突时批量补查，取消每原问题强制重读。
- `subagents/report.py`及两个只读角色：复用SDK ToolStrategy/structured_response（ProviderStrategy供应商诊断失败，见下），最多5条发现，保留claim/conditions/sources/confidence/unresolved，序列化≤4800。无来源的发现只能unknown。无新依赖、调度器或额外审稿LLM。
- `tools/errors.py`：只读子报告结构校验失败明确返回未完成，不把超长JSON首尾截断后当成功。未知程序错误及取消继续传播。

## 当前验证证据（Phase）

- 初始红测：`.local-stack/v25-initial-red.log`，5 failed；含真实限宽缺陷及未实现的计量断言。
- 工具输出/剪枝/计量：`.local-stack/v25-output-regression.log`，68 passed、5 warnings、7.47s、exit0。
- 首次交接组合：`.local-stack/v25-handoff-regression.log`仅打印`..`后人工中断，exit130；不计通过。旧fake model输出纯文本，已改为与新契约一致的JSON后逐项验证。
- 结构化正常实际图单例：`.local-stack/v25-handoff-single.log`，1 passed、9 warnings、6.54s、exit0，保留3并发/第4排队/原始证据隔离等断言。

## 继续项

完成失败/超长/取消/末轮、隐私、恢复与预算回归；完成v23离线审计及按需装载核对；基于矩阵校准三个既有参数；真实正式路径验证供应商结构化支持及完整烟测；冻结两臂六次，失败原样保留，原题通过后再做公开仓库泛化。尚无本轮真实模型质量改善证据，不提交、推送、合并或部署。

## 兼容缺陷与修复（继续实施）

- ProviderStrategy真实Web短探针Run `6c1202b6-35cc-4bcf-9216-2fe204f16886`失败，子报告结构错误并出现重复委派；独立公开事实诊断HTTP200仍返回Markdown，不能视为原生JSON Schema兼容。证据`v25-schema-smoke-raw.json`、`v25-provider-probe.log`保留。
- 切换ToolStrategy后，末轮仅暴露ResearchReport声明Schema，不允许任何执行工具；RuntimeConfig仅在SDK已解析structured_response时放行该报告envelope，执行权限不扩张。
- 第二短探针Run `ddb7000b-005c-445b-923f-796c5dc58228`为success且Usage4/4完整，但父工具结果仍是普通Markdown。SDK缺少structured_response时会静默回退文本，因此这次**交接失败**，不计质量通过。证据`v25-toolstrategy-smoke-raw.json`。
- 新增ResearchReportMiddleware，在子图结束时拒绝缺少合法ResearchReport的结果；两角色通用协议要求调用报告Schema，任务描述不覆盖交接格式。不额外调用LLM、不解析普通文本伪装成功。真实图plain_text负例先复现1 failed，再修复。
- 子报告/权限/取消/并发/末轮/预算/工具错误组合：`v25-report-enforcement-regression.log`，111 passed、1 skipped（20.85s）。跳过项不计通过。
- 真实HTTP/PG/Redis/Worker恢复、重启、权限与回滚：`TOOL_ERROR_PLATFORM_TEST=1 uv run pytest tests/e2e/test_tool_output_budget.py`，`v25-tool-e2e-4.log`，1 passed（138.57s）；前三次fixture失败日志保留。
- 预算矩阵180 cases，其中calibrated45，超预算0；证据`v25-budget-matrix.log`与矩阵JSON。128K/8K输出时动态spill约7680估算Token，展示≤24000字符；原来的1200/4800/300会过早丢弃大结果实质内容，故在修复硬上限、可回读和压力剪枝后沿用已有参数校准，不增加限额层。
- 请求组成日志改用独立私有INFO logger，宿主structlog配置不再吞掉诊断；只存元数据，无正文/参数/Schema原文。GitHub按HTTP捕获bytes、适配后chars/bytes分别记录，filesystem记录限宽视图；模型callback为请求组成边界，未知技能来源、供应商隐藏注入及多模态Token不硬分摊。
- v23离线审计：`25-v23-context-audit.json`保留六次失败及unknown。串行首轮68个读取窗口、2164行观察、842重复行；重复不自动等于浪费，按SHA/path/namespace/区间分类。已核对技能目录为request.override投影，不是每轮追加checkpoint；图表Schema仍按成功读取门控，暂无重复装配证据，不另改框架。

尚待：最新真实短探针严格JSON校验、原题完整烟测、冻结六次对照与另一仓库泛化；上述回归不代表真实质量改善。

### 严格交接短链已通过

Run `8351792f-03b1-46e3-ad8c-9ca7c9b31cfa`，Thread `3e35cf8d-f384-4892-b3d7-5d5bb0437a11`。正式Web入口沿用xiaok DeepSeek、Pro、8192输出，父task内容经`ResearchReport.model_validate_json()`成功校验，2789字符、4项发现均有conditions。Usage200/available/finalized，7 observed/7 reported、missing/incomplete均0、token_budget=null。全scope输入65,247、输出4,319、总69,566，费用无价格故unknown。仅为交接兼容短链，不计入正式六次或原题五项质量。

证据：`v25-report-guard-smoke-raw.json`、`v25-report-guard-smoke-audit.json`。新GitHub HTTP捕获→适配→filesystem视图→模型callback的私有元数据已在该Run实际采到，可由run_id/tool_call_id/namespace关联；没有保存正文到新日志。计量及GitHub/工具回归`v25-metrics-regression.log`：101 passed。

### 扩大回归与当前环境边界

- `v25-current-phase-regression.log`：595 passed、2 failed、49 skipped（200.61s）。一项是旧子研究错误夹具仍用普通文本，已改为带unknown/未解点的合法ResearchReport；修复后`v25-broader-fixes-2.log`：41 passed、4 skipped。首次修复命令误写测试路径，`v25-broader-fixes.log`为no tests ran，不能算通过。
- 另一失败是既有`test_docker_preserves_nonzero_and_timeout_results_without_repeat`：Docker daemon未运行，真实`docker info`确认不可连接。未为只读研究擅自启动Docker；该项仍未验证，不能写全量全绿。所属local Runtime正式链路不依赖Docker。
- 加严格报告交接后重新执行真实工具恢复E2E：`v25-tool-e2e-final.log`，1 passed（192.11s），覆盖独立HTTP/PG/Redis/Worker恢复和回滚。
- Ruff：`v25-report-ruff.log` exit0。技能快照进程重启另用所属隔离DB临时schema验证，不使用主库，待结果追加。

### 原题完整烟测失败与有界格式纠正

Run `2af96503-2005-4daf-98ab-61efca7f89c7`，Thread `4957f26a-eb8b-43d2-b7a4-00a9327cb86d`。终态success只代表运行结束：三个子任务中两个交接失败，原题质量不通过，正式效果组尚未登记/启动。原始记录`v25-full-smoke-terminal-read.json`及audit/report保留，不覆盖。

- 通过所属隔离PG checkpoint的`__error__`实际确认：一子`Report exceeds 4800 characters`，另一子`findings.4.sources`为5条、超过4条。不是上下文溢出，也不能仅凭父答复把它称为模型额度不足或普通文本回退。
- 父因交接失败补查，primary 12 calls、累计输入303,713、峰值36,396；全scope 43 calls、776,028 Token、Usage43/43完整、root自动摘要0。窗口低并未换来完整可靠交付，因此不算验收通过。
- 复用SDK ToolStrategy已有handle_errors反馈，让模型在现有16次上限内纠正非法报告；固定短反馈不泄露异常原文，不额外加审稿模型、不新增额度或重派同任务。到上限仍不合法、纯文本或取消继续明确失败。
- RuntimeConfig仅允许SDK已解析报告或已按相同schema名/call ID处理过的反馈envelope；报告仍不可作为执行工具。匹配/不匹配ID、夹带未授权执行工具均有权限回归。
- 新单例证明非法→纠正→合法消耗现有2次额度且保留条件；全图超长负例直到原上限退出，其他三个子任务成功。重试时update会重放此前来源artifact，验证按namespace/path/hash去重并额外断言真实来源调用恰好四次，不误判重复artifact为重读。
- 前两次格式纠正回归失败日志保留：第一次2 failed/82 passed/1 skipped；第二次1 failed/86 passed/1 skipped。待最终回归和真实复测结果再追加。
- 技能快照真实进程重启（所属隔离DB临时schema）：`v25-skill-restart-pg.log`，4 passed（97.35s）。扩大本地回归修复夹具后：`v25-current-phase-regression-2.log`，596 passed、49 skipped、1 deselected（Docker daemon未运行的既有测试单列）。

- 有界纠正最终组合：`v25-schema-correction-regression-3.log`，87 passed、1 skipped（39.64s）；`v25-current-ruff.log` exit0。第二次原题完整烟测已启动，仍独立于正式六次。

### 请求组成审计与装配核对

`audit-context-metrics.py`把模型callback元数据与供应商账本按call ID关联，原题首次烟测43/43覆盖、未缺profile；共HTTP捕获2,843,701 bytes、适配后227,514字符、工具展示232,375字符。该次无真实spill/展示截断/压力剪枝，日志的stage=spill但archived=false只是检查，不算外置。供应商隐藏输入、技能来源细分、多模态Token及HTTP捕获前内容均unknown，不把各阶段字节与字符混加。

primary的12个请求均1条system、17,365字符、40个Schema；subagent均1条system、2,088字符、6个Schema。支持“未随调用追加增长”，不证明每个字都无冗余；结合现有override与技能快照恢复证据，当前无需再改装配。原始细项在`v25-full-smoke-terminal-read.json.context.json`。

最新完整本地专项：`v25-corrected-phase-regression.log`，600 passed、49 skipped、1 deselected（183.90s）；Docker未运行项仍单列未验证，不声称全仓全量通过。T5.1–T5.5完成的是实现/契约/测量及接线，原题效果质量仅由T5.6判断。

### 第二次完整烟测与复用规则矛盾

Run `ba2eb26c-dfae-4c7f-8630-725a8ff128a2`，Thread `a8eb3a5c-e563-4afa-9549-c6e7aefdc5a4`，三个子报告全部合法（4567/3813/4753字符），供应商格式链路修复有效。但最终表格仍遗漏subagent概述中的可选/主循环外定位及父级发现等原验收限定，故不判五项全通过，未开始正式六次。

全scope40 calls、输入762,251/输出36,281/总798,532；primary12 calls、累计输入369,981、峰值47,730；Usage完整、root自动摘要0。40个引用均在实际观察窗口中，但引用存在不等于语义覆盖。证据`v25-full-smoke-2-terminal-read.json`及audit/report/citation-windows/context派生产物保留。

进一步找到通用复用规则矛盾：父上下文按隔离设计不接收子原始工具历史，而旧提示词把“原文缺失”设为补查条件，导致有完整有界子报告也逐条回读。已改为按具体引用、限定一致性、冲突或真实缺口决定补查；不因为父未重放子历史就回读，也不把文档研究扩成源码审计。概述优先保留默认/可选状态、架构位置和使用方可见能力，再删参数/接口支线；没有把本题答案、路径、行号注入运行时。

此为通用收敛规则修正，仍须独立完整烟测，再冻结两臂全部公共实现。前两次诊断不混入六次，不以最终success替代质量通过。

### 第三次完整烟测与源码页适配瓶颈

Run `65aba2e7-8811-448b-b8c6-f955af68f5d1`，Thread `13f67de0-e52b-47b8-bd2b-b421bb3fe4cb`。最终明确了subagent的可选/主循环外定位，但把compaction基础配置默认启用记为未知，父可发现子级也未交代，仍未达到原五项门槛。正式六次未开始；不以缺少源码审计为由删除文档已能支持的结论，也不降低验收。

- Usage47/47完整；primary10 calls、输入283,556、峰值45,453；全scope输入898,344、输出47,657、合计946,001；root自动摘要0。
- 76个实际读取窗口，39个最终引用均被窗口覆盖；这只证明观察过引用范围，不证明各结论完整正确。证据为`v25-full-smoke-3-terminal-read.json`及audit/report/citation-windows/context派生产物。
- 请求profile47/47对应账本；HTTP捕获200次、3,050,150 bytes，适配91次、257,716字符，模型工具视图270,095字符；真实spill、展示截断、压力剪枝均为0。瓶颈不能归因于本次上下文压缩。
- 实际`github.py`在通用展示上限24000字符之前仍把每个源码窗口截在3000字符。红测用200行、每行约100字符的普通文档复现仅返回28行，`v25-github-page-red.log`：1 failed、30 deselected。这会增加续读机会和每轮历史重传；真实收益仍待复测，不据此预宣称因果。
- 在T5.3已有授权范围内将该现有窗口校准为12000字符，统一查询前置上下文与长行切片的边界，仍至多200行、保留真实行号/next_line/line_truncated、原文hash和通用guard；不加环境变量或另一层限额。新增测试要求普通200行两页完整覆盖、超长行如实标记并可续读；与中文/查询坐标/错误及其他读取回归一起执行。
- 修复后GitHub组合31 passed（9.70s）；工具/报告/装配/剪枝/限宽组合108 passed（31.54s），Ruff通过。API原预算投影37 passed、266 subtests passed（2.56s），Web预算视图21 passed（3.75s）。这些均为定向Phase检查；pnpm配置提示与既有序列化/弃用warning未当作零告警。
- 使用所属脚本只重启Runtime API/Worker后，通过正式Web启动第四次独立原题烟测，Run `f9075d3e-77ef-48b5-8b86-fc02cc93dcb6`；未混入正式六次。另一公开仓库的题目/评分在模型运行前预登记于`26-generalization-preregistration.md`。

### 第四次烟测结果与委派提示的通用收敛

第四次Run `f9075d3e-77ef-48b5-8b86-fc02cc93dcb6`经正式Web→API→Runtime终态success，Usage37/37完整、root摘要0。全scope输入822,126、输出45,493、总867,619；primary 9 calls、输入268,531、峰值46,520；subagent 28 calls、输入553,595、峰值42,298。较第三次调用47次→37次、总输入898,344→822,126，但这是不同烟测的观察差，不构成因果或正式效果结论。

- 3个code_explorer真实namespace；source audit核实62项来源原文hash/fixed SHA，全通过；root、子工具权限符合白名单。引用窗口55个、最终引用46个，窗口未观察到的引用为0；自动审计仍发现正文有`README.md#L74`等省略完整路径的歧义引用。
- 质量仍失败：报告说明continuable子可被父发现，但未完整说明subagent位于主agent loop之外；不得以“可选能力缝”替代明确架构位置。默认挂载结论有组README支持，但基础preset未核；按评分表应标文档声明/运行时配置未知，不能把文档文字说成已实证装配。
- 轨迹中主Agent把用户问题扩成逐子包package.json、实现源码与注册点清单，导致handoff报告过细；最初任务Schema/默认描述明确鼓励详细任务prompt。作通用收敛：主提示要求委派仅含对应问题、来源约束、交付格式且最多三句，不重复评分表；最终引用必须每次使用完整仓库相对路径和行号。未加入本题评分答案、路径、引用或行号。装配断言2 passed、Ruff通过。
- 当前只完成测试与提示词修正，第四次之后的效果尚无证据；需第五次独立烟测判断是否改善。第四次原始账本、报告、source/context/window audit均保留。

### 第五次烟测：父级重新研究与整合遗漏

Run `54eff865-88c9-4cfb-8252-858b3884e7e3`，Thread `b2862196-5257-4692-9567-c32ecd9b49bd`，终态success、Usage43/43完整且账本对平、`token_budget=null`。primary 11次，输入359,125、峰值51,847（配置窗口39.6%）；subagent 31次、输入590,488；auxiliary摘要1次，输入17,632。全scope输入967,245、输出52,551、总1,019,796，耗时458.30秒。root自动摘要1，未达既定零摘要门槛；不因为总量超过旧1M而判费用失败，本组费用限额已关闭。

- 三个真实code_explorer仅用github_query；75份来源固定SHA、hash与本地git blob通过，43/43请求组成可关联。无实际spill、展示限宽或压力pruning。
- 引用审计的42个去重引用在56个观察窗口中；其中13处`#L...`沿用同一行前面的明确路径，审计器可解析并核对，不能误称为虚构或未知引用。它们未遵守新提示的完整路径格式，但不据此追加原验收门槛。来源存在与结论完整是不同门槛。
- 报告仍未明确随附基础配置默认启用、subagent在主循环外以及父可发现子级等完整限定，质量失败。实际子报告第一条已经写出“Optional seam outside the agent loop”，另一个报告也写出默认基础配置和discovery；证明传输后父级整合仍可丢信息，不能以JSON合法宣布语义可靠。
- 父级收到三份报告后又调用27次github_query，细化参数/exports/权限接口；短委派规则也未阻止任务被扩成审计清单。SDK原生task描述包含“Put full detail in the prompt”“relay a summary yourself”，与本项目的简洁委派和完整限定保留存在冲突。该轨迹支持具体矛盾存在，不足以证明它独立造成全部失败。
- 本次在现有`middleware/delegation.py:DelegationConcurrencyMiddleware.awrap_model_call()`只复制模型可见task描述，保留原SDK工具handler、args_schema、状态隔离、执行/并发和权限；不注册全局HarnessProfile，不替换SDK调度，不新增审稿调用。描述统一对应原问题/来源/格式、最多三句，整合优先保留直接回答问题的结论和限定。`ResearchReport.findings`仅补字段说明，要求直接答案先于可选参数清单，不增加字段或本题答案。
- 专项测试先红：`v25-delegation-description-red.log` 2 failed；修复后`v25-delegation-description-green.log` 43 passed、1 skipped（46.57s），Ruff通过。验证工具描述拷贝且不改原工具/消息/handler、task不可见时不新增工具，并在真实图测试中核对供应商绑定到的描述；覆盖父子隔离、取消、失败及预算。第六次独立完整烟测Run `651df39e-5ebd-4b54-a6ed-c80d4ddfbf25`、Thread `6f8ae800-14c4-401d-bfac-955775710268`已通过正式Web启动，等待终态质量审计；本次及此前全部失败原样保留。

原始证据：隔离Worktree `.local-stack/v25-full-smoke-5-terminal-read.json` 及其 `.audit.json`、`.report.md`、`.context.json`、`.sources.json`、`.citation-windows.json`。正式六次尚未冻结，不计入效果组。

### 第六次烟测终态补记

上述第六次烟测现已完成，Usage35/35完整、root自动摘要0、主峰值29,218/131,072=22.3%，总723,173 Token；原五项评分3/5，仍漏较早历史摘要与父级发现。第六次完整原始/audit证据保留，详见[逐项评分与技术审计](27-phase5-smoke6-review.md)。第五次之后的“等待终态”是当时状态，现以本补记及tasks.md为准；正式组与Final仍未开始。当前主链路无需Docker，额外容器补测已停止，相关项保留未验证。
