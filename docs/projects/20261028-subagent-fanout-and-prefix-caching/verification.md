# 验证计划与记录

> 当前状态：`done`（当前用户批准的简化实现与工程验证），用户于2026-10-30验收通过；所属服务已停止，功能分支已推送并快进合并main，Worktree及两个专属数据库/角色已清理，收尾记录随main提交推送。相关回归、额度失败隔离及正式链路已验证；最后一次原五项明确语义覆盖3/5，不能判为原语义稳定性门槛通过。四次独立烟测和旧v50–v53全部保留，不宣称费用收益或25%同质量降幅；未提交或部署到共享环境。

## Phase 验证记录：Open SWE 方向的最小委派（2026-10-30）

- **S1 删除自研交接：通过。** 撤除5个模块和6个专属测试/夹具，删除前备份计973行实现、1720行测试；Runtime src/tests旧报告模块及类引用零匹配。
- **S2 普通文本与安全组合：通过。** 275 passed / 12 skipped覆盖主/子图、普通文本、共享预算、PII、模型容灾、工具限宽、三路并发和父级取消的组合；跳过项不计通过。
- **S3 只读工具接线：通过。** compiled graph先复现目录/GitHub四项权限失败，修正工具实例、RuntimeConfig和PlanMode三处后ls/read_file/glob/grep/github_query五项通过；保留项目授权及禁止写入/执行/嵌套task。
- **S4 定向复核与交付提示：已验证，有质量局限。** 最短回归53通过/2跳过；最后独立烟测完整收尾且无缩写路径歧义，但原五项明确语义覆盖3/5。没有创建todos，不把通用提示当作待办跟踪已验证。
- **S5 官方子工具额度失败隔离：通过。** 第二次真实Run因48次工具额度异常穿透error，保留完整用量未知；红测3失败/17通过→绿测20通过，含兄弟证据保留的额度组合5通过。主级超额、权限/PII/取消/全局预算及未知异常继续传播。
- **S6 规范与状态：通过。** Runtime开发标准、README/plan/tasks、CONTEXT、FEATURES和CHANGELOG已按当前简化实现更新；旧结构化方案保留为已取代的历史。当前未新增JWT或SSE契约，无相关草案毕业。
- **S7 相关回归：已执行。** 282通过/12跳过；扩大27文件回归560通过/13跳过/1失败，唯一失败在默认Docker环境，显式local后端单项复验1通过。失败/skip原始日志保留，不改业务代码或测试断言，不写成一次全绿。
- **S8 同步与正式链路：通过工程烟测。** 所属Runtime已精确同步并重启，四次正式Web→API→Runtime独立烟测保留。第三次success但输出截断、语义4/5；第四次success、226.27秒、三子完成、28/28 Usage完整、主峰31.1%、root自动整理观测值0、最终正文完整；语义3/5。详见[66号](implementation/66-open-swe-delegation-simplification.md)。

## Final 验证记录：2026-10-30当前简化范围

**状态一致性：** tasks.md当前S1–S8全部完成，与本节8条Phase记录逐项对应；README、plan、CONTEXT均写明“当前简化实现与工程验证done、待人工验收”，不代表旧方案语义稳定性门槛通过。下方已取代的历史任务未勾选项不改写。

### 验证范围与方法

复用已安装DeepAgents的官方task与只读general-purpose，撤除自研报告/合成/原文校验；对本轮涉及的Runtime调用方、测试和组合链做相关回归，通过正式Web→API→Runtime验证真实委派及持久结果。没有新增依赖、公共API、JWT/SSE字段或数据迁移；本次Final只覆盖上述简化范围，不是全仓所有项目验收，不复用旧实现的质量通过记录。

### 单元与组合回归

- 27个相关测试文件：**560 passed / 13 skipped / 1 failed / 60 warnings，143.92秒**。失败项为Showcase真实Python执行测试默认选择Docker，当前栈backend=local且未启动Docker；默认配置单独复验仍失败，失败证据保留。显式`RUNTIME_BACKEND=local`复验同一项 **1 passed / 5 warnings，5.87秒**，断言和业务代码未改；不将不同环境结果拼成一次全绿。
- 覆盖DearFlow角色/工具装配、模式、普通文本交接、共享预算、三路并发、父取消、失败隔离、PII、Usage、容灾、工具输出及上下文边界。新增官方子工具额度分支先红测再绿测，并验证父任务接住失败且兄弟结果保留；主级、安全及未知异常继续传播。
- 13项跳过明确不计通过：1项真实Tavily、1项Langfuse、9项独立PG/Redis Worker取消/重试/冷却测试、1项Showcase真实模型、1项独立HTTP/Worker重启/ACL/回退测试。当前取消/权限/预算等有compiled graph和组合回归，以上被跳过的特定外部环境场景没有本轮新证据；不以正式研究烟测替代它们。
- 本轮最终48份变更Python文件Ruff通过，主目录`git diff --check`通过。最初`uv run --no-sync ruff`因当前服务环境未安装该CLI启动失败，改用已有缓存的`uvx --offline ruff check`通过，未添加项目依赖。
- 调用前登记的272份源码SHA256在终态后无漂移，主目录与所属Worktree一致；没有仅凭运行成功推定服务加载的是新代码。

原始日志/JUnit：所属Worktree `.local-stack/open-swe-simplified-final-regression.{log,xml}`、`open-swe-showcase-execution-recheck.{log,xml}`、`open-swe-local-execution-recheck.{log,xml}`；最终静态检查与源码核对为`open-swe-final-ruff.log`、`open-swe-final-source-check.json`。

### 正式端到端结果

最后一次Thread `1ccc5abf-0043-402e-aa1d-ac2694a22131` / Run `9856913c-d061-4b76-8adc-4e4cf4e61da1`：

- 正式Web新对话选择xiaok `deepseek-v4.1-flash` / Pro / 8192输出；固定公开DSH SHA，三真实general-purpose均完成，226.27秒终态success。API持久状态与最终报告可读取，正文12,725字符、`finish_reason=stop`、完整收尾；截图已人工查看。未创建todos，本轮不证明待办跟踪。
- 28/28调用Usage完整且finalized，missing/incomplete=0、未降级、`token_budget=null`。主7次调用、累计输入191,773、峰40,707/131,072（31.1%）；子21次调用、累计输入269,416、峰32,600；全Run输入461,189、输出36,642、总497,831 Token，cache_read255,232。价格未知。
- 完整root running→completed捕获中未过滤custom、未观测offloading，root自动整理观测值0；这不是所有任务都不会压缩的保证。52份来源原文/固定SHA/hash和README目录核对通过；74个可解析范围中73个已读，另1明确标为未读，不当作支持结论；缩写路径歧义0。
- 原五项最终正文完整语义覆盖 **3/5**：#1/#2/#3通过；#4缺agent loop之外的可选能力限定，#5有fresh/fork和外部provider但未明确父级可发现其子级。模型自述部分工具调用次数与事件不符，也保留为质量局限。不能以来源真实、Run success或低占用判为内容全对。
- 第一轮语义错误、第二轮额度异常穿透失败、第三轮语义4/5且输出截断、第四轮3/5均保留。四次是逐次配置变化的独立烟测，不替补旧冻结组、不混算收益、不继续采样凑成功。

逐项来源、引用、用量、事件与截图证据见[66号](implementation/66-open-swe-delegation-simplification.md)。本轮只作实现及工程交接验证；没有同条件DSH截图会话对照、同质量两臂实验或泛化数据，不能声称复现DSH的累计成本、稳定质量或25%主输入降幅。

### 服务交接与边界

所属环境 `wt_bf33bcf838fd`：Web `http://127.0.0.1:29201`，API `http://127.0.0.1:29713`，Runtime `http://127.0.0.1:26751`。仅所属`local-stack.sh`管理，Runtime API/Worker已同步重启，当前五服务running、Runtime ready、API健康；backend=local，未启动Docker，保持服务供用户验收。没有修改生产环境、提交/推送代码、回滚其他既有修改或删除历史数据。

**结论：** 当前用户批准的简化开发与工程验证`done`，已获用户人工验收；原语义稳定性门槛未过，特定外部环境跳过项、跨任务泛化、统计收益和费用保持未验证。回退可使用本轮精确备份恢复源码及所属Runtime，当前未执行实体回退演练，且不声称已验证回退；本轮不涉及依赖或数据库迁移，历史Run/来源保持不动。

### 人工验收与收尾（2026-10-30）

用户明确确认本需求验收通过，并授权停止服务、提交推送、合并、清理Worktree及相关开发测试数据库。功能提交`e40742baa14082c7dcab8765b152325b16305e90`已推送独立分支并快进合并main；逐项核对原主目录61份代码/测试/配置，内容一致或Python AST等价，仅提交钩子格式化，无覆盖原有功能。

所属五服务全部stopped；数据库`wt_bf33bcf838fd_runtime`和`wt_bf33bcf838fd_platform`及同名角色已通过带归属校验的destroy删除，其他57个数据库定义与清理前一致；29201/29713/26751/28302监听已释放。关联Worktree及隔离资源登记已移除。验证材料3877份另存`/Users/lijiaxin/.codex/task-evidence/20261030-subagent-fanout-closeout/`，失败证据不随数据库清理丢失。

本轮收尾仅更新文档并合并已验收代码；原模型语义评分、skip与未知费用保持原样，没有以人工验收替代未执行的测试。main推送后以远端SHA回查确认，本地机器记录在上述归档目录，详见[67号](implementation/67-acceptance-merge-and-cleanup.md)。

---

下方v53及更早记录仅保留原方案事实；当前进度以tasks.md顶部有效任务区为准，历史“Final未开始/进行中”等表述只描述其当时组别。

## Phase：v53六次冻结对照终态与定向回归（2026-10-30）

- 委派三次为5/5、2/5、4/5，Usage均完整，root自动摘要均0，主累计输入29,688、98,067、30,110，峰值17,495、20,769、17,917。仅1/3达到五项语义质量。
- 串行1成功：7/7 Usage完整，主累计输入139,884、总Token146,073、峰值27,558；固定SHA与14条引用窗口审计通过，人工评分2/5。串行2错误终态：`runtime.execution_failed`；4次primary调用仅1次有Usage，已知输入11,877、总量未知，无最终报告，记0/5且不替补。串行3成功：10/10 Usage完整，主累计输入216,999、总Token227,471、峰值29,559；固定SHA与11条引用窗口审计通过，人工评分2/5。
- 串行质量0/3，两组没有同质量结果，不计算或宣称25%主输入降幅。v53原始样本及审计留在所属Worktree `.local-stack/`，详见[65号记录](implementation/65-v53-controlled-validation.md)。
- 隔离Worktree定向回归：`uv run --no-sync pytest tests/services/dearflow_agent/test_research_synthesis.py tests/services/dearflow_agent/test_research_report.py tests/services/dearflow_agent/test_source_context.py tests/services/dearflow_agent/test_source_quotes.py tests/services/dearflow_agent/test_subagents.py -q` → 103 passed、1 skipped、59 warnings（24.43s）。此为Phase回归，不替代真实质量门槛、泛化或Final。
- 隔离栈由 `scripts/local-stack.sh status` 确认五服务运行：Web `http://127.0.0.1:29201`、API `http://127.0.0.1:29713`、Runtime `http://127.0.0.1:26751`；Web返回200、Runtime `/ok`返回`{"ok":true}`。Docker未启动。当前T5.6/T3.2质量门槛未过，泛化与Final未完成。

## Phase：v51完整结果与只读循环隔离（2026-10-30）

- 六次终态完整保留并复核无漂移：委派5/5、5/5、0/5，串行4/5、4/5、3/5；完整质量2/3与0/3。委派3与串行1完整Usage未知，不把已报告量当总量；无同质量降幅结论，见[63号](implementation/63-v51-controlled-validation.md)。
- 组后修复已批准T2.2只读子任务隔离遗漏：精确loop错误停止该子任务并返回失败，兄弟任务和父级可继续；主级、鉴权/隐私/全局预算/取消不被吞。正式红测3 failed，绿测170 passed/1 skipped/89 warnings（46.11s），Ruff通过，四文件已核对同步；见[64号](implementation/64-readonly-child-loop-isolation.md)。
- v52独立正式原题Run 1b4f22e5-be1f-49c3-ba62-1d6116b48a53已5/5，三个code_explorer成功、27/27 Usage，主输入30,269/峰18,076、root摘要0；27份固定来源、交接去重/渲染及唯一最终流通过，全Run355,720 Token。修正后六次组v53已在首个模型调用前冻结并执行，见[65号](implementation/65-v53-controlled-validation.md)；稳定性、既有nanobot一次泛化和Final仍待验，当前六项待验任务不勾选。

## Phase：v50独立正式原题与v51冻结（2026-10-30）

- v50 Run 68bbfafa-baae-4d93-a2fa-05a77cf73bff：五项结论/支持引用5/5、三个真实code_explorer、34/34 Usage完整，主输入67,880/峰20,879，root自动摘要0；32份固定来源/24个显式行范围、有界交接与唯一最终流均通过。全Run总498,835 Token、325.04秒，不能据低窗口宣称费用下降。见[62号](implementation/62-bounded-document-intro.md)。
- 同版v51清单已于首次模型调用前冻结，六次按委派1/2/3→串行1/2/3执行；委派前两次5/5，第三次只读子任务实际循环停止异常穿过task边界，其他子任务中止、无最终报告，完整质量2/3未通过。主峰12,193、root摘要0，28调用仅26有Usage、完整总量未知；串行三次已终态4/5、4/5、3/5。旧失败不混算、不补样，组内不改源码或审计器；见[63号](implementation/63-v51-controlled-validation.md)。
- 独立烟测有一子耗尽既有16次调用、两子成功；父未重派，补读两份固定来源后正常交付，界面如实保留失败标记。不是三子全部成功。
- 当前冻结测试的扩大Phase回归：35文件672 passed / 16 skipped（222.60s），独立原生临时PG，未用Docker/业务库；跳过项不计通过。独立浏览器历史Run恰一条success、无重发/整理悬挂、390px无整页溢出，关闭侧栏后的报告截图已人工核验；详见62号。
- v51失败历史经独立浏览器复核：恰一条error Run、一子失败/两子中止，循环停止原因可见，无整理悬挂或自动重投；`.local-stack/v51-failed-history-browser-result.json`及截图留存。只读task循环隔离的无模型探针在旧实现明确失败，`.local-stack/v52-loop-isolation-probe-red.log`；六次冻结组结束后已接入修正并通过170项相关回归，真实效果待新组验证。


## Phase：v48 原题核验与 v49 新冻结组（2026-10-29）

v48 Run `4e799a78-a59f-4d16-a0ec-7b64d1cfbd6f` success，原五项语义/支持引用5/5；25/25 Usage、三真实code_explorer、28固定SHA来源与已读行通过。主累计输入30,260、峰18,095，root摘要0，有界原文交接1,785字符，单一最终流与checkpoint相等。附加provider限制引用粒度及driver并列表述局限如实保留，详见[60号](implementation/60-github-operation-and-fixture-correction.md)。1131公共文件、12测试、10审计器无漂移；一次烟测不替代稳定性。

v49首次模型提交前登记清单SHA256 `3da1bee0434a4bf7b3ddc69f68cddab6afaea8a587a1adc0bdaeab13d1f725d9`，固定委派1/2/3→串行1/2/3，只切Pro delegation，全部终态保留；见[61号](implementation/61-v49-controlled-validation.md)。泛化与Final尚未开始。

## Phase：v46 独立原题通过与 v47 冻结验证（2026-10-29）

v47三次委派均success、原核心语义5/5，完整质量2/3：第二次缺operation/ref/path的调用默认回退info，最终保留两条裸仓库来源，固定提交要求未过。三次主峰18,202/20,510/18,131，root自动摘要均0，Usage均完整；串行三次已success但核心语义2/5、3/5、1/5，完整质量0/3，六次全部保留。组后已接入缺参修复。逐项评分和失败边界见59号；不宣布稳定性通过。

交付纠错修复后，Run `cafac200-594b-4bc6-be9c-7e60ee9d75fe` 正式交付，原五项语义/引用 5/5，主累计输入 29,719、单次峰 17,570/262144，root 自动摘要 0，三个真实子 namespace，22/22 Usage 完整。24 条行引用均处于实际读取窗口，目录 tree 补充核验通过，交接与唯一最终流/保存报告一致。独立成功不当作稳定性；v47 已在首轮前冻结 1131 份公共文件、配置/模型/原题及验证器，依次执行委派三次→串行三次，见 [59号](implementation/59-delivery-convergence-controlled-validation.md)。

同版恢复 E2E 使用夹具自建原生临时 PG/Redis、local backend，HTTP/Worker 重启/ACL/中部回读/回退完整断言 1 passed（350.13s）；首次错误选择外供基础设施模式导致缺 POSTGRES_URI，启动前失败原日志保留。API 预算和 Usage 37 passed、266 subtests passed（15.05s）。Web全量927 passed/1 skipped，lint/类型/构建通过；扩大Runtime9 failed/651 passed/16 skipped，夹具及本地backend配置已定位，组后修正复验。这些均为Phase，Final未开始。

## Phase：交付纠错收敛（2026-10-29）

v45六次已全部终态失败，完整来源与Usage未知项如实保留，见[56号](implementation/56-pro-controlled-comparison.md)。组内公共源码无漂移；组结束后恢复Pro再接入57号候选。正式新增三项回归先失败；修复及夹具对齐后63 passed/7 warnings（40.29秒），Ruff通过。交付纠错只暴露报告Schema、拒绝执行工具、同Run反馈覆盖、新Run排除旧反馈，取消/单一流/预算与原验证保留，见[58号](implementation/58-synthesis-delivery-convergence.md)。主目录已同步，xiaok Kimi新独立正式检查已预登记，尚不能记稳定质量通过。

## Phase：v45独立正式烟测与六次冻结（2026-10-29）

探索角色与来源说明的通用澄清经88项回归后，独立Run `e8e23320-164b-4b7b-825f-7ffa14a783bf` 正常交付，原五项语义及引用5/5；38/38实际maomaoai/deepseek-v4-pro调用，Usage完整finalized，主累计输入134,936、峰30,733，总736,963 Token，root自动摘要0。三个合法报告、31份固定来源、原文限宽、单一最终流及重渲染通过，详见[55号](implementation/55-role-scope-and-pro-smoke.md)。目录坐标以独立固定提交树核对，保留原文件行号审计的未解析记录，不把目录当行为证据；目录1M窗口与供应商实际部署元数据未知单列，未将窗口变大归因代码优化。

在首次正式组调用前冻结[56号六次对比](implementation/56-pro-controlled-comparison.md)，委派1/2/3→串行1/2/3顺序执行中。独立烟测不混入正式组，组内不更改配置、不补样本；全部终态后逐次审计评分，再执行泛化与Final。本节仍为Phase证据。

## Phase：v42终态与原生HTTP夹具兼容（2026-10-29）

97项证据视图专项及66项调用方回归通过后，v42正式独立任务正常交付；34/34实际xiaok/kimi-k3，Usage完整finalized，总522100 Token、主累计45045/峰17881、root摘要0，三个合法子报告、32份固定来源、单一最终流及重渲染通过。但原质量仍4/5：父级可见性的引用范围未支撑该条件，另一结论错误概括上下文共享边界，父级全部接受。详见[53号](implementation/53-parent-coverage-independent-smoke.md)及所属原始八类审计，不能据格式/低占用判成功。

真实HTTP持久化/ACL/Worker重启/回退夹具适配现役overview与整合协议，原断言保留；旧夹具1 failed（390.87秒），修正后原生临时PG/Redis/local后端1 passed（208.17秒），Ruff通过、主目录同步，无Docker。[54号](implementation/54-http-fixture-and-clause-diagnostic.md)记录独立固定材料诊断，均为Phase，未进入Final。

## Phase：全字段引用反馈（2026-10-29）

Kimi原记录证实逐个校验错误消耗多轮调用。49号将同一报告全部无效引用字段按原因一次反馈，原匹配规则、2000字符回执和调用额度不变；父级15项/子级5项完整图均能在读取→无效交付→一次修正的3次既有调用内完成。旧实现红测3 failed；首轮修复93 passed/2 failed为新夹具误读私有字段，修正后95 passed/7 warnings（9.74秒），Ruff与diff通过。两份代码/测试及标准说明已同步，所属Runtime已重启，详见[49号](implementation/49-all-quote-feedback.md)。

新Kimi完整任务于调用前冻结，终态见[50号](implementation/50-all-quote-feedback-smoke.md)：28/28实际Kimi调用、Usage完整finalized，总416000 Token，主峰18075，root摘要0，三个合法子报告和单一最终流通过；原质量仍4/5。父级收到完整原文却未补缺，固定材料SDK覆盖诊断见[51号](implementation/51-parent-coverage-diagnostic.md)；新六次、泛化与Final仍待验，不以确定性通过代替。

## Phase：Step5初始化拒绝与合法配置登记（2026-10-29）

v38原8192输出在模型请求前被`runtime.context.output_budget_exceeded`拒绝，模型调用0，无可评分报告；当前解析器安全上限4096，已只读复核，未绕过guard或扩大目录。失败原始记录、Usage not_recorded及不适用审计说明见[47号](implementation/47-step-independent-smoke-registration.md)。这不是外部模型失败或Token预算耗尽。

保持v37应用、原题与评分，以4096新登记一次独立正式UI检查，见[48号](implementation/48-step-legal-output-smoke.md)。两种输出配置不混算，不替补，不提前记为正式组或Final通过。

合法配置后实际Step5请求全部失败，转入备用maomaoai DeepSeek；诊断停止，96项调用/49项缺Usage，Run总Token未知，已知和1082462不是总量。两个合法子报告、49份固定来源及96份profile保留，无最终报告，不能计为Step5质量对照；完整终态见48号。不改计数器或扩额，取消不冒充预算停止。

## Phase：v35纠错后GLM独立烟测终态（2026-10-29）

Run `38d9d8ec-f4ca-458d-872e-1eae9d1b9308`：三个code_explorer均耗尽原16次额度，合法报告0，确认失败后经正式接口诊断停止，终态interrupted。原五项均未通过，无最终合法报告；不将取消算作预算停止，不替补v34或v33。59次调用profile关联完整；账本未finalized、总Token未知。主峰30836/131072（23.53%），root自动摘要0；43份固定来源hash通过，其中31来自子级。低占用不代表质量通过。原始/审计摘要见[43号](implementation/43-draft-recovery-smoke-registration.md)。

下一步独立Kimi兼容性检查已在调用前登记于[44号](implementation/44-kimi-independent-smoke-registration.md)，保持v35应用和原门槛，仅用既有xiaok Kimi及其配置256K窗口。该次不构成正式六次或Final；报告绝对输入并注明窗口变化。

## 1. 验证范围

### Phase：目录/字段反馈与只读流中断隔离（2026-10-29）

真实Kimi烟测27次调用后因单子模型流中断进入error，两个子报告虽合法但无父最终报告，完整Usage未知，全部证据保留，见[44号](implementation/44-kimi-independent-smoke-registration.md)。据此修复既有目录quote误拒、overview/findings/additions字段路径、超额字符数反馈，以及只读子task精确流中断失败隔离；不改变原限额、报告字段、权限或评分。

首轮红测7 failed中一个夹具缺import，修正后隔离单测仍1 failed；首轮绿测1 failed/102 passed/1 skipped为旧错误路径断言，补齐后专项104 passed/1 skipped。扩大关联集478 passed/54 skipped/1 deselected/114 warnings，223.26秒，exit0；Ruff及两目录diff检查通过，8份修正摘要校验后逐字同步主目录，所属Runtime API/Worker已重启。详细日志与边界见[45号](implementation/45-evidence-feedback-and-child-isolation.md)。Docker未启动，跳过/未选项不计通过；不是Final。

修复后同模型/窗口/原题的新独立完整任务已先登记再启动，见[46号](implementation/46-evidence-feedback-smoke-registration.md)。只有该任务通过后才登记新六次组；泛化/Final保持未完成。

委派主体位于 apps/runtime-service；真实基线已暴露既有 API/Web 预算投影假设，前置修复纳入最短链路验证。必须覆盖 Runtime 预留、API Usage/SSE 校验、Web 通知解析，并通过 Platform Web 正式 Run 与 Usage 接口复验。如果运行于关联 Worktree，服务启停和 E2E 必须遵守 docs/standards/worktree-development.md 与 scripts/local-stack.sh。

## 2. 自动化测试

在仓库根目录执行：

- Dear Agent 与 Subagent：cd apps/runtime-service && uv run pytest tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py -q
- Token 预算与上下文治理：cd apps/runtime-service && uv run pytest tests/middlewares/test_token_budget.py tests/middlewares/test_tool_output_budget.py tests/middlewares/test_tool_output_pruning.py tests/middlewares/test_conversation_offloading.py -q
- 静态检查：cd apps/runtime-service && uv run ruff check src/runtime_service/services/dearflow_agent/modes.py src/runtime_service/services/dearflow_agent/agent.py src/runtime_service/services/dearflow_agent/subagents tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py

旧版v0–v23真实模型对照的运行配置（历史保留；新预算以T4为准）：

- RUNTIME_USAGE_ENABLED=1
- RUNTIME_TOKEN_BUDGET_ENABLED=1
- RUNTIME_TOKEN_BUDGET_MAX_TOKENS=1000000

2026-10-28 新基线登记：通过正式运行参数界面将 `context.max_tokens` 固定为 4096（单次输出上限，不是 Run 额度）；两个组均相同。此前默认输出上限参与保守预留，留下 24,488 Token 时仍可能拒绝下一次短答复。该修订只约束生成上限，不增加 100,000 Token Run 额度，不改变任务、模型和证据门槛；旧样本全部无效，须重新收集两组各三次。

Token budget 开启时必须同时开启用量采集。串行与委派组使用同一模型、同一 1,000,000 Token Run 兜底额度和相同上下文策略；任一 Run 的 usage 缺失或 invalid 即判该次结果无效。只在隔离测试 Runtime 配置这些变量，不修改主工作区或其他 Worktree 的私有配置。

若在关联 Worktree 执行真实模型对照，先运行 bash "scripts/local-stack.sh" init、deps、doctor、start、status，并使用 status 返回的地址；配置只写入该 Worktree 的 `.local-stack/runtime.env`。测试后只停止本环境服务，不销毁数据。主工作区和其他 Worktree 的服务、数据库、Redis、Workspace 不得复用。

自动化通过条件：

1. Flash、Standard 的 task 工具不可见；Pro、Ultra 的 task 工具可见。
2. code_explorer 仅可见批准的读取工具和受限来源证据记录能力；不存在 execute、write_file、edit_file 或 task，且不得修改用户文件。
3. 并发契约测试提交 4 个子任务：3 个同时活动，第 4 个等待槽位；释放一个槽位后第 4 个启动，峰值活动数为 3。
4. 子任务 namespace 互不相同；父 messages 不包含子 Agent 的原始工具消息或父会话私有输入。
5. 取消父 Run 会取消运行中的所有子任务；单个子任务失败不会导致其他结果被错误伪装为成功。
6. 主、子模型调用 usage 都按 namespace 记录，并共同消耗同一个 Run Token 预算；并发在途调用不得导致额度超调，额度耗尽后模型请求数不再增加。
7. 每个子任务交回的 ToolMessage 不超过有效输出上限；被限制时有明确截断标记，必需的来源信息在合格报告中保留。
8. 现有工具输出截断、ToolOutputPruning 和 ConversationOffloading 测试通过。

## 3. 真实模型对照（v0–v23历史配置与原质量门槛；新组配置见3A）

### 固定数据与任务

- 仓库：`https://github.com/deepseek-ai/deepseek-harness`，固定提交 `477b4f420553e8a52c2fbccc464d7561b239c443`。该 SHA 来自本地干净 checkout 的 `origin/master`；任务中的每次 `github_query` 必须传相同 `ref`，不可读取默认分支后再声称结果来自该提交。
- 三个互不重叠方向：能力包边界；compaction 触发和生命周期；subagent 能力与提供方边界。
- 两组使用相同的原始提示词、全新 Thread、Pro 模式、模型配置、上下文策略和 1,000,000 Token Run 兜底额度；唯一被测差异是委派组新增 task 入口和 code_explorer。当前新增对照使用同一冻结实现，仅切换 Pro delegation；旧实施前失败组单独保留、不混算。每组各运行 3 次，按中位数比较；记录执行时间和 provider/model 标识，模型版本发生变化则对照无效。
- 在每次委派 Run 中，至少两个方向必须由不同子任务处理，且至少一个子 namespace 标识为 `code_explorer` 并完成固定 SHA 的 GitHub 读取；没有真实子任务 namespace 的运行不得计入委派组。
- 授权：用户已于 2026-10-28 明确授权持续真实模型测试，无需逐次确认；maomaoai 不可用时使用 xiaok。仅发送公开固定 SHA 仓库内容，provider/model 变化后整组重建，不混算。

固定提示词（两组逐字相同）：

> 请只基于公开仓库 `deepseek-ai/deepseek-harness` 的提交 `477b4f420553e8a52c2fbccc464d7561b239c443`，调研以下三个互不重叠的问题：1）包目录如何组织 compaction 与 subagent 能力；2）长对话 compaction 的触发、工具结果剪枝和重试流程；3）subagent 的能力边界与提供方形态。如果 task 工具可用，将三个方向拆开并行处理，最多三个子任务；GitHub 源码读取使用 code_explorer。若 task 工具不可用，则由主 Agent 顺序完成。所有 GitHub 文件读取都显式传入该提交 SHA。最终用中文表格逐项给出结论、不可变 GitHub `path#Lx-Ly` 证据、置信度和未解决点；不能从证据推出的内容标为未知，不要猜测。

预登记答案（运行时不给模型）：

| # | 必须核对的事实 | 固定证据 |
|---|---|---|
| 1 | 包目录将 compaction 定义为 Service Definition、基础 Provider 与命令 Consumer 的能力族；subagent 则是提供方注册约定和面向模型的委派工具。 | [`packages/README.zh.md#L51-L53`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/README.zh.md#L51-L53) |
| 2 | compaction 在 Token 压力上升时摘要较早历史，支持 `/compact`，并可先修剪超大工具输出；该仓库随附基础配置默认启用。 | [`packages/compaction/README.zh.md#L10-L12`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/compaction/README.zh.md#L10-L12) |
| 3 | `dsh-compaction-basic` 在派生请求前经 `agent/pre-step` 处理压力；`agent/request-error` 仅处理规范上下文溢出；先做可选剪枝再选摘要，只有 replacement generation 前进才重试。 | [`docs/agent-lifecycle.zh.md#L85-L89`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/docs/agent-lifecycle.zh.md#L85-L89) |
| 4 | subagent 是 agent loop 之外的可选能力；同一注册表可以同时承载多个命名提供方。 | [`docs/subsystems/subagent.zh.md#L5-L7`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/docs/subsystems/subagent.zh.md#L5-L7) |
| 5 | 子 Agent 可由全新进程内、继承父级已完成历史的进程内、ACP/Codex/Claude Code/另一 Harness 等进程外形态提供；父 Agent 可发现子级。 | [`packages/subagent/README.zh.md#L10-L12`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/subagent/README.zh.md#L10-L12) |

每项只在结论正确且至少一个引用确实支撑该结论时计为通过；引用必须指向固定 SHA，文件路径和行号准确。5 项全部通过且无虚构引用才满足证据质量门槛。

### 正式调用和取数路径

- 通过 Platform Web 中 `dearflow_agent` 的正式 Run 流程执行；不要用 `DEAR_LIVE_TEST=1` 的 direct graph 测试代替，它不覆盖 Platform Run 身份和 Runtime 用量账本。
- 在隔离 Runtime API/Worker 环境启用 `RUNTIME_USAGE_ENABLED=1`、`RUNTIME_TOKEN_BUDGET_ENABLED=1`、`RUNTIME_TOKEN_BUDGET_MAX_TOKENS=1000000`。token budget 依赖用量采集、数据库迁移和受信 native Run 身份；缺少任一条件时停止真实对照。
- 由有该项目 Run Usage 读取权限的身份记录 `thread_id` 与 `run_id`；等待 Run 终态后，通过 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage?limit=100` 读取用量，并按 `calls.next_cursor` 取完所有调用页。必须为 `availability=available`、`finalized=true`，且 `coverage.missing_usage_call_count`、`coverage.incomplete_call_count` 均为 0。确认 `token_budget` 非空、`token_budget.max_tokens=1000000`、`token_budget.coverage=complete`、`token_budget.stop_code=null`（成功组；失败样本保留实际停止码）。单独记录 summary 的 `truncated`；它可能表示价格版本列表被截断，不能代替调用分页完整性判断。
- 主 Agent 和子 Agent 用量按逐调用记录的 `scope`、`namespace` 汇总；预算和 Run 总 Token 使用所有 scope（包含 auxiliary），不得只加 primary/subagent 而漏掉辅助模型。
- `conversation_offloading` 不在 Run diagnostics 聚合中。通过同一 Run 的 SDK custom SSE 帧记录 root namespace（`namespace=[]`）事件；只把 `type=conversation_offloading`、`trigger=automatic`、`status=completed` 计入自动整理次数，同时保留 `started/skipped/failed` 事件。诊断接口不能代替这项实时事件计数。
- 如果在关联 Worktree 执行，按 `docs/standards/worktree-development.md` 与 `scripts/local-stack.sh` 初始化和启动专属栈，配置写入该 Worktree 私有 `.local-stack/runtime.env`，使用 `status` 返回地址；不得复用其他 Worktree 的服务或数据。

### 必须记录

| 指标 | 计算与来源 |
|---|---|
| 主 Agent 输入 Token | 全部 `calls.items[]` 中 `scope=primary` 的 `tokens.input_tokens` 求和；另记录单次 primary 调用最大 `tokens.input_tokens` |
| 子 Agent 输入 Token | `scope=subagent` 的 `tokens.input_tokens` 求和 |
| 总 Token 与成本 | 全部 scope（primary、subagent、auxiliary）的 `tokens.total_tokens` 与 `cost.estimated_cost_usd`；summary 的 `tokens.total_tokens` 和 `cost` 用于交叉核对，不得过滤 scope 漏算 |
| Cache Read 与命中率 | 全部 scope 的 `tokens.cache_read_tokens` 求和；命中率 = cache_read_tokens / `tokens.input_tokens`；任一必要字段缺失则标为未采集 |
| 上下文整理次数 | 同一 Run SDK custom SSE 中 root namespace 的 `conversation_offloading` 事件；统计自动且 completed 次数，并记录其他状态 |
| 上下文错误 | 记录 ContextOverflowError、TokenBudgetExceeded 与其他失败码 |
| 耗时 | 从 Run 开始至终态的墙钟时间 |
| 证据质量 | 逐项核对预登记的 5 条事实是否有正确 URL 或 path:line；记录无证据或错误引用 |

### 通过门槛

1. 3 次委派运行均无 ContextOverflowError 或意外 TokenBudgetExceeded；主 Agent 自动整理事件为 0，任意 primary 模型请求输入不超过解析模型窗口的 50%。
2. 仅新增同额度两组均达到五项证据质量时，计算主 Agent 输入中位数降幅；达到 25% 才可宣称该幅度的同质量改进。串行失败时比较完成率并报告实数，不以失败结果计算同质量降幅。
3. 5 条预登记事实全部有正确证据；不允许出现虚构 URL、文件路径或行号。
4. 不再要求 100,000 内完成。新增两组使用相同 1,000,000 Run 额度作防失控兜底；所有 scope 完整采集、实际用量与 summary 对平。触发兜底、超出配置或用量未知都如实记为失败；不能以提高额度替代共享并发预算测试。
5. 缓存命中率、总成本和耗时如实报告但不设独立百分比门槛；不得将缓存命中解释为上下文窗口节省。
6. 每次委派 Run 至少出现两个不同的 subagent namespace、最多三个，且至少一个 namespace 对应 `code_explorer` 并有固定 SHA 来源证据；自动化并发测试证明峰值活动子任务不超过 3。
7. 自动化测试全绿、真实模型门槛全过，才可判定 done。真实模型测试未执行时最高为 partial；若预算/权限或输出证据失败，先修复并重跑，不能豁免门槛。

## 3A. DSH摘要前效率专项（执行中）

### 目标、控制变量与测量口径

- **目标：** 减少无关装载、不可恢复的截断和无收益重读，并在无需LLM摘要时完整交付；低占用本身不算成功。固定短题保留原≤50%窗口及root自动摘要0的目标，不另设49%门槛；一般长任务仍按有效W/O/headroom安全边界处理，不承诺任意任务永远不整理。
- **冻结：** 新组仍用第3节原始任务、公开固定SHA、五项评分表；供应商、model ID、配置窗口W、输出O、headroom、工具/技能组合、提示词与公共源码hash、调用次数/时间/循环设置全部登记。拿不到供应商部署fingerprint时明确unknown，不能声称已验证部署版本绝对相同。
- **预算：** T4后使用`RUNTIME_USAGE_ENABLED=1`、`RUNTIME_TOKEN_BUDGET_ENABLED=false`；新Run的`token_budget=null`是预期，不是采集失败。显式费用限额仍有单独回归，不在效果组途中过渡回1M。安全guard和已有非费用执行限制保留。
- **组内控制：** 两臂只切Pro delegation；不额外给委派组目标路径、评分答案、推荐读法或不同提示词。预登记委派1/2/3→串行1/2/3，每次新Thread且前次已终态；固定六个样本全部保留，不删除失败、不追加成功替补。失效或中断照记且整组不可计算的值保持未知。
- **状态：** 第一层契约/恢复、严格交接与overview/主级组合短链已执行，第九次独立烟测原五项5/5；v30已冻结并完整执行六次，委派3/4/5、串行2/2/2且一份Usage缺2次，正式门禁未过。继续已批准的短来源原句绑定，不把Phase证据当作原质量门槛通过。

| 量 | 记录方式与边界 |
|---|---|
| 请求组成 | 用现有guard/trace采样点区分互斥的system、Schema、技能/指令注入、其他消息和工具结果；无法识别来源的文本归未分类。记录字节/字符/同一meter估算和Schema数量，不把估算分项硬凑成供应商Token精确分账 |
| 首轮和后续输入 | 每个call记录配置窗口、估算、供应商实际`input_tokens`、cache tokens；主/子分开，auxiliary仍入总量。记录归一化/容灾后的有效Schema，已知provider隐藏开销和估算残差单列，缓存不从窗口输入中扣除 |
| 工具数据链 | 原始捕获→适配/分页→spill预览→压力剪枝→最终可见内容各阶段长度、结果身份及变化原因。原始捕获前工具/HTTP已经截断的，标为上游截断，不能伪造“全文已保存” |
| 四种不同处理 | 分别计spill、窗口/长行截断、历史结果pruning/replacement、LLM摘要；包含触发前后投影、作用namespace及结果。不能用root摘要0证明没有剪枝，也不把spill记为LLM摘要 |
| 重复读取 | 对同SHA/路径/namespace的实际返回行区间求总行观察、去重行、重复行；跨子任务另统计，不混入单namespace重读率。标注续读、原文回读、引用复核、冲突核对或理由未知，重叠不是自动判错 |
| 恢复与语义 | 对首/中/尾哨兵做真实工具回读，校验原文哈希/位置和namespace权限；再检查最终报告有无丢失限定、否定或来源绑定。checkpoint中存在正文不替代模型可用的读取路径 |
| 运行质量 | 正式Run终态、完整报告、原五项逐项评分、全部scope的Usage及耗时；保持同质量才算25%主输入降幅。失败串行不能用0输入/无引用空集合制造降幅或合格结果 |

诊断尽量复用现有私有trace/离线审计，仅持久化长度、身份和受控hash等必要元数据；不将完整模型请求、凭据、PII或父级私有正文新增到公共日志/SSE。缺少原始payload的旧Run保留未知，不从Usage总量反推不存在的分项。

### 第一层：无需模型费用的契约与回放

对应`tasks.md`的T5.1–T5.5，未实现前不勾选：

- [ ] 请求计量覆盖首/中/末轮、父/子、工具按需加载及容灾；不修改messages/Schema、不重复触发工具，不打破隐私与快照恢复契约。供应商实际输入与本地估算分别展示。
- [ ] 工具结果超限时确认保存成功才给可用引用；保存失败、来源过期/哈希不符、越权读取有真实有界失败，不泄漏其他namespace或伪称可恢复。
- [ ] 200行×100字符、多行长行、单行长文本、CJK、文本/图片块都在**附带提示后**守住有效工具展示上限；不能只断言读取原始结果前的阈值。单位和估算方式明确。
- [ ] 首/中/尾唯一哨兵在文件中保持完整，read_file分页能读出中间哨兵并继续到下一页；不得一遍遍只得到同一spill指针。工具名、路径、SHA、行号和实际返回文本对齐。
- [ ] 压力前不主动遗忘旧证据；压力后保留有内容的首尾与可恢复引用，保护未消费的完整工具批次和本轮有界子报告，剪枝后重测。能通过剪枝释放压力时不调用摘要模型；仍不安全时才走现有摘要/溢出流程。
- [ ] 通用研究样例覆盖“证据已足够”“缺一处中间段”“两来源冲突”“必须复核引用”；不硬禁重读，不把截断当全文，保留调用/时间收尾与无工具交付轮。
- [ ] 与本题无关的结构化子报告哨兵完整传到父可见内容，限定/否定/冲突/未知和来源绑定不丢；正常、过长、格式失败、取消、供应商不支持和末轮禁止工具等分支都有明确行为。JSON合法不计为语义通过。
- [ ] 技能/目录/规则是否重复注入有测量证据：同一历史被再次发送不误判为重复追加，恢复仍引用旧快照；权限指令、工具授权及PII行为不因“减Token”变化。

回归复用第2节既有单元/集成文件，并覆盖T5任务所列调用方及fixtures。先记录失败再修复；每项保存实际命令、退出码、通过/失败/skip数量及源文件hash。没有新增跨服务协议时不造API字段或前端面板；若确需改变契约，先明确差异并补对应API/Web测试。

### 第二层：正式链路与完整任务烟测

- [ ] 按worktree规范仅启动所属栈；使用正式Web→API→Runtime和新Thread，不以direct graph代替。沿用T4预算配置，调用后核对`availability=available`、`finalized=true`、全部Usage分页、missing/incomplete均0、`token_budget=null`；总量与各scope对平，成本缺价格仍记未知。
- [ ] 用一次独立完整研究任务检查有用工具页、证据回读、父子整合、最终可渲染报告；真实语义按第3节原评分核对，传输或格式通过不能掩盖事实不全。该次只作接线/诊断，不混入正式六次。
- [ ] 采集整个Run的root及子namespace事件，保留摘要started/completed/skipped/failed、pruning、spill和截断计数；流中断导致覆盖未知时不得记0。验证终态回放不自动重发Run。
- [ ] 权限、父取消传播、单子失败、图级3并发与费用显式开启时的预留继续通过；结束后按用户最新要求保持所属栈启动供人工验收，保留数据库、来源及原始失败，不destroy。

### 第三层：冻结效果组、归因和泛化

- [ ] 第一、二层完成后冻结manifest再跑完整两臂各三次；按原门槛检查委派3/3完整报告、五项结论与不可变引用全对、主峰值≤50%、root自动摘要0、Usage完整及无越权/越并发，不因此前失败调低门槛。
- [ ] 分开报告单次上下文峰值、主累计输入、全scope累计输入/输出、重复行观察、模型/工具调用次数、四类上下文处理事件、耗时、缓存及质量。不以“比DSH49%低”或“没有摘要”单项判定成功。
- [ ] 新结果与v23标为不同配置组，不能跨T4预算开关、源码或提示词变化计算单因素收益。组成审计/契约可支持某机制存在；最终六次只能支持整套新配置的效果，不冒称每项独立贡献已被因果验证。
- [ ] 若需要声称某一机制的单独收益，先固定公共配置再预登记只切该机制的成对实验；不默认增加全因子实验或继续堆模型调用。无这类实验时明确“机制依据＋组合效果”，保留原因的不确定性。
- [ ] 原题通过后，用预先冻结问题/公开材料/引用评分表的另一仓库任务检查泛化；可行时再增加自然跨过压力水位的长任务恢复检查。原短题无摘要是效率目标，长任务能够安全摘要且不丢证据是韧性目标，二者不能相互替代。

若获得DSH截图会话的实际导出或可运行环境，可补同一任务/SHA、模型/W/O、preset和工具集合的直接对照，记录spawn/fork/PTC及replacement事件。未取得时保留源码可复核结论和本平台对照；不把缺少DSH运行环境作为停止其他已授权工作的理由，也不宣称已复现其49%或累计费用。

## 4. Phase 验证记录

### 2026-10-30：v49六次终态及Markdown有界开头修正

- v49按登记完整结束，完整质量委派2/3、串行1/3；委派2与串行3缺loop外可选的最终结论，串行1供应商拒绝且用量缺1，不能补分或把未知算零。其余Usage完整，root自动摘要均0、主峰均低于50%。无同质量百分比结论。全部原始数据、无漂移末检和逐项评分见[61号](implementation/61-v49-controlled-validation.md)。
- 组后修正Markdown深处定位：有界开头与命中共用12000字符，身份/行范围独立校验，不扩原文跨上下文范围。旧实现红4 failed/5 passed；五文件136 passed/8 warnings（13.62s）；Ruff首轮1处import格式错误，修正后exit0。文件与标准已同步，见[62号](implementation/62-bounded-document-intro.md)。
- DSH/nanobot离线审计器组后补开头窗口和失败读取过滤，并修null报告；旧文件留存。独立合成自检验证同根来源、未读间隙与失败不计入。下一次首次模型调用前重新冻结；不回写旧样本。
- 本记录仍为Phase。独立正式复验、新六次、泛化及Final未通过前，T5.3/T5.6/T5.7/T5.8/T3.2/T3.3仍未完成。


### T5.3/T5.7/T5.8：角色事实边界与模型兼容性（2026-10-29）

54号逐句核对候选诊断3次实际请求，两臂仍全部保留且无新增，候选未接入；原指令下两模型诊断2次请求，DeepSeek Pro合法但未纠错、xiaok Flash纯正文，失败全部保留。55号只修正code_explorer自身执行约束与目标事实混淆、excerpt/citation旧措辞矛盾；88 passed/1 skipped/13 warnings（68.14秒）、Ruff通过。源码hash核对同步、所属Runtime API/Worker重启；新DeepSeek Pro正式独立任务已首次发送前冻结，主50/子16/三并发及其他额度未变，不混入旧组。见[55号](implementation/55-role-scope-and-pro-smoke.md)。

### T5.3/T5.7/T5.8：父级证据视图与覆盖（2026-10-29）

v40正常交付但原质量4/5；固定材料SDK两对诊断全部原始保留，不计正式组。52号将证据放在真实工具回执视图、明确同主题缺失事实可补充以及excerpt/citation字段边界；引用匹配与调用/原文限额不变。角色断言旧实现4 failed；首轮94 passed/1 failed暴露15项回执2030字符，缩短指令后95 passed；补多模态和整理后兜底后97 passed/7 warnings（8.42秒），调用方66 passed/2 skipped（96.43秒）。四文件与标准已同步，Runtime已重启；53号新独立正式任务已预登记启动。原质量、新六次、泛化、Final继续待验，不提前勾选任务。

### T5.3 / T5.7：GLM烟测失败与草稿纠错补齐（2026-10-29）

- 41号Run三个子级均失败，主级重复引用/字段校验错误；只读检查后正式接口诊断停止，终态interrupted，未用成功样本替补。51次已知Usage与profile对应；主峰31626/131072=24.13%、root摘要0，正式账本未finalized、总Token未知。54份固定SHA来源核验通过；无合法最终答复，五项质量未过，不执行成功答复的流/组合审计，见[41号](implementation/41-glm-independent-smoke-registration.md)与[42号](implementation/42-draft-recovery-correction.md)。
- 新回归先红4 failed；应用修复及旧失败夹具预算补齐后专项66 passed。PII新增回归与扩大集420 passed / 54 skipped / 1 deselected / 112 warnings，190.23秒，exit 0；Ruff与两目录diff检查通过。5份修正已核对旧摘要后逐字同步主目录，Runtime API/Worker已重启；仍为Phase，不提前勾选质量/泛化/Final。
- 同GLM配置新独立烟测先冻结清单，再正式UI发起Run `38d9d8ec-f4ca-458d-872e-1eae9d1b9308`，配置/题目/评分不变，见[43号](implementation/43-draft-recovery-smoke-registration.md)。

### T5.3 / T5.7：报告纠错缺陷修复与独立烟测登记（2026-10-29）

- 两个真实 compiled graph 新回归在旧实现先红（2 failed），修复后专项57 passed。新增混合批次无额外执行回归后，扩大集411 passed / 54 skipped / 1 deselected / 110 warnings，171.01秒，exit 0；Ruff通过。未选中的Docker场景及skip不算通过，见[39号](implementation/39-validation-retry-correction.md)。
- 两处应用/两份测试/服务规范已精确同步主目录，逐文件hash校验留在所属环境。未扩大报告、原文、工具权限或调用限额。
- 修复后xiaok `glm-5.3`独立烟测已先冻结1131份公共源码、环境/采集脚本/原题与评分；manifest摘要及边界见[41号](implementation/41-glm-independent-smoke-registration.md)。Run `05a0f218-e79e-41e3-993f-aafff336c07c`进行中，不能将兼容性烟测当六次稳定组或模型收益归因。

### T5.6：v33固定六次全部终态（2026-10-29，未通过）

- 委派三次原五项分别4/5、4/5、4/5；串行两次异常无最终报告、第三次4/5。两臂原质量门禁均0/3；六次主峰值均低于50%、root自动摘要均0，窗口效率不能代替质量达标。
- 串行前两次异常将Usage采集标为degraded，正式总量未知；已知调用和不冒充完整账本。完整Run、输入实数、引用局限及恢复Pro=True证明见[40号](implementation/40-v33-controlled-comparison.md)。保留全部失败，不宣称同质量25%降幅。
- 采集结束后恢复登记的Pro=True并重启所属Runtime API/Worker；五服务运行。泛化/Final尚未执行。

### T5.6 / T5.8：第十二次烟测与 v33 冻结（2026-10-29）

- 正式 Run `bbefc3ee-6e35-48e0-8d8a-2f0261219ec4` success，原五项人工5/5；36/36 Usage完整，主累计输入102637、峰28073/131072=21.42%，root自动摘要0，总766725 Token、637.63秒。三份合法子报告及实际交接原文、51处明确来源坐标、最终单次流/checkpoint一致均已核验。引用解析假阳性和浏览器检查失败尝试保留，详见[37号](implementation/37-smoke12-and-v33-freeze.md)。
- 1131份公共源码无漂移；新六次于09:48:50 UTC先冻结manifest，再按委派1/2/3→串行1/2/3开始。独立烟测不入正式组，历史失败不替换；正式门槛/泛化/Final尚未完成。

### T5.8：有界原文交接实施（2026-10-29，Phase）

- 用户已批准35号范围，应用接入已完成首轮专项：51 passed / 7 warnings，17.74秒，exit 0；详细命令、位置、覆盖与回退见[36号](implementation/36-source-context-handoff-implementation.md)。原题语义、六次稳定性、泛化及Final尚未完成，任务不提前勾选。
- 交付时按用户最新要求保持所属服务启动；不启动Docker，不提交/推送/部署。

### T5.3 / T5.7：第十一次复核与后续修订准备（2026-10-29）

- 第十一次原五项人工评分`[true,false,true,true,true]`已落盘，原始证据未改；15条发现重渲染与checkpoint逐字一致。真实正式链路仍质量失败，不把窗口24.65%或格式/传输通过计作5/5。
- 另预登记固定材料SDK诊断，父扩写描述/原始子问题各4次模型调用均未交回完整合法报告；共204965 Token，原有错误结果保留，没有执行研究工具。不能据一个失败对照认定简化描述有效，未修改应用提示词或追加替补。
- 有界原文交接的离线原型7项自检通过，三子原文包905/899/899字符；独立假模型SDK样例验证先校验再封装、360字符JSON经原生task回传。应用未接入，没有新Platform Run，不作语义收益或稳定性结论。数据与接入/验证/回退细节见[35号待评审稿](implementation/35-source-context-handoff-review.md)。
- 当前无活跃模型任务，所属五服务已通过local-stack停止，数据及失败证据保留。当前`blocked`仅指新的治理修订待人工决定；原五项门槛及28号批准不变。新正式六次、nanobot、Final仍未开始，不以本条Phase诊断收口整个项目。

### T5.7 短来源原句绑定与第十次独立烟测（2026-10-29）

- 实际已读固定GitHub行与短原句绑定，父级新发现同验、子级原句确定性保留；仍计入4800/18000字符，未增模型、权限或调用额度。来源存在性不等于语义完整。
- 初次扩大回归5 failed/319 passed，旧fixture缺excerpt；修复后324 passed、54 skipped、1 deselected（193.09秒），Ruff及两目录diff检查通过。原失败日志保留，跳过项不算通过，详见[33号记录](implementation/33-source-quote-binding.md)。
- 07:37:10 UTC冻结1130份公共文件；正式Web新Thread `1257aa91-b0a3-410f-886b-994bddc0dac8`、Run `79cc79c6-e809-4d22-a0c8-2d41cedbd014`终态success但质量4/5，仅一份子报告有效。Usage48/48完整、总1277294、主峰值29.10%、root摘要0，最终流一致；来源63份/独立引用26处验证通过。仍漏父级发现行为，不能重建六次或启动泛化，详见[34号记录](implementation/34-smoke10-and-validation-feedback.md)。
- 已定位字段形状错误被通用纠错文案掩盖，八次缩短仍未修复overview字符串。新增回归先红2 failed；字段级错误反馈与原句索引接入后45 passed（7.69秒），扩大327 passed/54 skipped/1 deselected（228.58秒），Ruff通过。预算与原评分不变。
- 第十一次独立原题烟测已完成：Run `c5b7ce5b-8fb7-4fc4-82b9-d875e67d274d`，三份子报告全部合法，33/33 Usage完整，总703073 Token、主累计输入162970、主峰值32307（24.65%）、root摘要0；49份来源及51处sources引用范围核验通过，最终流恰一次且与checkpoint一致。原五项仍4/5，仅2缺随附基础配置默认启用；`auto:true`不是默认挂载证据。该事实在两个子级的完整已读窗口中存在，5669字符初稿中已遗漏，非长度纠错或父级传输丢失。1130份公共源码无漂移；失败保留，不与正式组混算，详见[34号复核](implementation/34-smoke10-and-validation-feedback.md)。

### T5.6 / T5.7：v30六次冻结对照及后续原句绑定（2026-10-29）

- 六次新Thread/终态均保留、采集进程exit0，公共源码/环境无漂移、Redis无OOM。委派原五项3/4/5，串行2/2/2，全部门禁均0/3；完整Usage分别2/3、3/3。委派3含两次缺Usage失败调用，一次为maomaoai容灾尝试，不满足单provider条件。主级总量/整组中位数保持未知，不算同质量25%降幅。
- 已知主峰值22.53%–41.91%，缺Usage样本仅报告已知峰值；六次root自动摘要均0、最终AIMessage恰一次并与checkpoint一致。来源/引用坐标和人工语义分开核对，机械解析false及独立辅助核验均保留。详见[32号记录及完整数据](implementation/32-v30-controlled-comparison.md)。
- Pro已恢复到True预登记hash；按28号已批准A项完成短原句绑定及关联回归（324 passed/54 skipped/1 deselected），4800/18000总额度及调用保护不变，第十/十一次独立烟测均4/5未过；字段级反馈已修复，第十一次三份报告合法、Usage33/33、主峰值24.65%、root摘要0，仍漏默认装配语义（34号），见[33号记录](implementation/33-source-quote-binding.md)。无新的正式组结论，泛化/Final未开始。


### T5.7 第九次烟测及 v30 正式组冻结（2026-10-29）

- Run `59765d3f-6b26-4cfd-8895-91649998721a`：原五项5/5、三子code_explorer、Usage36/36完整、785088总Token、主峰值31269/131072=23.86%、root自动摘要0；最终messages seq29203恰一次且与checkpoint一致，seq29240终态。
- 59份来源固定SHA/hash/blob通过；原引用解析器35个引用均覆盖但30个正文缩写未解析，机械false保留。单独人工辅助核验sources、完整路径及缩写映射共99处坐标均存在且实际已读，不把存在性当语义证明；额外两处精度问题亦保留，见[31号记录](implementation/31-smoke9-and-frozen-comparison.md)。
- 当前DearFlow/容灾/PII回归299 passed、54 skipped、1 deselected（Docker场景不运行、不算通过），408.54秒。v30于06:29:57 UTC冻结1129个文件及环境/采集器，开始委派1/2/3→串行1/2/3；尚无正式组结论，泛化/Final未开始。

### T5.7 第八次烟测与正常/纠错指令分离（2026-10-29）

- Run `bcf342d2-4b9e-40a8-b092-b6c54f2b668f`正常交付但原质量2/5，未委派，全部Token122827、峰值21.92%、Usage6/6完整、零摘要；实时最终消息seq690恰一次且与checkpoint一致，失败保留。
- 分离正常收尾说明与验证失败反馈，组合专项31 passed/1 skipped；预算/隐私96 passed，扩大隐私/容灾37 passed/9 skipped；集合重叠不累加。Docker未运行仍单列。第九次独立烟测运行中，不混入正式组，详见[30号记录](implementation/30-smoke7-and-stream-audit.md)。

### T5.7 概述与有界组合接入及第七次烟测（2026-10-29）

- `v27-synthesis-regression-2.log`：71 passed、1 skipped；`v27-synthesis-boundaries.log`：35 passed（集合部分重叠），报告/权限/预算/取消/隔离与单一答复的局部契约通过，不能作为原题语义合格证据。
- 第七次正式Web烟测Run `fd6eae0e-6e7c-44a9-8be0-3cc8ce8380be`：40/40 Usage完整，root摘要0、主峰值18.75%，原五项3/5，漏subagent主循环外及父级发现；报告重复。保留失败，不计正式组六次。
- 原流采集器30MB后静默漏采；补读原事件seq27266找回唯一表格，ID/正文与checkpoint一致，无需修改业务发布。新增正式Worker V3与legacy四场景4 passed；下一次烟测仍须完整实时采集。
- 扩大专项20 failed/241 passed/45 skipped如实保留；19项夹具适配与一个Docker环境失败分开处理，local链路不启动Docker。后续修正与证据边界见[30号记录](implementation/30-smoke7-and-stream-audit.md)。T5.7继续未完成，Final未开始。

| 日期 | 测试/模型/Run ID | 结果 | 证据 |
|---|---|---|---|
| 2026-10-29 | Phase 5：原题完整烟测 `2af96503-2005-4daf-98ab-61efca7f89c7` | 运行success、质量失败；2/3子报告非法 | 4800字符超限、sources条数超限，PG错误确证；776,028 Token、Usage43/43完整；不混入正式组 |
| 2026-10-29 | Phase 5：SDK有界纠正及Schema权限匹配 | 87 passed、1 skipped | `v25-schema-correction-regression-3.log`；纠正沿用既有调用上限，无新执行权限 |
| 2026-10-29 | Phase 5：真实技能快照进程重启 | 4 passed | `v25-skill-restart-pg.log`；所属隔离数据库临时schema |
| 2026-10-29 | Phase 5：子报告/权限/并发/取消/末轮/预算/错误 | 111 passed、1 skipped | `v25-report-enforcement-regression.log`；纯文本回退先红测1 failed后修复 |
| 2026-10-29 | Phase 5：私有计量、GitHub捕获/适配、工具输出/剪枝 | 101 passed | `v25-metrics-regression.log`；不记录正文或Schema原文 |
| 2026-10-29 | Phase 5：真实HTTP/PG/Redis/Worker恢复、重启与回滚 | 1 passed，138.57s | `TOOL_ERROR_PLATFORM_TEST=1`；`v25-tool-e2e-4.log`，前三次fixture失败保留 |
| 2026-10-28 | Subagent、TokenBudget、工具输出与 ConversationOffloading 定向测试；提交 `78aa1717` | 122 passed, 1 skipped | 命令见 tasks.md 的 T0.1 completion card；33.04s |
| 2026-10-28 | Runtime 全量探索测试（排除缺失 `scripts.verify_execution_budget` 导入的集成测试文件） | 1783 passed, 12 failed, 291 skipped | 失败包含 7 项记忆抽取/用量测试和 5 项需要可用 Docker 的集成测试；这不替代上方定向门禁 |
| 2026-10-28 | 原 maomaoai 串行 Run；Thread `483ae85b-c09b-43ff-9f43-1b01bda67e61` | 无效 | 4 次模型调用，117,245 Token；cache read 58,880；估算成本 $0.102288；超出 100,000 上限 17,245，且 stop_code=null；不是有效基线 |
| 2026-10-28 | xiaok / deepseek-v4.1-flash；Run `b29946ba-af92-4f18-a1de-8ffb4edb7781`；Thread `2c6b8cae-114e-4556-9147-6c1fdbf02cc0` | 无效 | 正式 Web Pro；1 次已完成调用，26,915 input + 423 output = 27,338；cache read 1,280；价格未配置，成本未知；19.157s；下一次调用被保守预留拒绝，stop_code=token_budget_exhausted；Usage 当时 502；未捕获 root SSE，不记作 0 次整理 |
| 2026-10-28 | T0.B 预算前置修复定向验证 | Phase 通过，真实链路待复验 | Runtime 73 passed；API 37 passed、266 subtests passed；Web 31 passed；Ruff passed；另既有 Subagent/上下文 93 passed、1 skipped |
| 2026-10-28 | xiaok Run `85f0be0d-6735-4369-a3a7-ef2c4425f31c` | 无效 | 83,755 Token，三次调用后预算停止；未完成报告，不计中位数 |
| 2026-10-28 | xiaok Run `ca2e6fd2-38ea-43e0-b93a-40701cc9a168`；Thread `f9abb551-442c-4e0f-ad8c-9f5502eabc3e` | 无效；T0.B 正式链路通过 | input 82,720 + output 747 = 83,467；cache read 27,520；Usage 200/finalized、coverage complete、缺失/未完成均 0；递归 tree 两次失败，未交付报告 |
| 2026-10-28 | xiaok Run `a0a83cac-804c-4caa-94df-aa056ff21dda`；Thread `f68eaaf8-6e6a-4cda-8faa-8fb9548a557c` | 无效 | 目录失败已消除；三次模型 input 27,061/28,840/30,934，总量 87,762；预算停止、Usage 200 complete；固定 Schema 开销阻止继续，不算基线 |
| 2026-10-28 | xiaok Run `4728927a-ee4e-46d2-89cb-3ce6dd53ffe5`；Thread `b617d4f6-208e-4f34-9d7e-cd07f7ca8332` | 无效；图表按需展示效果已观测 | 首输入降至 12,402；五次调用 input 74,024、output 1,488、total 75,512；cache read 39,040；参数错误重试后预留拒绝，未交付报告；旧默认单次输出上限，不计新 4096 配置基线 |
| 2026-10-28 | T0.G 固定 SHA GitHub HTTP/工具探测 | 通过 | 递归树 4,337,791 bytes；非递归根目录 14,308 bytes；工具根/子目录/文档 L80-L93 成功，content hash 与 namespace 校验通过 |
| 2026-10-28 | code_explorer 完整图权限、四任务单槽释放、父取消与单子失败 | 8 passed、1 skipped | `test_subagents.py`；最终模型工具集合恰为 ls/read_file/glob/grep/github_query；四份来源哈希与 namespace 独立，父消息无子原始正文，用户文件未改；Langfuse opt-in skip 不计通过 |
| 2026-10-28 | 图表 Schema 首次隐藏、按规格加载、策略拒绝、图重建 | 2 passed | `test_agent.py -k chart_schemas`；后续共同前置条件 |
| 2026-10-28 | GitHub 与图表已有能力定向回归 | 26 passed、2 skipped | `skills/test_data_web_batch.py skills/test_research_batch.py`；外部 opt-in skip 不计通过 |

| 2026-10-29 | xiaok Run `4d6ea942-7cff-4d34-8702-1757e4377608`；Thread `a4fda3cb-a954-474b-b7d8-d4a4fa71b4f4` | 无效；不计基线 | 正式参数 `max_tokens=4096`；五次 primary input 12,444/14,208/14,838/16,621/18,036，合计 input 76,147、output 1,756、total 77,903，cache read 56,192；Usage 200 complete，但参数纠错与逐级列目录耗尽准入空间，未交付报告 |
| 2026-10-29 | 图级共享预算、namespace、TokenBudget | 57 passed | 三个在途子调用共享预算；父已用 10 + 三份预留 90 = 100，实际结算 100、预留归零；不同子 namespace 保留实例身份，末级模型步骤归一；额度耗尽不再调用模型 |
| 2026-10-29 | Subagent/预算/工具输出/剪枝/整理/modeling 组合 | 97 passed、1 skipped | 沿用现有上下文机制；opt-in skip 不计通过 |
| 2026-10-29 | 最新 GitHub clamp/紧凑 tree、Subagent、共享预算 | 29 passed、1 skipped | max_lines 正整数夹取至 200；目录默认 100 项，返回直接紧凑 JSON；随后 Ruff 检查全部修改 Runtime 源码与测试通过 |
| 2026-10-29 | `tests/observability/test_usage.py` 探索回归 | 17 passed、1 failed（单次运行结果） | `test_hidden_memory_model_inherits_usage_without_exporter` 预期辅助记忆用量 60，实际为 None；根因尚未确认，不将该文件记作全绿；基线已有记忆/用量失败，仍需核对当前影响 |
| 2026-10-29 | Run `b94bebfc-c766-4dd0-a42d-5b07be3688a9`；Thread `9668f7f9-b1bb-460c-88d6-58f17daa5afa` | 无效；保留失败证据 | 六次调用，input 89,056 + output 2,144 = 91,200，cache 51,840；仍继续逐层列 src，未交付；完整 Usage、stop_code=token_budget_exhausted；`.local-stack/serial-compact-v2-1.json` |
| 2026-10-29 | Run `5f3a4507-dd72-4cef-af2c-d87467070b0d`；Thread `063c9d45-3f2e-479e-8297-6932814e880d` | 无效；文档优先共同规则后的首样本 | 五次调用，input 78,832 + output 1,808 = 80,640，cache 43,520；有源码文档但仍未交付；Usage complete，stop_code=token_budget_exhausted；`.local-stack/serial-doc-first-1.json` |
| 2026-10-29 | 超长子报告真实编译图、完整 Subagent 与 Usage 回归 | 27 passed、1 skipped | 超长报告落盘、父 task 消息≤4,800 字符，截断明确且尾部不可变引用保留；普通报告保留引用。旧记忆用量测试改为等待异步抽取任务结束后再断言，60 Token 正确结算；未修改记忆生产代码 |
| 2026-10-29 | 预算准入失败的安全收尾 | 35 passed | `tests/middlewares/test_token_budget.py`；`end` 模式下同步/异步预留拒绝不派发模型、正常交回“尚未完成”；`error` 模式仍抛精确预算异常，未知用量不豁免 |

2026-10-29 方案修订已获用户批准：保留三次 100,000 失败基线；随后用户授权放宽总额度，按 plan.md 第 7 节预登记 1,000,000 新对照。总预算、累计用量与当前/峰值上下文占用分别记录，五项证据不放宽。原失败组不混入新额度效果计算。

图级共享预算测试定位并修复旧 namespace 归一化缺陷：三个子调用原本全部被折叠成 `[tools, model]`。现在保留祖先任务实例 ID，只去除末级模型步骤 ID；不新增账本字段或权限，相关新契约测试已通过。

### 预算估算边界

输入估算使用 4 字符/Token + 25% 边际，并非供应商精确 tokenizer，中文/多模态/模型特有隐藏输入仍可能低估。当前 1,000,000 是隔离测试 Run 准入兜底配置，不作账单硬上限保证。超额、预算停止、用量不完整或证据不合格的 Run 一律单列，不补零、不算有效样本。失败样本发生在委派组实施前，任何验收修改都必须在委派结果出现前明示登记。

### Task T4.1：DSH预算对齐（2026-10-29）
- 用户本轮明确授权，预算默认按窗口/输出/65,536 headroom计算，触发80%全窗口与剩余容量取小，保留16%消息预算；普通运行关闭累计费用限额，Usage保持开启。旧Run/失败不改写。
- 红测4 failed；实现后预算/上下文/主子装配/共享预留128 passed、5 warnings（28.25s）；扩大相关组合48 passed、2 skipped、1 deselected、41 warnings（52.67s）；Ruff通过。
- 初次扩大回归发现两个30K模型fixture缺headroom，已显式配置并通过；额外误纳入的Showcase Docker执行集成因执行结果不可确认失败，未计通过，本次未宣称全仓验证或Final通过。
- 覆盖128K/1M窗口、输出变化、小窗口拒绝与配置、非法headroom、显式覆盖、先剪枝重测、手动/供应商溢出、并发预留；关闭限额的组合测试在累计1,200,002 Token后继续且采集完整。真实探针不花费百万Token证明这一分支。

### Task T4.2：正式预算接线与后续计划（2026-10-29）
- playwright-cli正式页面提交新Thread `dd453501-506d-4182-843d-12d19a7c95e3`，Run `da6a1372-ff6a-4217-b02a-c891c9f298a5` success。xiaok/DeepSeek模型身份由Usage核验；HTTP200、finalized、complete，`token_budget=null`，2 observed/2 reported，0 missing/0 incomplete，总28,645 Token。
- 固定公开SHA单份README短探针，仅验证预算接线，不混入质量对照、不证明长任务成功。raw及冻结hash见`implementation/24-dsh-budget-alignment.md`。
- 初次Redis启动因旧数据BusyLoading被立即停止；对该错误追加有界等待，3项探针回归、shell语法与实际所属栈启动通过；资料未删除。首次页面脚本因过期登录态在新建前停止，重新登录后才发送新Run。
- 调用方补查：隐私/工具输出矩阵56 passed、5 warnings（15.09s）；所属隔离PG两次整理/连接恢复/官方wrapper回退及循环状态恢复2 passed、5 warnings（5.19s）。13个修改Python文件Ruff通过。合计234项Runtime/真实PG相关测试通过，另3项启动探针；两个skip不计通过。真实模型历史十次摘要和Docker执行集成未作为本次通过证据。
- 收尾：浏览器已关闭，仅所属wt_bf33bcf838fd应用/Redis停止，status确认均stopped；数据和证据保留，未destroy。
- 后续顺序：保留可恢复证据→收尾/父子交接→同配置完整对照。旧结果超过300字符门槛后整段占位的逻辑尚未改变，不能把预算通过当作原质量门槛通过。

### Task T5.0：DSH摘要前效率源码分析与设计（2026-10-29，仅文档）

- 参考仓库HEAD核对为`477b4f420553e8a52c2fbccc464d7561b239c443`；base显式12500估算Token spill，read默认2000行/单行2000字符/50KiB选中内容，grep默认250匹配/每行2000字节，技能目录及指令digest去重都有本地源码依据，详见plan。截图会话的实际preset、模型窗口和工具轨迹未知，不据此声称逐项因果已证实。
- 检查所属隔离env中4个相关非敏感配置键，其中3个有显式值：1200 Token外置、4800字符工具输出、300字符剪枝门槛；未打印凭据、未修改配置或应用源码。300不是保留长度。
- 对`middlewares/filesystem.py:truncate_tool_output_text()`做独立静态复现：用Python AST只提取该纯函数，输入200行、每行100个ASCII字符（总20199字符），传`max_chars=4800`/`tool_name=read_file`，实际输出10237字符，断言`len(result)>4800`成立。源码SHA256为`d68ed9c182234c1ff6c6587ff3d3bcc7a61a47ccc06a91c16ac27801797b6705`。这是**既有缺陷被复现，尚未修复**，不是单元测试绿灯或真实Run证据。
- 已把范围、调用方、fixtures、分层验证、冻结规则和无数据损失回滚补入plan/tasks及本节；T5.1–T5.6未执行。本轮未启动栈、未发模型请求、未改五项答案/历史失败，也未提交、推送或部署。
- 文档机械校验：8份本轮编辑文档共328个本地链接/锚点扫描，无新增坏链；FEATURES中4个缺失目标在HEAD中已存在，本轮不扩大修复范围。21个主要源码/测试/fixture路径存在，T5.0完成/T5.1–T5.6及T3.2/T3.3未完成的状态断言通过；`git diff --check`通过。该检查不替代应用测试或Final。

### Task T5.3 / T5.6：源码页校准、第三/第四次烟测审计（2026-10-29）

- 第三次烟测Run `65aba2e7-8811-448b-b8c6-f955af68f5d1`：Usage47/47完整、39个引用均在实际窗口、root自动摘要0，仍遗漏默认启用与父发现等原质量限定。全部原始及派生证据保留，不计正式组通过。
- 审计确认本次真实spill/展示截断/压力剪枝均为0；GitHub适配层仍仅3000字符源码页。普通200行文档红测只返回28行，1 failed；校准现有窗口至12000字符后，GitHub读取、分页、查询坐标、证据hash及长行组合31 passed（9.70s）。
- 工具/报告/装配/剪枝/限宽组合`v25-page-handoff-regression.log`：108 passed（31.54s）；Ruff通过。两次Ruff命令/格式失败日志保留，不计通过。
- 第四次独立完整烟测Run `f9075d3e-77ef-48b5-8b86-fc02cc93dcb6`已通过正式Web入口启动，等待真实终态与五项评分；不混入正式六次。
- 第四次终态Usage37/37；三个code_explorer、62项source hash/fixed SHA审计通过、0未观察引用窗口、root摘要0。输入822,126、primary峰值46,520、持续441.16秒；质量仍因主循环外架构边界不完整及短路径引用歧义未过。该差异不证明页宽调整因果。
- 通用缩短委派描述与完整引用格式的提示词契约`test_agent.py -k restricted_code_explorer` 2 passed；Ruff通过。第五次烟测尚待执行。

### Task T5.3 / T5.6：第五次烟测及task描述一致性（2026-10-29）

- Run `54eff865-88c9-4cfb-8252-858b3884e7e3` success，Usage43/43完整；总1,019,796 Token，主输入359,125、峰值51,847，root自动摘要1。75份来源SHA/hash正确；42个去重引用均在观察窗口，13处同一行承接路径的裸行号也可解析，属于提示格式未遵守，不能误称虚构或追加验收门槛。
- 五项质量失败：报告未完整保留基础配置默认启用、主循环外和父可发现子级等关键限定。子报告包含若干被遗漏结论，父级仍额外27次GitHub调用，不能把低窗口占用解释为成功。
- SDK task默认详细委派/自行摘要措辞与项目简洁范围规则冲突。现有委派中间件只复制模型可见描述；SDK执行、Schema、权限和私有状态隔离沿用。报告Schema只补优先顺序描述，未注入原题答案。
- 红测`v25-delegation-description-red.log` 2 failed；修复后`v25-delegation-description-green.log` 43 passed、1 skipped（46.57s）；模型实际绑定描述、工具对象/消息不变、task不可见不新增、图级父子隔离/失败/取消/预算回归通过，Ruff通过。下一次独立烟测继续执行，正式六次未开始。详见implementation/25-phase5-evidence-preservation.md。

### Task T5.3 / T5.6：第六次烟测逐项复核与Docker边界（2026-10-29）

- Run `651df39e-5ebd-4b54-a6ed-c80d4ddfbf25` success/stop，Usage35/35完整、总账对平、无fallback，`token_budget=null`；总723,173 Token、310.425387秒。主8次输入170,508，峰值29,218/131,072=22.3%；子27次输入515,417；root自动摘要0。来源54份（子47），固定SHA/hash/git blob通过；39个去重引用被41个读取窗口覆盖，35/35组成计量关联，spill/展示截断/压力pruning均0。
- 人工按原评分为3/5：1/3/4通过，2遗漏摘要较早历史，5遗漏父级发现。子报告含direct-child与递归后代发现，父自己的README读取也覆盖原文，最终却遗漏。窗口与零摘要达标不能替代语义验收；本次与前五次均不混入正式六次。
- 逐项评分、样本hash与证据位置见[完整复核](implementation/27-phase5-smoke6-review.md)。task描述修复的43项回归不证明单因素质量收益；未新增评分门槛、未重发模型任务，Final仍未开始。
- 当前主链路使用local隔离栈，无需Docker。额外既有容器执行/超时/取消补测已停止，daemon未连通、未启动测试容器；相关项保留未验证，不以其作为继续本轮的前置条件，亦未确认Docker GUI退出。本次只更新审计与状态文档，没有新增代码或模型调用。

### T5.3诊断与T5.7修订准备（2026-10-29，Phase）

- 固定第六次公共研究材料与原题，不注入五项答案，进行两种子报告呈现的六次直连诊断：compact三次均返回DSML工具正文，readable三次中两次工具正文、一次报告仍漏重要事实；没有足够有效终稿，不作格式收益推断。独立封闭工具组首调用同样失败，按断言停止，剩余五次未执行。实际共7次供应商调用，原始响应、Usage和两个manifest均留存，不计正式Run/对照组。
- 离线`v25-lossless-projection-demo.py`真实执行exit0：第六次3份子报告、15条发现字段全部保留，缺决定/重复/陌生引用/无理由/非法状态5类负例拒绝，unknown不升级、excluded保留。输出均标unreviewed；不证明来源语义、SDK权限、流/持久化一致或原题5/5。
- 应用源码和已批准的运行机制未因上述诊断修改；T5.3/T5.6/T3.2/T3.3仍未完成，新增T5.7为待人工评审。具体改动点、接入/预算/安全/取消/回退及正式验收见[可审阅修订稿](implementation/28-evidence-composition-review.md)。当前local栈无需Docker，Final未开始。

## 5. Final 验证记录

尚未进入Final：v23两组真实对照已完整执行，但现行质量门槛未通过。用户已同意优化方向并要求补齐方案，当前Phase 5已批准并实施、分层验证进行中；不再把相同方向的评审列为未答复阻塞。未完成必要实现与验收前不作done结论。

最终记录需保留 3 次串行和 3 次委派运行的指标、事实核对表、测试命令和四态结论。

## 6. 2026-10-29 连续三次串行失败组（Phase 证据）

这三次采集在共同前置修复及安全收尾之后，使用同一 Runtime Worker、xiaok `deepseek-v4.1-flash` / model ID `070cced3-350b-42ec-b678-994dd07b7078`、Pro=False delegation、4096 单次输出、100,000 Run Token；每次全新 Thread 且前一次终态后才开始下一次。上下文策略保持 trigger=0.85、keep=tokens:40%、工具输出=1200 Token/4800 字符、pruning keep=4/min_chars=300。provider 未提供可核验的部署 fingerprint，不推定其隐藏版本。

- Prompt SHA256：`2568adff93f0d58f3b97b90ce59b8be2350fa2bac909983549fc0962ea5314bc`；原始用户提示词未改。
- [可审查的采样与汇总 JSON](implementation/02-serial-baseline-evidence.json) 保存每次 Run/Thread、UTC 时刻、逐组用量、成本缺失状态、来源 SHA 检查、root SSE 检查及原始文件 hash；完整原始证据留在所属 Worktree `.local-stack/serial-final-{1,2,3}.json`。
- 工程状态 `run.status=success` 仅表示安全结束；三次 `stop_code=token_budget_exhausted`，最后答复明确“尚未完成”，**不算调研任务成功**。价格未配置，成本未知，不能记为 $0。

| Run ID | 主输入 | 最大单次主输入 | 输出 | 总 Token | Cache Read | 墙钟秒 | root 自动整理 | 证据评分 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `94a276d0-cc6f-4eb4-bb81-012c5c0debab` | 77,806 | 17,282 | 1,691 | 79,497 | 66,304 | 61.914 | 0 | 0/5，未交付最终报告 |
| `3d278a0e-50f6-4d28-9e92-53ead57480b1` | 77,869 | 17,378 | 1,759 | 79,628 | 63,104 | 71.516 | 0 | 0/5，未交付最终报告 |
| `972373e3-fbc3-4469-b12b-c28e2a38c8e4` | 77,685 | 17,190 | 1,849 | 79,534 | 63,616 | 62.744 | 0 | 0/5，未交付最终报告 |

三次均为 Usage HTTP 200、available/finalized、coverage complete、缺失/未完成调用为 0；各五次 primary 调用，无 subagent/auxiliary。逐调用总量与 summary 对平，所有 GitHub 调用均显式携带固定 SHA。SSE 根据 `event_id` 去重并按 Run 过滤，观察到 root running 和 completed；thread stream 仍开放不等于 Run 未结束。未观察到任何 root offloading 事件，故自动 completed=0。

中位数：主输入 **77,806 Token**，总量 **79,534 Token**，墙钟 **62.744 秒**，缓存读取比率 **81.89%**；完成率 **0/3**。这些是失败基线实数，**不作为成功基线，不计算同质量主输入降幅**，也不把缓存命中视作上下文窗口节省。

本轮定向回归：

- Runtime：`test_agent.py/test_subagents.py/test_delegation_budget.py`、GitHub/图表工具测试、预算/输出/剪枝/整理、modeling/usage 共 **222 passed、3 skipped**（84.90s）；命令与完整输出见 `.local-stack/phase-runtime-tests.log`。Pro 模式最终开启断言与 Pro 权限验收尚未通过，不包含在此绿色集合中。
- 首轮该组合为 220 passed/1 failed/3 skipped，失败是 Pro 关闭时预先写成“必须开放”的角色测试。改为显式覆盖当前 Pro/Ultra 的角色装配；最终 Pro=True 的模式验收仍保留在 `test_modes.py`，待门禁批准后执行，没有把最终要求降为 False。
- API：`test_execution_budget_projection.py test_run_usage.py` → **37 passed、266 subtests passed**（2.92s）。
- Web：`src/modules/chat/budget/view-model.spec.ts` → **21 passed**；`vue-tsc --noEmit`、修改文件 ESLint exit 0。
- 全部修改的 Runtime/API Python 源码和测试 Ruff 通过；两工作区 `git diff --check` 通过。
- 浏览器实看 `.local-stack/serial-final-3.png`：Token 预算停止横幅、尚未完成答复及输入/输出用量均可见；无重复重投。

**当前判定：partial，实施与验证继续。** 人工验收修订已经批准，不再存在该审批阻塞。旧三次失败完整保留；根据用户放宽预算的新指示，重新采集同额度两组，不提前作 Final 结论。

### 2026-10-29 预算修订与后续 Phase 门禁

- 用户授权放宽 100,000，按 plan.md 第 7 节预登记新额度 1,000,000；旧三次保留，新增两组各三次，不选样。
- Pro 开启后的模式/角色/研究/Subagent/共享预算组合：63 passed、2 skipped、39 warnings（152.19s），见隔离环境 `.local-stack/phase-pro-tests.log`。Ultra 权限定向：8 passed、21 deselected（31.32s）。
- dsh 49% 的计算已核对本地固定源码；只代表该时刻投影，不能推出窗口分母或整轮峰值。新增记录主/子输入峰值、解析窗口分母、所有 scope 总量与缓存；成本缺配置仍标未知。

### 2026-10-29 新额度v1失败与T0.L修复（Phase）

- Run `a36a405c-3893-4758-839d-c42e40682973` / Thread `80c4ff01-e708-4394-8ad9-b8fc7badfeff`：模型在已正确读取后误将repo写为deepseek-ai，连续失败仍重复。诊断发现后主动取消；原始文件`.local-stack/serial-relaxed-v1-aborted-1.json`完整保留，不补样掩盖。
- 状态interrupted，finalized=false、collection_degraded=true；25次已报告调用的已知输入491,805+输出8,824=500,629，summary total仍unknown，不把known值宣称完整账单。未交付最终报告，不计成功或同质量降幅。
- T0.L先写回归：5 failed、3 passed，分别复现三类缺少定位提示与同步/异步错误循环未拦截。修复后错误/循环/GitHub工具组合**95 passed**（17.87s）。
- 复用现有LoopDetectionMiddleware，补github_query白名单；仍只对完整、有限、无artifact的相同结果计数，分页参数改变属于进展。三次预警、五次阻止第六个模型调用。只在隔离环境显式开启既有AGENT_LOOP_DETECTION_ENABLED=1，不改产品默认。
- 不可访问GitHub来源返回静态安全提示，要求按原始任务核对owner/repo/ref/path、禁止原样重试；原错误code/outcome和权限语义不变，不泄露私有状态、上游正文或凭据。
- 公共工具提示与错误/循环源码变更后，采样版本改为v2，重新预登记两组各三次；旧v1保留，不混算。新manifest为`.local-stack/relaxed-v2-manifest.json`。

### 2026-10-29 新额度v2串行样本1（Phase，失败保留）

Run `47445535-1cb4-46c0-b82f-60ca233954f2` / Thread `6566df20-c830-48be-bac8-5e33294753fd`：已避免上一轮错误仓库参数死循环，但仍持续反复分页取证，最终工具调用上限触发（102/100），status=error。已知用量909,948；32次调用均已报告，但finalized=false、collection_degraded=true，summary未知。捕获到root automatic整理started/completed各一次。没有最终报告，不能记成功或把已知值当完整账单；原始`.local-stack/serial-relaxed-v2-1.json`保留。采集器修正为失败终态先落盘，不因finalized=false丢弃失败。

### 2026-10-29 T0.C复现与v2诊断停止（Phase）

- 新回归在同一段原始历史上覆盖开启折叠、关闭折叠、手动整理：修复前1 failed、2 passed，证明自动整理仍按未折叠历史触发。不能通过把折叠消息提前传给摘要来修复，否则归档会丢原文。
- v2样本2 `9c19a5ac-5c93-4a72-bb2f-92ad0a07ab5d` / Thread `ec19adde-3108-4c95-a529-ec75511752c8` 在诊断确认后主动停止，并先终止自动采集器，未启动第三轮。终态interrupted；已知输入664,202+输出8,112=672,314，32次均已报告，peak input24,813，root自动整理0；finalized=false，不当完整账单。原始`.local-stack/serial-relaxed-v2-aborted-2.json`保留。
- v2组因为公共上下文修复而终止，不作为完成的三次对照，也不挑成功替换失败；v3在公共修复及回归通过后重新预登记两组。旧100k、v1、v2的全部失败记录继续保留。
- T0.C关联组合105 passed、5 warnings（57.20s），Ruff与diff检查通过。计数和最终请求共用实际折叠实例，原文用于摘要/归档；无该实例的调用者仍按原文计数。隐藏摘要真实回调确认auxiliary/summarization。详细见`implementation/04-pruned-context-accounting.md`。
- v3预登记manifest SHA256 `16c70f4b902c174a29a1b9dcc1c0c3f8d145dff9524ee73ef0197326a1f68af1`，15份公共源码；除Pro委派开关外，两组保持相同配置。尚未采得结果，不预判通过。
- 串行配置下扩展组合为251 passed、2 skipped、8 failed（106.82s）；8项均为要求Pro已开放委派的角色权限场景，当前串行临时关闭因此失败。此结果不作为最终门禁通过，恢复Pro后须重跑完整关联组合。
- v3采样次序在首轮尚未终态、委派结果出现前登记为serial-1 → delegation-1/2/3 → serial-2/3，以尽早暴露委派链路问题；仍逐次等待终态、全新Thread，不并行跑样本，不替换失败。旧三次基线已满足批准的隔离委派前置门禁。每次切组只改Pro delegation并重启本栈Runtime；公共源码15文件哈希继续冻结。次序记录`.local-stack/relaxed-v3-sampling-order.json`。

### 2026-10-29 v3串行样本1与委派启动（Phase）

- Run `6fa36fa8-e759-43be-8844-e7fac5bf68d7` / Thread `910a3fc2-c406-4330-9205-0ca7cbe70cd2`终态success表示基础执行结束，stop_code=token_budget_exhausted，实际任务未完成，不能当作成功样本。39次primary调用，输入959,265、输出16,780、总量976,045；cache read759,936，primary峰值34,086/131,072（约26.0%）；root自动整理0。
- Usage finalized=true，调用账本与summary总量对平；最终仅55字符预算收尾提示，无完整五项证据报告。67份成功来源记录已核对完整文件SHA256、GitHub调用的固定ref、原文与本地固定提交完全一致。原始`.local-stack/serial-relaxed-v3-1.json`及audit/sources文件保留。
- 首轮终态并落盘后，仅将Pro delegation恢复True，核对15份公共源码哈希未变，重启本隔离栈Runtime API/Worker。委派组启用前状态记录`.local-stack/relaxed-v3-delegation-handoff.json`。尚未取得委派结果，不预判完成率。
- API关联复验37 passed、266 subtests（6.56s）；Web预算21 passed，vue-tsc与修改文件ESLint均exit0。当前范围仍在推进，均记Phase，不提前作Final结论。

### 2026-10-29 v3委派首轮诊断与新增回归（Phase）

- Pro=True关联Runtime组合348 passed、2 skipped、40 warnings（204.30s）；完整输出为隔离环境`.local-stack/final-runtime-related-tests.log`。这是关联测试集合，不宣称全仓库全绿；日志文件名不代表已进入Final阶段。
- Run `c2c27d29-0b5f-4963-9afb-dd63fc80299f` 已产生三个独立code_explorer命名空间及三份子报告，真实来源通过正式Protocol v2 tools事件只读重放采集。子checkpoint state仅含delta字段，不能以其缺少messages推断未读取。
- 子报告明确指出最早目录/README正文已被折叠；代码检查确认`prune_messages_for_model`只按最近四条ToolMessage保留，未保护最新并行批次，也会折叠当前回合的task摘要。新增T0.P回归；在当前Run终态前不修改公共源码、不重启Runtime。
- 仅停止自动采集器并以单样本模式接续取数，Run继续正常执行；不启动v3委派2/3或串行2/3，以免在已定位缺陷上重复消耗。当前Run结果仍待终态，所有失败保留；新公共修复之后另登记新版本，不混算。

- 上述Run已自然终态：49次调用，input943,668+output33,527=977,195，预算停止，finalized/coverage完整且账本对平，最终55字符无报告；耗时734.051s。primary31次，输入828,494、峰值36,419/131,072（27.8%）；subagent18次，输入115,174、三个namespace。106份来源（其中子级30份）已核对哈希、固定SHA、原文及权限工具集合。`.local-stack/delegation-relaxed-v3-1.json`及audit/sources保留。
- Redis已达511.16MiB/512MiB、noeviction且出现23,163次错误回复与event transport unavailable；捕获root running/completed和0次整理仅为观察值，不能证明事件全量无缺。v3整体标为诊断，既不算通过也不据此计算降幅。
- T0.P先红2 failed，修复后pruning/offloading43 passed；再加Subagent、共享预算、DearFlow装配组合**76 passed、1 skipped、33 warnings（62.71s）**，Ruff通过。实现见`implementation/05-unconsumed-tool-results.md`。
- v4正式采样前只把本隔离Redis改为1GiB，原有5个key保留；同步写所属redis.conf与CONFIG SET，不重启/清空数据库。新组次序委派1/2/3 → 串行1/2/3，公共修复和资源配置统一登记，不能与v3混算。

### 2026-10-29 v4诊断与T0.W（Phase）

- v4 Run `e012aad9-bbb7-494c-80a4-b6cbda18f81f` / Thread `bfead6fc-c9c3-4115-a2fe-610085cb2afd`在诊断出低压力仍被反复折叠后，经正式Web停止，未启动第二/三次；全部失败保留。67次已报告调用的已知input755,535+output34,923=790,458；finalized=false/collection_degraded=true，不宣称完整账单。主4次input65,166、peak19,104；子63次input690,369、peak19,367。没有最终报告，不计任务成功。
- 118份成功来源中111份来自三个独立子namespace，哈希、固定SHA与原文核对通过；全部子工具仍只有github_query。源文件hash在采集结束时没有漂移。root running/interrupted已捕获，观察到自动整理0。
- v4后半段Redis总错误回复增加1、内存远低于1GiB；不能把所有Redis错误等同OOM。v5新增单独OOM计数，并保存每次完整before/after资源快照。
- T0.W新构造参数用例初跑2 failed；实现后的pruning/offloading/agent组合**68 passed、5 warnings（44.47s）**；主/子factory共享水位接线**1 passed、23 deselected（9.97s）**，Ruff通过。详细见`implementation/06-pressure-triggered-pruning.md`。v5仍使用原提示词、模型与1M兜底，两组公共修复一致，不混算旧版本。
- 包含Subagent/共享预算/factory的T0.W关联组合**79 passed、1 skipped、35 warnings（88.06s）**。v5预登记manifest SHA256为`9dc2034f9605cf5b9b250783bfc54e29cbff9b92f4a97b9ad52fb8b15ae26da0`；公共15文件及私有配置哈希冻结，Pro=True开启委派首轮，终态后才继续下一Thread。实际模型调用上限环境覆写为50，旧v3 manifest中100的标签错误已另记更正，运行配置没有改变。

### 2026-10-29 v5失败与T0.D（Phase）

- v5 Run `b741e7ed-102b-42ef-8706-0158d9d02696`自然终态；执行状态success仅表示安全结束，任务失败。969,120 Token（primary63,639/subagent905,481），49次已报告调用、覆盖完整、finalized=true、账本对平；耗时380.89s。主输入峰值16,801/131,072=12.8%，root lifecycle running/completed与整理0次观测齐全。
- 最终55字符预算提示、五项事实交付0/5；三个真实code_explorer子namespace，102份成功来源（子99份）全部固定ref/哈希核对通过。没有用子工具活动冒充最终答案。
- 原始文件SHA256 `55aa34db4f70ad953b2f0c137c65ee604bf2bdfcf22b49856b251690bc2b21c5`；`.local-stack/delegation-relaxed-v5-1.json`及audit/report/source/citation检查保留。终态前停掉自动采集器以防拉起第二轮，补采文件明确标注终态快照；从登记前快照起OOM增量0，公共源码漂移为空。v5第二/三轮未启动，属于诊断版本，不与后续混算。
- 根因：父任务扩成源码审计，子任务45次模型调用消耗905,481；预警只有提示词，最后一轮仍能继续调用工具。T0.D为Run/Thread最后一次模型调用清空工具，为报告保留轮次；子调用上限8/预警2，父级不变。
- 新回归先红6 failed/4 passed。修复组合97 passed/1 skipped/1 failed：残留失败是T0.L扩展github_query只读检测后的旧组合断言未同步；已把github_query纳入期望并验证DearFlow确实覆盖，复测中。Ruff通过。
- v6已预登记16份公共源码、原任务/SHA/模型/输出/1M兜底与环境哈希，次序委派1/2/3→串行1/2/3；仅在相关门禁通过后启动。真实质量尚未验收。

### 2026-10-29 v6交付但质量未达标、T0.Q（Phase）

- Run `22f458d1-42eb-4df4-9a5f-a6b8ac5c7927`：291,599 Token，primary输入100,554/输出6,596，subagent输入170,833/输出13,616；24次完整报告调用，finalized/coverage完整，账本对平，耗时311.92s。主输入峰值24,647/131,072=18.8%，root生命周期running/completed，自动整理0次，无预算停止、源码漂移或新增Redis OOM。
- 三个真实code_explorer，各报告均在4,800字符内（3,408/3,272/2,716）。38份固定SHA来源（子32份）核对通过；6条完整URL引用均落在实际读取窗口，但该检查不等于所有简写引用或语义已验证。
- 交付表格6,658字符，人工核心事实评分3/5：1/4/5通过，2缺默认装配与完整摘要契约、3缺pre-step及replacement前进才重试；额外存在未经证实的依赖关系和后端数量矛盾。**任务已交付，验收失败**，不计算25%降幅；v6后两轮不启动，原始报告/Usage/来源保留。
- T0.Q只补通用行为研究契约，不注入路径/答案；装配与角色3 passed、31 deselected、9 warnings（12.75s），Ruff通过。v7预登记16份公共源码，manifest SHA256 `0891e3fbf8f8ece4beba1bca4c925555a73af72585856bb12495052568739db7`；原题/SHA/模型/预算及全部门槛不变。
- 扩展Runtime组合646 passed、42 skipped、4 deselected、2 failed（396.25s）；两项未改记忆抽取测试在单文件独立复现，测试和对应源码都与HEAD相同，不能宣称全仓库全绿。API37 passed/266 subtests，Web21 passed，vue-tsc退出0，修改文件ESLint退出0/8既有警告，31份Python文件Ruff通过。当前仍为Phase。

### 2026-10-29 记忆抽取测试等待模式修正（Phase）

- 扩展门禁两处失败不是预算/委派生产回归：既有MemoryContextMiddleware默认后台create_task，旧测试直接asyncio.run后断言模型调用次数，退出时后台任务被取消。未修改生产记忆代码。
- 先用现有`MEMORY_EXTRACTION_SYNC=1`在测试进程验证全部16项通过（13.71s），再仅给两项需要完成抽取再断言的测试显式传`sync_mode=True`。默认命令复测16 passed、5 warnings（13.22s），Ruff通过；保留之前失败日志。
- 该测试修正不改变隔离服务配置或v7公共源码哈希。v7全关联集合重新执行中。

### 2026-10-29 v7首轮诊断与关联回归（Phase）

- Run `0a6bfb5d-0b5a-4328-86ef-7490b0b84526`自然终态success，总Token492,336；primary9次、输入199,424/输出9,716，subagent24次、输入263,026/输出20,170；完整33/33账本，finalized/coverage完整，耗时477.57s。主输入峰值32,859/131,072=25.1%，root自动整理0，预算停止无，源码无漂移、Redis无新增OOM。
- 方向二子任务最后轮返回原样DSML工具标记，父级重新委派，实际4个code_explorer命名空间，违反任务最多3个。来源审计保留数量失败标志并继续验证hash，不因数量失败丢弃来源记录：65份来源（子52份）固定SHA/hash/原文核对通过；19条完整路径引用均在实际读取窗口，逗号省略路径引用仍需人工核对。
- 最终响应`finish_reason=length`：4096输出Token包含1835 reasoning Token，5107字符正文在第三部分第一条引用中截断。五项评分1/5：第1项通过，2缺默认装配和完整摘要契约，3缺replacement generation前进才重试，4缺loop之外可选能力，5未交付。**任务未完整交付，验收失败**；v7后两轮未启动，不计算同质量降幅。
- 原始SHA256、Usage、报告、来源及人工评分保存在本Worktree `.local-stack/delegation-relaxed-v7-1.json*`。
- 记忆测试等待模式修正后扩大Runtime关联门禁真实结果：648 passed、42 skipped、4 deselected、100 warnings（370.65s）；skipped不计通过，Final仍未开始。
- T0.F协议回归先红6 failed/4 passed（13.51s）。安装版LangChain在tools为空时不传tool_choice，故改用保留Schema并明确none；Anthropic使用原生type:none，容灾切换重新规范化。真实供应商是否正确遵循仍须v8验证，不能从mock协议测试推断。

### 2026-10-29 T0.F收尾协议回归（Phase）

- `test_execution_budget.py`、`test_model_resilience_protocols.py`、`test_agent.py`、`test_execution_budget_composition.py`组合：70 passed、5 warnings（47.33s），Ruff通过。保留Schema、OpenAI-compatible none、Anthropic type:none及四组跨协议容灾的HTTP请求字段均核对；这不等于外部供应商实际依从性已通过。
- v8预登记22份公共源码，manifest SHA256 `c5113dabafcf0f6e0ba3b5e102d1a902900a7ae9e1e26eee2e324aedc0078307`；原题/SHA/xiaok模型/4096输出与1M隔离兜底不变，委派1/2/3→串行1/2/3。源码冻结，后续任何生产修复都另登记版本，不混算。

### 2026-10-29 v8完整交付但质量失败（Phase）

- Run `806052b6-6753-4d4f-a196-edb679c1ad5a`完整交付，finish_reason=stop，338,340 Token，primary输入123,290/输出6,885、子输入196,563/输出11,602；主峰值26,689/131,072=20.4%，自动整理0次、三子namespace、26/26完整账本、无预算停止，耗时296.24s，无源码漂移或新增Redis OOM。
- 三份子报告为纯文本（1931/1629/1855字符），未出现v7的DSML正文；40份固定SHA来源（子32份）hash/原文核对通过，15条完整路径引用均在实际读取窗口。最终4879字符，五项1/5：1通过；2缺默认启用和完整旧历史摘要契约；3未说明request-error只处理规范上下文溢出；4未说明subagent在loop外的可选性；5未区分fresh/fork历史与外进程形态，反而泛称不接收父历史。任务已交付，质量验收失败，不计算25%降幅。
- 实际轨迹发现GitHub工具错误：三次`operation=readme,path=<子目录>`仍请求根`/readme`，返回根README；这是工具丢弃有效参数，不能靠继续增加提示词掩盖。T0.H修正目录定位，保留v8原始结果，后两轮不启动。
- 原始SHA256 `e2427f085da04da83943189ffb6064ef8c7c68fd4122e0a4394adb58038fc880`，完整私有证据在`.local-stack/delegation-relaxed-v8-1.json*`。
- v8扩大Runtime关联门禁：665 passed、42 skipped、4 deselected、98 warnings（372.77s）；覆盖新增协议与容灾测试。此为Phase，质量未通过不能进入Final。

### 2026-10-29 T0.H目录README路由（Phase）

- 新目录/ref回归先红3 failed（11.90s）；修复后GitHub/研究/Subagent/循环/错误组合135 passed、2 skipped、40 warnings（101.29s），Ruff通过。
- 真实工具读取固定SHA根、compaction与subagent目录，三份返回路径、原文hash与namespace均正确。私有来源审计确认v8三处目录不匹配，整体标志false；hash正确不等于读取位置正确。
- 修复不改变模型/原题/预算/评分，不追加目标路径或答案；v9重新预登记同版本两组三次，真实效果仍待T3.2。

- v9 manifest SHA256 `c1e49666354bbf345a37cbe216d769eb0e5a55b99670dbefd1631304ab43cdda`，公共源码22份；采样次序和v8其余配置相同。


### 2026-10-29 v9来源正确但质量失败（Phase）

- Run `b1a20f3a-f00c-457f-a453-e364dc3cdc60`，Thread `d6efe79b-33b0-42f9-b127-75256a3a5e77`；报告3836字符，finish_reason=stop，耗时503.77s。
- 总490,202 Token：主输入229,634/输出8,177，子输入239,324/输出13,067；主峰值33,795/131,072=25.8%，自动整理0；三个真实code_explorer，31/31完整账本、无预算停止/源码漂移/新增Redis OOM。
- 59份固定SHA来源，目录README全部匹配；内容hash/原文通过。16条含同文件简写范围引用在实际读取窗口内（不能将未解决简写当成通过）。
- 五项2/5（1、3通过）：缺基础装配默认启用、loop外可选边界及完整provider上下文/进程/发现比较。又展开配置、exports和类型清单。完整交付但质量失败；后两轮不启动，不计算降幅。
- 原始SHA256 `a08a6a92cf94662498a6173f17b31fb428060f4885e78e112a0f161e8ac64f74`，证据保存于Worktree `.local-stack/delegation-relaxed-v9-1.json*`。

### 2026-10-29 T0.O父子概述契约（Phase）

- `test_agent.py -k "code_explorer or mode or budget"` → 4 passed、20 deselected、5 warnings（16.24s），父子提示词Ruff通过。
- 只调整通用研究顺序、比较维度和短报告要求；不改原题、模型、SHA、输出、预算、工具或离线评分。
- v10在采样前重新冻结22份公共源码；同版本委派1/2/3→串行1/2/3。该最小门禁不代表真实质量通过，Final未开始。

- v10 manifest SHA256 `bcd868f07757f4de8aa3788d6aa73a86da5a4647f961e4b6991b6c28c5c2f468`；首轮Thread `a119300b-267a-4179-9ac8-8b719f429435`、Run `29103d60-664b-4543-a0b0-082eb5da5005`。首次来源订阅遇到Run列表尚未可见，随后按since=0重放成功；采样脚本增加有界等待，不改被测任务。


### 2026-10-29 v10交付截断与协议失效复现（Phase）

- Run `29103d60-664b-4543-a0b0-082eb5da5005`，总465,260 Token：主输入288,719/输出9,022，子输入154,371/输出13,148。主峰值35,160/131,072=26.8%、整理0，三子、30/30完整账本，349.04s，无源码漂移/新增OOM。
- 46份固定SHA来源（子30），目录全部匹配、hash/原文通过；28条引用含同文件简写均在实际读取窗口，未解决简写0。
- 第三子在第8次最后模型调用仍输出DSML正文；父未重派、改自行补查。最终报告finish_reason=length，4096输出含1964 reasoning，第三方向未完成；五项3/5，另有五种/六种数量矛盾和依赖推断。任务交付失败，保留全证据、不启动后两轮、不计算降幅。
- T0.J拟撤除Schema并通过ModelRequest.model_settings保留协议原生none，避免LangChain空tools分支丢弃tool_choice。共同单次输出改为8192后重登记v11（仅隔离测试，不改产品默认）；该值同时给reasoning与正文使用，不是Run额度或窗口大小。


### 2026-10-29 T0.J无Schema收尾（Phase）

- 查阅LangChain docs动态工具选择与reference ModelRequest，并核对安装版factory：空工具分支只bind(model_settings)，request.tool_choice会被忽略。因此撤除Schema时必须用model_settings继续传none。
- 新回归先红8 failed/4 passed、16 deselected、5 warnings（14.06s）；修复后ExecutionBudget、跨协议容灾、Dear Agent装配及预算组合70 passed、5 warnings（59.08s），Ruff通过。
- 同步/异步OpenAI-compatible和Anthropic真实SDK HTTP mock载荷均无tools且带原生none；DeepSeek/OpenAI-compatible/Anthropic四组容灾方向保留禁止语义和历史。Mock不能证明外部供应商依从。
- v10原始SHA256 `99a523c3359057039b6886f1f0f77a24f54f9d1d4e72a82b6c630c0ac0fb1f16`。v11 manifest SHA256 `4706f814559cc4192ce622a636f35c87153bd4600e669ad4cf6e80bef956f61a`，22份公共源码；任务prompt哈希和隔离env哈希不变。
- v11两组单次输出统一8192，既用于reasoning也用于正文；1M Run兜底/131072配置窗口、原题/固定SHA/模型/质量条件不变。不把此前输出截断当上下文溢出，也不混算版本。未进入Final。

- v11首轮Thread `c139b4ea-6107-4ce5-b380-1966ec6bca97`、Run `d459f727-0ddf-47aa-b179-fdc76a7ad15b`，正式UI已固定8192；38个修改Python文件Ruff全部通过。


### 2026-10-29 v11委派样本1（Phase，通过）

- Run `d459f727-0ddf-47aa-b179-fdc76a7ad15b`，405,454 Token：主输入248,931/输出9,475，子输入134,744/输出12,304。主峰值36,609/131,072=27.9%、自动整理0；三真实code_explorer，25/25完整账本，319.74s，无预算停止、源码漂移或新增OOM。
- 三子报告纯文本（1713/2492/3123字符），无DSML；最终4681字符、finish_reason=stop。50份固定SHA来源（子32），目录、hash、原文与namespace核对通过。
- 五项事实5/5：能力组织、compaction默认/触发/剪枝/重试、loop外可选多注册、进程内外/父历史与发现均在报告及已读引用中得到支持。24条路径/同文件范围引用通过；另有无目录README.md#L73-L74，按compaction-basic本节语境人工定位，73–74确在模型已读窗口。
- 保留写作局限：3.5的窄引用单独不覆盖list_agents/interrupt，同报告3.1的subsystem#L7直接支持；1.3用两份package.json概括统一导出，离线核对15包确实一致。离线核对不计作模型额外读取/Token或加分，不宣称每行引用排版完美。核心五项按已批准口径通过，无虚构路径或事实。
- 首轮通过后继续同版本样本2/3，未修改公共源码、原题、模型、输出或评分；尚未完成三次稳定性与串行对照，不能进入Final。

- v11样本1原始SHA256 `d329d78ff38d5fcdcc930ea9d251cf274815a885ca5ae396eb8af4523238d820`。


### 2026-10-29 v11连续三次委派与模型交叉验证（Phase）

| 次数 | Run | 总Token | 主输入 | 主峰值 | 耗时 | 核心事实 |
|---|---|---:|---:|---:|---:|---|
| 1 | `d459f727-0ddf-47aa-b179-fdc76a7ad15b` | 405,454 | 248,931 | 36,609 | 319.74s | 5/5 |
| 2 | `0bfb70c6-0116-4de3-83b9-efb002a885b1` | 477,579 | 269,114 | 32,276 | 326.65s | 4/5 |
| 3 | `92b72643-487e-4ca8-accc-b637e3abbdd3` | 314,535 | 164,511 | 32,083 | 295.75s | 3/5 |

- 三次报告均正常结束、三子、root整理0，全部账本完整且无源码漂移/新增OOM。主上下文峰值24.5%–27.9%，已不是上下文爆满导致失败。
- 质量仅1/3达标：样本2包后端数量4/6自相矛盾，第1项失败；样本3缺默认装配与pre-step/generation完整重试契约，第2/3项失败。旧失败保留，不因第一轮通过就宣称三次稳定，也不以平台success等同质量完成。
- 49份/38份来源分别核对；样本2审计扩展root yaml、唯一文件后缀后34条引用通过；样本3剔除Markdown链接label的重复简写推断后39条通过。私有审计器带解析自检，修正只影响取证，不修改原始答案或生产代码。歧义README仍须人工定位。
- v11未达到委派三次质量门槛，不运行其串行组或计算25%降幅。原始3份和人工评分完整保留；后续不是挑选成功样本替补。

### 2026-10-29 v12 xiaok GLM-5.3预登记（Phase）

- 使用另一已配置且已授权的xiaok模型 `glm-5.3`（ID `2ee61b35-ccf0-4f51-97dd-0ecede296162`），catalog配置窗口同为131072。供应商实际部署指纹/窗口元数据仍未报告，不能套用DeepSeek官方参考窗口。
- 公共源码沿用v11的22份冻结文件，无新增提示词或生产修复；原题prompt哈希、SHA、预算env、8192输出、调用额度和评分均不变。仅模型组更换，在新组内部仍以delegation开关为唯一对照差异；不与DeepSeek组混算。
- manifest SHA256 `ab09be41e94b481431fc1030a1936506bd91438273b5fad4b5a8bc5900db90a5`，次序委派1/2/3→串行1/2/3；先验证首轮质量后继续后两轮。不从余额或模型标签推断能力，效果以真实结果为准。


### 2026-10-29 v12质量失败与子调用边界诊断（Phase）

- Thread `b5a1612c-16f7-4ac7-8fcc-eee8648ac564` / Run `dfb15d67-dee4-48e2-b717-f9fbc85c7220`：25/25调用均为xiaok GLM-5.3，finalized/coverage完整，225,701 Token；主输入83,093/输出3,566、子输入134,746/输出4,296，账本对平。主峰值19,585/131,072=14.9%，root整理0，无源码漂移或新增OOM。
- 最终6491字符、finish_reason=stop，但五项仅2/5：包组织与loop外可选registry通过；缺默认启用、pre-step/generation重试完整条件及fresh/fork历史/运行位置对照。第三子第8次返回原始tool_call正文；另一子7次后明确说明预算耗尽未读完整生命周期。低上下文占用并不等于任务完成。
- 来源审计初次断言失败：误将`operation=info`仓库元数据也要求固定ref。修正审计适用范围后，31份来源（28份子来源）hash/身份通过；30份file/readme/tree内容固定SHA，1份info只证明仓库元数据，不算提交内容。目录匹配，20条引用窗口通过；原始失败与报告保留。
- 原始文件SHA256 `9cad658591d227afc98d38fcccf607094f02730d250e889c668967e3b8d7d382`；私有证据`.local-stack/delegation-relaxed-v12-1.json*`。不启动后两轮，不混算v11或计算25%降幅。
- T0.N只将子调用硬上限8→16并同步角色说明；预警2、工具48、全局1M、输出8192、模型、原题与评分不变。先红装配回归2 failed/22 deselected/5 warnings（17.17s）；真实改善仍须v13检验，不解析或执行正文中的原始工具标记。


### 2026-10-29 T0.N子模型额度回归与v13登记（Phase）

- DearFlow装配/Subagent边界/并发共享预算组合：34 passed、1 skipped、33 warnings（74.15s）；修改3份Python的Ruff通过。生产只改子模型上限8→16及对应说明；预警2/工具48/主额度/全局预算不变。
- v13 manifest SHA256 `f5f9e92a2696e9ff653c5ffa60b706c0f38e917389b882f09b8347c6d3383f83`，22份公共生产源码哈希冻结；保持xiaok GLM-5.3、8192输出、原题和固定SHA。委派1/2/3→串行1/2/3，旧诊断全部保留。
- 主目录对应43份app文件重新核对均与HEAD相同，无冲突；当前仅核对归属，尚未整合源码。Final未开始。

- v13首轮Thread `29e109fe-c3bc-4b83-8dbd-1fce49d64305` / Run `b8e891ea-f82e-4857-924c-585e967919b9`。提交后Run列表短时不可见，初次来源订阅超过10秒等待；随后用since=0成功重放，未重发用户任务、未产生替补模型样本。原采集失败日志保留。


### 2026-10-29 v13子额度放宽仍质量失败（Phase）

- Run `b8e891ea-f82e-4857-924c-585e967919b9`：39/39调用、399,595 Token，主输入81,867/输出3,353、子输入308,914/输出5,461；210.38s。完整账本，峰值18,963/131,072=14.5%、整理0，无源码漂移或新增OOM。
- 三个子namespace分别7/16/11次调用。compaction子第16次仍返回原始tool_call正文；另两子已报告默认启用、loop外可选与fresh/fork比较，父报告却丢失前两点。最终5246字符、finish_reason=stop，但核心2/5（1/5通过，2/3/4失败）。扩大子额度没有解决该GLM路径的交付与整合可靠性，不继续提高上限。
- 43份固定SHA来源（39份子来源）hash/目录/原文通过；15条引用检查中pruner的URL指向未读L88-L90，label却写L12/L44/L48，属于真实错配，不放宽为通过。全文原始文件SHA256 `b4a602251d941e19bf18808df716d5e528bc2d27550ecb8d2af69c7ec8d0b14d`。
- v13首轮完整保留，后两轮不启动；不能将子模型上限调整说成质量修复已验证。T0.N只证明配置接线与共享准入回归通过，真实改善继续由T3.2验证。Final仍未开始。


### 2026-10-29 v14 DeepSeek子额度16预登记（Phase）

- 沿用v13全部22份公共生产源码，无提示词改动；模型回到已配置xiaok `deepseek-v4.1-flash`（ID `070cced3-350b-42ec-b678-994dd07b7078`），子16/预警2/工具48，输出8192、Run1M、原题/SHA/五项门槛不变。v11同模型三次子报告都为纯文本，但仅1/3质量通过，此事实不证明v14效果。
- manifest SHA256 `e2ca9be85066681f05dcf749938ab14b1302a62306e94e08c28bd0836c2f497d`；次序委派1/2/3→串行1/2/3，不混算GLM或旧子额度8的v11。首轮Thread `9380684c-ff5f-4bd2-b104-fc5064f8c059` / Run `855df3c2-f0fb-47fe-8dff-4710def855ef`。


### 2026-10-29 v14完整交付仍质量失败（Phase）

- Run `855df3c2-f0fb-47fe-8dff-4710def855ef`：39/39同xiaok DeepSeek调用，781,815 Token，主输入384,446/输出11,616、子输入367,318/输出18,435；461.81s。峰值49,086/131,072=37.5%、整理0、三子纯文本、完整账本、无源码漂移/新增OOM。
- 78份固定SHA来源（子52份），43条引用窗口通过；最终5825字符、finish_reason=stop。核心3/5：1/3/4通过，2把基础默认启用当未知，5缺父级发现。额外依赖/目录不存在断言证据不足。保留失败，后两轮不启动，不计算25%降幅。
- 原始SHA256 `7db6c79dd3a4dc0583db9e47249cdb078f865e41fb24086af80ccb1eaf65302d`。原始委派描述再次扩成依赖、patch配置与2–4实现文件审计，说明提示词不能被当成硬性范围保证。

### 2026-10-29 v15独立配置模型预登记（Phase）

- 公共源码完全沿用v13/v14；使用已配置xiaok `step-5-preview`（ID `7a1034b5-ac3c-4d12-aa5c-5df5afed7ddf`），配置窗口131072。保持原题/SHA/输出8192/Run1M/子16与评分，不宣称模型本身更强或已证明通用收益。
- manifest SHA256 `8c5ee27119abbe30c95ac5a6827b5922a719baf779f4a70ca31dca43d698be10`，同模型委派1/2/3→串行1/2/3，不混算其他模型或版本；先验证真实首轮。


### 2026-10-29 v15建图失败与v16登记（Phase）

- v15初次UI模型列表暂时读取失败，未提交Run；保留采集器JSON解析失败日志，刷新页面后正式提交一次。Thread `fb3fea63-5cf6-4419-834f-01cbb845623d` / Run `ff83a2de-80e9-4f24-a610-08d6c785ca6a`在1.19s终态error，SSE明确failed，模型调用观测0、用量未知，不把未知账单当0。
- 实际异常来自`_input_budget()`的`runtime.context.output_budget_exceeded`：既有`resolve_model_max_output_tokens()`把未识别Step族推断为4096，而实验输出为8192。属于调用前配置兼容问题，不能推断供应商接口或模型能力；没有降低本组输出上限、篡改profile或重试替换该失败样本。
- v16沿用相同22份生产源码，选已配置xiaok `kimi-k3`（ID `bcaf9543-5cc9-40cb-9848-d1fbe90cc086`）；catalog窗口262144，现有族规则允许8192输出。原题/SHA/预算/子16/质量评分不变，只有本独立模型组使用其真实配置窗口，不将不同窗口/模型混算。
- v16 manifest SHA256 `b59e8e10dce50be163cc6a270850aa19c96bc5ebe700a12e4769e6363c517e3a`；同模型委派1/2/3→串行1/2/3。实际provider部署指纹、窗口元数据与价格仍未报告；不保证实际tokenizer或账单硬封顶。

### 2026-10-29 v16低上下文但证据整合失败（Phase）

- Thread `389f41fe-3d72-412b-8e7b-51c74ad4b256` / Run `d50fd1a3-7496-4163-b195-0867e7b356a1`，390.33s、393,905 Token；主2次输入26,622/输出2,350，子32次输入355,933/输出9,000。主峰值14,728/262,144=5.6%、整理0，三子4/15/13次，34/34账本完整、无源码漂移/新增OOM。
- 41份固定SHA来源（全部子读取）、27条引用窗口机械通过；最终4363字符正常结束。人工核心2/5：1/5通过；2缺较早历史摘要；3缺request-error仅规范上下文溢出限定；4的loop外可选结论所引L13-L36不支持，不能从实际读过但未正确引用的L5补分。第5项spawn/fork位置由同报告其他正确引用支持，但本行引用不够完整。
- 三个子报告纯文本。父零次来源核对，直接重排；子概述无独立引用，最终保留多项类型/锁细节却遗漏关键限定。下一步只修通用证据交接和核查，不提高额度、切模型或注入目标答案。首轮失败保留，后两轮不启动，不计算降幅。
- 全部调用model ID为登记Kimi；最终响应模型别名`kimi-k3-1`，没有部署fingerprint。原始SHA256 `f67ab38ee7cfa4c5b9fe468005ea1c28fb08a6c00a7e6c7fe0cf07cae2898c48`，人工评分与全部私有证据保留。

### 2026-10-29 T0.V证据交接与v17登记（Phase）

- Pro/Ultra装配回归先红2 failed、22 deselected、5 warnings（12.35s）；父子通用证据交接修改后，装配/Subagent/共享预算34 passed、1 skipped、33 warnings（54.68s），三文件Ruff通过。该断言只验证指令接线，不证明模型遵循，真实效果由T3.2核验。
- 只要求子概述并入有引用结论、压缩保留限定/作用对象/先后关系；父在最终表格前批量核对每个原问题的一处关键来源，不加评分答案或目标路径，不重派子任务。沿用已有GitHub工具，不新建验证器或LLM调用层。
- v17 manifest SHA256 `6917f6fbcd97dc0f588631d5ddbfa3522c51fcbd3b10d73b8ef3c0dc1ca147a4`，冻结22份公共源码；同xiaok Kimi-K3/262144窗口、原题/SHA/8192输出/Run1M/子16。次序仍委派1/2/3→串行1/2/3，v16失败不替补、不混算。

- v17首轮正式UI：Thread `928536a3-27f1-4f89-bb3b-7f99e4c1a8e9` / Run `a99de371-e258-413c-8907-ad3c17de4dd3`；仅重启本隔离Runtime API/Worker，新pid73622/74246。

### 2026-10-29 v17实际核查发生但比较覆盖不足（Phase）

- Thread `928536a3-27f1-4f89-bb3b-7f99e4c1a8e9` / Run `a99de371-e258-413c-8907-ad3c17de4dd3`：239.74s，271,796 Token；主7次输入126,230/输出5,230，子19次输入133,249/输出7,087，26/26账本完整、峰值23,585/262,144=9.0%、整理0。三子均纯文本，无源码漂移/新增OOM，响应别名仍`kimi-k3-1`。
- 36份固定SHA来源（28子）、21条引用窗口通过。父有8次成功原文读取，但另有2次缺path/ref参数调用在工具边界失败、未返回源码，保留参数失误。不能把所有调用均固定ref写成true。
- 人工4/5：1/2/3/4通过；5未交付父已完成历史边界与父级发现，不能用子报告已有发现代替。类型/activation细节再次替代了统一维度比较。最终7597字符正常结束；个别总体组织断言的行内引用过窄，保留局限。T0.V只证明核查发生，没有证明稳定质量。
- 原始SHA256 `8e651be6e87a3f3d3667b759fd78e19eeea67edd1e6b279336d4066b95e0c38a`；首轮失败保留，后两轮不启动、不计算降幅。

### 2026-10-29 T0.X比较维度与v18登记（Phase）

- 最小Pro/Ultra装配2 passed、22 deselected、5 warnings（11.03s），修改三文件Ruff通过。该测试只核对指令装配，真实依从性仍待验证。
- 不继续叠加概述清单，直接规定比较表格以提供方为行、初始历史/运行位置/父级控制为列；移除父提示词与多提供方比较冲突的最多六行软约束。已证实的限定不能因排版丢失，未知单元格明示；不加目标仓库事实或路径。
- v18 manifest SHA256 `399e37ad93bbd63de29538e5dafe9b6b09e91c8897439ddcb0844507676d610b`，同22份公共源码冻结，只有上述通用交付格式修改；Kimi配置窗口262144、单次8192、Run1M、子16、原题/SHA/评分均不变，委派1/2/3→串行1/2/3。旧失败全部保留，不替补或混算。

- v18首轮正式UI：Thread `b5e40425-4144-44a1-9480-14b7ab6ebfd4` / Run `9984e286-6898-4d81-b22a-b807b183c2dc`；Runtime API/Worker归属本隔离栈，新pid86552/87105。

### 2026-10-29 v18预算异常与子任务隔离修复（Phase）

- Thread `b5e40425-4144-44a1-9480-14b7ab6ebfd4` / Run `9984e286-6898-4d81-b22a-b807b183c2dc`，294.52s，终态error，未交付最终报告（0/5）；后两轮未启动。一个子第16次响应在工具声明已撤除、tool_choice=none时仍返回原生tool_calls；系统执行该工具后，下一步抛ModelCallLimitExceededError并穿透task，父无法整合另外两个成功子报告。
- 初始Usage HTTP200、34次观测/报告调用、missing/incomplete为0，但finalized=false、collection_degraded=true、availability=partial；稍后独立补查仍相同。完整Token总量为null，仅已知373,518（input365,006/output8,512）；不将已知和改称完整账单。主1次input12,010/output690，子33次input352,996/output7,822；主已知峰值12,010、自动整理0，不代表质量通过。成本仍unknown。
- 37份来源全部由三个独立code_explorer读取；固定SHA、来源hash、namespace及原文逐份通过核对。无公共源码漂移、新增Redis OOM=0；Redis其它错误回复增加2，未归因为OOM。原始文件SHA256 `4fba6228cae901664b7c94680bc526087a9c67c80de61e263dedb9d5cceab938`，原始快照、独立usage-refresh和sources审计均保留，不覆盖初始unknown。
- T0.I对抗回归先红5 failed/38 deselected（14.59s）；修复后预算/子隔离等组合90 passed/1 skipped，唯一旧测试仍要求子预算拖垮父，正在改成失败反馈与父自身限额不重置。GitHub文字定位先红1 failed/23 deselected（11.42s）。新组合157 passed/1 skipped，残留是测试误读隐藏计数字段，已改成验证实际模型/工具调用边界；未据此启动下一真实样本。

### 2026-10-29 T0.I/T0.A回归与v19冻结（Phase）

- 末次工具响应拦截、只读子额度失败隔离、父自身限额、GitHub字面定位及既有重试联合159 passed、1 skipped、62 warnings（53.15s）；本轮九个Python文件Ruff通过。跳过项与既有第三方警告未当作通过。先前测试误读隐藏计数的失败保留，最终改成实际请求与工具执行边界断言。
- v19 manifest SHA256 `940885793c27e7bf668062a7fbf2080270df18355cc3a834c331987c228135d5`；22份公共源码hash、测试私有环境hash及两臂Pro delegation唯一开关hash固定。原题/SHA、xiaok Kimi-K3、窗口262144、输出8192、Run1M、主50/工具100、子16/工具48不变。先委派连续三次，再同配置串行三次；旧失败不替补、不混算。
- 当前44个app文件逐份确认主目录仍等于HEAD，无覆盖冲突；仅记录整合范围，尚未复制主目录、提交或部署。Final未开始。

- v19首轮Thread `f4380417-4e4d-43ce-bc5b-177965379a7d` / Run `f68f687a-dcf8-4e01-9c79-1b1cd6e8be16`；仅重启本隔离Runtime API/Worker，pid19357/20166。44个app文件中的39个Python文件Ruff全通过。manifest资源快照继承自v18，仅作历史；已另存addendum纠正，v19使用collector实际before/after，不宣称覆盖重启及collector前区间。

### 2026-10-29 v19低上下文、来源漂移与质量失败（Phase）

- Thread `f4380417-4e4d-43ce-bc5b-177965379a7d` / Run `f68f687a-dcf8-4e01-9c79-1b1cd6e8be16`，338.80s、356,676 Token；主5次input96,935/output4,316，子27次input247,334/output8,091。32/32完整账本、finalized=true、availability=available、无预算停止；主峰值24,191/262,144=9.2%、root自动整理0。报告5297字符正常stop，响应别名kimi-k3-1；记录区间无新增OOM/源码漂移，其他Redis错误增加1。
- 人工核心4/5（1/2/3/5通过）；第4项虽称可选能力，却没有交付主循环之外边界，不能用结尾列出的子引用代替未陈述的事实。30条可解析引用落于已读窗口，但另有3条简写未解析（#L84-L86、pruner/README.md#L44、#L34），不宣称引用全通过；局部原文核对不能保证整体忠实整合。
- 来源46份（子37），其中44份file/readme/tree、2份info/commits元数据。两个子调用未传ref，工具默认读取master；其中README原文与固定提交实际不一致，不是单纯参数格式问题。hash/namespace均可核验，但这两份不是固定来源；来源审计明确失败。最终“所有读取均显式SHA”的声明不实，后两轮不启动。
- 原始SHA256 `8bb8f7e229d651f6c322ddc5452d95bf4958bf67a730c6b748fe8089b071d422`。初次审计的assert失败日志保留，私有审计器改成先保存非固定来源及原文差异再以非零退出，不把失败吞掉。无重跑评分覆盖人工结果。
- T0.SHA新增工具前置版本校验及安全纠错提示，先红7 failed/67 deselected/5 warnings（10.34s）；同时修正技能中不带ref的README/tree示例，与新入口规则一致。没有增加目标SHA、路径或答案式指令。

### 2026-10-29 T0.SHA回归与v20独立Step组登记（Phase）

- GitHub版本前置校验、安全错误、旧读取/证据契约与Agent/子装配组合136 passed、2 skipped、44 warnings（115.48s），四个本轮Python文件Ruff通过。两个skip不计pass，第三方警告保留。
- v20 manifest SHA256 `20788df86b8126a390cd1dc197418793ea5d07a2003b440481b9025d5eb19e4b`，冻结同22份公共源码；xiaok已配置Step-5-preview，model ID `7a1034b5-ac3c-4d12-aa5c-5df5afed7ddf`，配置窗口131072。单次4096是当前Runtime未知模型族的保守上限，不是供应商真实输出上限；v15的8192建图失败继续保留。
- 两臂同原题/SHA、模型/窗口/4096输出、Run1M、主50/工具100、子16/工具48，仅Pro delegation不同；先委派1/2/3再串行1/2/3。模型和输出与v19不同，整组独立，不混算或声称单一因素收益。价格/部署fingerprint/供应商真实窗口未提供，保持unknown/not_reported。

- v20首轮正式UI已发出：Thread `25485b77-1a0e-48e2-82a0-5bc13fbdbc5a`；Runtime API/Worker所属本隔离栈，pid41601/42284，模型选择精确校验Step/xiaok、单次4096。

### 2026-10-29 v20首调用失败且用量不可核验（Phase）

- Run `58fa9059-a418-4c93-8d12-16c1f8f74480` 在7.73s终态error，未交付报告、未启动子任务，人工0/5；后两次未启动。原始SHA256 `418281f93aa91a00ad8bd444520e3683f9dc7d95a65ce081502847ca0ab1ed10`，保留完整原始数据，不替换失败。
- Usage HTTP200、finalized=true，但1次观测主调用为failed/missing，报告调用0；Token和成本均未知，不将known_used=0当成实际消耗0。终止原因是`token_budget_unverifiable`；现有日志仅证明后续准入因不可核验停止，尚不足以判定首次失败来自供应商还是回调，不能直接归因预算不足。
- collector资源采集区间21:11:46–21:11:54 UTC晚于Run结束；该区间无新增OOM/源码漂移，其他Redis错误+1，不能用它证明Run执行区间无资源异常。独立诊断与下一模型组另登记，不混算。

### 2026-10-29 v21显式ref边界后的Kimi独立组预登记（Phase）

- 生产代码与v20相同，22份公共源码hash全部核对；改回已配置xiaok Kimi-K3（ID `bcaf9543-5cc9-40cb-9848-d1fbe90cc086`），配置窗口262144、输出8192，原题/SHA/Run1M/主50/工具100/子16/工具48与评分不变。不注入目标路径或答案，不与v19/v20混算。
- manifest SHA256 `c863f8c57b4e5258adfb6987183bd2deae4f0dc08a8f2219b5a36bc71443e057`；委派1/2/3→串行1/2/3，仅Pro delegation开关不同。前序失败全部保留，真实调用已持续授权；价格、部署fingerprint和供应商窗口仍未知。
- 首轮Thread `d2f6557f-fa82-47a3-b368-19aef3775be0` / Run `120bc4ee-5317-4890-8bbe-d18906b9886a`，正式Web提交；未修改生产代码或重启其它环境。
- Step独立短请求诊断HTTP503，错误码`model_not_found`，供应商明确表示当前分组无可用通道，usage未返回。该探测与v20原调用分开保留，不据此把原调用未知消费补零，也不声称已还原原始失败栈。
- 在查看v21首轮最终质量前固定执行纪律：无明确实现缺陷或基础设施故障时，按登记次序完成当前版本两组各三次；语义遗漏照记失败，不以提示词微调、重采样或只保留成功轮次替代连续观测。三次委派全部质量通过的验收门槛不变。

### 2026-10-29 v21委派首轮完整交付（Phase）

- Run `120bc4ee-5317-4890-8bbe-d18906b9886a`，465.76s、457,343 Token；主9次input152,930/output3,951，子31次input293,634/output6,828。40/40完整账本、available/finalized、stop_code=null；主峰值21,223/262,144=8.1%，root自动整理0。一个只读子额度失败如实返回，父级直接补查完成，未重派或伪装子任务成功。
- 人工五项核心5/5：仅按最终报告跨表格语义核对，不使用子报告补缺。第2项由压力压缩、`/compact`、先剪枝、基础默认启用及“早期已关闭step可压缩”的最终表格行共同覆盖；第5项由包表和提供方比较共同覆盖。44份来源（子35份）逐份固定SHA/hash/namespace核验通过。
- 引用机械审计25条覆盖、无未读窗口，但根`README.md#L5-L7`因通用同名解析器判为歧义；人工按该表格的仓库相对路径及实际根README窗口复核，单独记录解析结果，不改机械原始结果。提供方真实窗口、部署fingerprint和价格仍unknown，不将配置窗口称为供应商容量。
- 原始SHA256 `8d95f46d75fa5fa2c32042ff298ae6b51ee8d958770686ca9eee4678db137e92`。连续第2/3轮已按同一冻结实现启动；此单次结果不代表稳定性验收，也不计算25%降幅。

### 2026-10-29 v21委派第二轮（Phase）

- Thread `4c023f16-6336-427f-90cf-7eb4f7c7f98b` / Run `d231114c-204e-409c-ae63-fd5d4c7dcfa0`，236.85s、279,991 Token；主4次input66,730/output3,449，子22次input202,342/output7,470。26/26完整账本、available/finalized、stop_code=null，三子全部成功；主峰值20,493/262,144=7.8%，自动整理0。
- 五项核心人工5/5；40份来源（子34）固定SHA/hash/namespace核验通过。机械25条引用覆盖但“同上#L113”未解析，人工按上一行完整路径指向实际读过的compaction-basic README L111-L118；逗号后的行号逐一人工核对已读窗口，不把解析器未抽取等同自动通过。
- 限制：扩展提供方表把多个进程外后端的播种方式合并，紧邻引用并未逐一支撑所有额外细节；核心第5项另有包README与fork README的正确引用，按原五项口径评分，不据此声称任意附加细节均已核实。
- 原始SHA256 `3ee9e5688919f3c8d70cee6fdb34ff8f4792fcf990d9bb59fc5864bac6c98fd3`。第三轮Thread `5d541b25-edb0-484a-a50f-9e65b111ac51` / Run `67c94ead-3df9-402d-9323-bb249700f958`已按同配置启动，继续原登记序列，不补样本或修改提示词。

### 2026-10-29 v21委派第三轮与固定组判定（Phase）

- Run `67c94ead-3df9-402d-9323-bb249700f958`，219.89s、216,350 Token；主3次input45,933/output3,628，子20次input159,483/output7,306。23/23完整账本、available/finalized、stop_code=null；主峰值18,418/262,144=7.0%、自动整理0；34份来源（子31）固定SHA/hash/namespace通过，20条解析引用均在已读窗口。
- 最终报告核心3/5：1/3/5通过；第2项漏“摘要较早历史”和基础配置默认启用，第4项只称可选能力，未交付agent-loop之外边界。不得用子报告或引用文件本身补齐未陈述结论。附加提供方生命周期表也过度统一，保留局限。原始SHA256 `7b2d92e2990fb5506ca859a0953fdd07af2ab4d8de3962c8ce6a2c682e265da8`。
- 本版本连续三次委派核心得分5/5、5/5、3/5，合格率2/3，**未通过三次全部质量合格门槛**。三次均低上下文/无整理且完整记账，只能证明当前样例的窗口治理，不证明稳定事实交付。全部保留，无替补或提示词微调。
- 按预登记继续同版本Kimi串行三次，仅Pro delegation由true改false，hash与manifest串行臂一致；其余22份公共源码/模型/预算/窗口/输出不变。仅重启本隔离Runtime API/Worker，完成后恢复委派实现；未向主目录合并或部署。

### 2026-10-29 v21串行首轮（Phase）

- Thread `dd0f28cc-37b6-4e33-ac82-d054e976e8f7` / Run `a05ce3b8-9abc-492c-b478-ad2d54fc85b7`；同一Kimi模型/262144窗口/8192输出/Run1M与公共实现，只有Pro delegation=false。14次全部primary，input319,545/output5,899，总325,444 Token；账本完整、finalized/available、无预算停止，主峰值33,172/262,144=12.7%、自动整理0。
- 人工核心4/5：第2项缺随附基础配置默认启用，其余通过；不能用引用文件中的默认启用原文替代最终报告漏项。30条机械解析引用均在已读窗口。附加提供方表“占活跃槽”与报告前文一次性运行不占continuable槽的叙述矛盾，保留局限。
- 第二轮Thread `c6dadd8b-ff32-4d8c-bafe-d91a1aec858b` / Run `fbf196b9-e565-4679-8580-d7a66affc1f3`已按同配置启动，继续连续采样，不因首轮失败替换或调提示词。

### 2026-10-29 v21串行后两次异常，整组保留（Phase）

- 串行首轮227.66s，21份固定SHA来源通过，原始SHA256 `e9e0848f4bbb84f5b646a476dc4b8e3cae485037bb8277db826f61574aadac64`。
- 第二轮Run `fbf196b9-e565-4679-8580-d7a66affc1f3`，97.43s，6次观测/5次有用量，最后调用failed/missing，无完成报告（0/5）。已知66,673 Token（input65,589/output1,084），完整总量null；预算因`token_budget_unverifiable`停止，不能补零或把已知量当全账。原始SHA256 `1dc8bebb7ed5d540ae1d1088f14b69771cd10975dcc7058a136fd4d800f02618`。
- 第三轮Thread `a4be766b-7ff7-4d5c-b440-81d024418713` / Run `ab700b7f-f208-4360-9c23-237a8aa79016`，12.23s，首次观测调用failed/missing，Token未知、无报告（0/5）；原始SHA256 `e817a5773a8fcc6ebeeba895a57900689598d573eea5dfe44ffb2199b188d67a`。两个原始异常原因未确证，后续预算保护拒绝不等于原始原因；资源采集区间无新增OOM/源码漂移。
- v21完成六次预登记终态，但委派核心2/3、串行核心0/3且后两次用量不完整；不能形成合格同质量对照，也不计算串行完整用量中位数或25%降幅。失败和所有原始文件保留。
- 独立短探测：xiaok Kimi HTTP200/有usage，maomaoai DeepSeek HTTP200/有usage；xiaok GLM5.2 HTTP503/无可用通道。短探测只说明该时刻小请求状态，不能还原失败Run或证明长工具调用稳定性。真实模型测试持续授权，无需再次询问费用。
- T0.Y从两臂共同出现的遗漏出发，仅把已要求的通用概述字段改成显式表格列，防止默认装配/主循环关系仅留在引用中；不加入目标事实或路径、不增LLM层。v21整组已经结束后才改，新版本重新冻结与采集。
- 六次完整汇总、逐项人工评分、缺失用量和原始hash见[可复核JSON](implementation/19-v21-controlled-comparison.json)；unknown保持null，未将串行部分已知量混成完整账单。

### 2026-10-29 T0.Y回归与v22预登记（Phase）

- 新装配断言先红2 failed、10 passed、12 deselected、5 warnings（31.61s）；最小修改后Agent/Subagent/共享预算35 passed、1 skipped、37 warnings（68.51s），本轮三文件Ruff通过。只证明格式接线与既有边界，真实效果仍待验证；见`implementation/20-capability-overview-table.md`。
- v22 manifest SHA256 `1587ec76db2e894c7c491a893dcc8a5a7cecd2033f9a80e2d1e462bc6a21d947`。同Kimi/xiaok、配置窗口262144、输出8192、Run1M、原题/SHA、主50/工具100、子16/工具48；仅两份提示词的通用概述格式改变，不加入仓库事实或路径。重新冻结22份公共源码与测试环境，先委派三次、再串行三次，只切Pro delegation；连续终态不补样本，不与v21混算。

### 2026-10-29 v22委派首轮：窗口受控，语义交付仍有遗漏（Phase）

- Thread `72225b49-4249-4643-af8c-0cba92c108f2` / Run `ed08bbb0-7f51-41c7-a442-2fdc3db51d19`，440.83s、435,541 Token；主11次input229,335/output6,345，子23次input191,845/output8,016。34/34账本完整、available/finalized、stop_code=null；主峰值29,135/262,144=11.1%、自动整理0。三次真实code_explorer、49份来源（子32）固定SHA/hash/namespace通过；31条机械解析引用均在已读窗口。
- 最终报告人工核心4/5：1/3/4/5通过，第2项未说明摘要较早历史。复核第5项按最终报告跨行语义覆盖：进程内形态名称、fork对话播种、父级已完成轮次前缀与fresh子代、四种外部transport及父级发现共同满足原门槛，不要求固定比较排版；首次3/5评分及修订理由保留在audit历史。运行位置一行主要描述provider实现所在进程，作为表达局限另记。仍按原五项事实评分，不额外要求最近尾部或特定排版；不能用子报告或引用原文本身补分。低占用不等于质量合格。
- 采集区间无新增Redis OOM、公共源码漂移；其他Redis错误回复增加2，未归因为OOM。原始SHA256 `d44fe272e1bad96db1f0d15b907e507301c000866a6cc19dfdd1c3386a894ae6`；完整失败保留。第二轮已按冻结配置启动，继续完成预登记两臂各三次，不在组内微调或替补。

### 2026-10-29 v22委派第二轮（Phase）

- Thread `52ca1cae-8db4-4960-af68-a483b0c66ae5` / Run `658e5eb0-a40f-4241-885c-f3f41135ac55`，282.21s、294,283 Token；主4次input64,997/output3,936，子25次input217,244/output8,106。29/29账本完整、available/finalized、stop_code=null；主峰值20,154/262,144=7.7%、自动整理0。40份来源（子34）固定SHA/hash/namespace通过。
- 人工核心4/5：1/3/4/5通过，第2项仍未说明以较早历史为摘要对象，保留比例参数不能替代这一行为概述。第3项接受准确的pre-step事件作为生命周期简写，不要求特定措辞。附加生命周期行遗漏continuable限定、泛化到全部provider，另记局限。机械22条引用窗口覆盖，但“同上README#L12-L33”未解析；人工沿上一行compaction组README链接复核已读L1–44窗口，单独记录，不改机械结果。
- 采集区间无新增OOM/公共源码漂移，其他Redis错误+1。原始SHA256 `f10abadc9b669612f9eec8b82cdfd588d323e7a57acec3c580eec5173b4ad816`。第三轮Thread `67c43572-268d-46bc-ab8c-de0015b70408`已按原配置启动，继续完整采样，不替补。

### 2026-10-29 v22委派第三轮与固定臂判定（Phase）

- Run `fa2a8ad8-2ae9-4d63-a299-8fb2e0b9a219`，383.00s、424,524 Token；主8次input143,220/output4,174，子30次input267,925/output9,205。38/38账本完整、available/finalized、stop_code=null；主峰值23,773/262,144=9.1%、自动整理0。50份来源（子42）固定SHA/hash/namespace通过，23条解析引用均在已读窗口。采集区间无新增OOM/公共源码漂移，其他Redis错误+1。
- 最终人工核心4/5：1/3/4/5通过，第2项未说明摘要较早历史。额外“组文档未列相互依赖故无相互依赖”缺直接依据；手动压缩的部分行为只引组README链接行，证据过窄，单列局限。原始SHA256 `fda662608332eac0363638d592c6820e364ede894b9372cb6616ae858895105f`。
- v22三次委派核心4/5、4/5、4/5，合格0/3；主峰值7.7%–11.1%、整理0、全部账本完整，窗口治理证据与质量失败分开报告。主输入中位数143,220、总Token中位数424,524，只是本臂实数，不是同质量降幅。
- 按预登记继续同版本串行三次，仅切Pro delegation=false并核对两臂hash，公共22份源码、Kimi模型/窗口/输出/额度不变；只重启本隔离Runtime API/Worker。完成六次后保留当前实现，使用已配置DeepSeek建立独立模型组，不继续围绕本仓库五项事实堆叠提示词，也不混算跨模型结果。

### 2026-10-29 v22串行三次与整组判定（Phase）

| 次序 | Thread / Run | 秒 | 主输入 / 输出 / 总Token | 主峰值 | 核心 |
|---|---|---:|---:|---:|---|
| 1 | `93635f30-4d37-4b29-98d0-4ea17a53d7b1` / `d0867012-3dc0-44d4-84e2-e1678fa56d06` | 275.75 | 153,067 / 5,282 / 158,349 | 27,082（10.3%） | 3/5，缺精确流程/重试门控及subagent主循环之外边界 |
| 2 | `6ab690da-b376-4e61-86c5-9ce3cfe2965d` / `2cc2b580-c583-4c44-babf-d10e09c2b883` | 218.06 | 221,612 / 5,597 / 227,209 | 31,559（12.0%） | 4/5，缺精确流程/重试门控 |
| 3 | `57299b5a-acbb-47c4-96a5-aef84b756a54` / `eb0510df-dcb1-4cc5-a2ba-edb630264be3` | 362.88 | 374,157 / 5,857 / 380,014 | 32,861（12.5%） | 3/5，缺摘要较早历史及父级发现；流程按跨行语义通过 |

- 三次分别8/10/16次primary调用，无子调用；全部账本完整、available/finalized、无预算停止、root自动整理0。16/19/20份来源的内容SHA/hash/namespace核验通过，机械25/36/25条引用窗口覆盖；附加细节未全部核验，未将覆盖窗口等同全部断言准确。
- v22完整六次终态均保留，报告交付和完整账本均为两臂3/3，但核心质量均0/3；不能宣称同质量25%降幅。委派/串行主输入中位数143,220/221,612，总Token中位数424,524/227,209，耗时中位数383.00/275.75s；这些是各臂实数，不能掩盖委派总消耗更高及质量未过。
- 逐次评分、评分复核历史、原始SHA256、采集区间资源和引用局限见[六次可复核汇总](implementation/21-v22-controlled-comparison.json)。三次串行原始SHA分别为`b289f60d00397f3ec54c534ce9de23660adaa389e8970b70ef0089d33e9ecd76`、`db1dc4808b457355604aafaf23bd1125a53a043b2acce8122fb5425561711a20`、`0f497a8f9460d8c5c6b656df96fa2b984f034bf23be7e0307d188e983905a808`。各采集区间无新增OOM/公共源码漂移；其它Redis错误+1/+1/+2，未当作OOM。资源区间不覆盖所有Run之前时段。

### 2026-10-29 v23冻结实现的DeepSeek独立组预登记（Phase）

- 公共22份应用源码/提示词与v22完全相同；恢复Pro delegation=true，只重启本隔离Runtime API/Worker（pid70849/71886）。maomaoai目录记录虽存在，但正式项目选择器无可选项，UI guard在填入/发送原题前拦截，未产生模型调用或替换真实样本；按既有授权选用可用的xiaok `deepseek-v4.1-flash`，model ID `070cced3-350b-42ec-b678-994dd07b7078`，配置窗口131,072、输出8192。原预检manifest另存、最终hash在首轮真实提交前刷新；价格、真实供应商窗口和部署fingerprint仍未知。
- 原题/SHA/五项语义评分、Run1M兜底、主50/工具100、子16/工具48及上下文策略不变。先委派1/2/3，再串行1/2/3，两臂只切Pro delegation。既有真实模型持续授权适用；不改变当前运行中的组，不注入答案或目标路径，不混算不同模型/配置窗口。
- 最终manifest SHA256 `e51e88969001896f0c931cdee958aee63e41dd58358ac5b2af3ef240951eec92`，在首轮真实提交前落盘。采集器拒绝覆盖旧文件、逐次核对源码及私有测试环境hash、预算与Redis；沿用连续三次纪律，语义失败照记，不以替补或提示词微调取代整组观测。首轮Thread `e6b6e5a8-b033-4201-829e-eb1a6b56af04`由正式Web提交；Final仍未开始。

### 2026-10-29 v23委派首轮与采集恢复（Phase）

- Run `268384cd-1bb3-49d5-89f6-40935dc798b8`正常终态，37/37调用完整记账、finalized/available、无预算停止。累计676,060 Token，其中主input335,804、子input306,460；主单次峰值47,551/131,072=36.3%，root自动整理0。累计消费与当前/峰值上下文分别衡量，不能用累计量推算窗口占用。
- 三个真实code_explorer，75份来源（子49），内容固定SHA/hash/namespace校验通过；49条解析引用均在实际读取窗口。人工核心4/5：1/2/3/5通过，第4项未在最终报告陈述“subagent是agent loop之外的可选能力”；即使引用来源含该事实也不补分。成本及供应商部署fingerprint仍未知，不宣称质量达标。
- 首轮raw保存后，采集器在自动启动第二轮时收到非JSON的UI错误而退出。只读核验确认当前仍是空白新会话、草稿为空，正式按创建时间倒序查询的最新Thread仍为首轮，没有新增第二轮Thread；因此恢复页面后提交第二轮一次。原采集失败日志保留，不重发已有Run、不算作模型失败样本，不改应用源码/原题/配置。
- 第二轮Thread `f77fd90e-15c4-4e12-a69e-acb48ce1649e`使用同一xiaok DeepSeek配置继续冻结采样；采集仍未完成，Final未开始。

### 2026-10-29 v23委派第二轮：流中断与用量未知（Phase）

- Run `503ccb68-a0f6-4129-89e4-d47202fa27a0`在63.63s后error终态，没有完成报告（核心0/5）。7次观测调用仅4次有用量，3次failed/missing，完整总Token保持null；已知input23,402/output2,117/total25,519，不当作完整账单。
- 正式diagnostics HTTP200记录两个RemoteProtocolError、一个OpenAIConnectionError及后续TokenBudgetUnverifiableError；SSE与Worker记录`runtime.model.stream_interrupted`。预算保护随后以`token_budget_unverifiable`拒绝新工作。不能把该保护码误判为额度耗尽，原始网络/供应商具体根因尚未确定。
- 原始采集finalized=false、collection_degraded=true；不覆盖raw，后续用量补查需另存。三子均有固定SHA读取；6份来源hash/namespace通过，但无最终引用/报告，不能计作研究成功。采集区间无新增OOM或公共源码漂移。
- 原始SHA256 `62f62c945ded8b18d9fbcbdf5519b73bd4062a2f79e8b28a580701c7bcf2f4e8`。第三轮Thread `cb4991e2-586c-46e1-9e92-77289ad8e629` / Run `df549392-3334-461a-8819-bc5e0d2ee8b8`按同配置继续，不替补第二轮。

### 2026-10-29 v23委派第三轮与异常保护回归（Phase）

- Run `df549392-3334-461a-8819-bc5e0d2ee8b8`在344.92s后success终态，32/32完整账本、finalized/available、无预算停止；累计509,931 Token，主input149,063、子input332,761，主峰值34,269/131,072=26.1%，root自动整理0。三个真实code_explorer，66份来源（子51）固定SHA/hash/namespace通过，46条解析引用均在已读窗口。
- 人工核心4/5：1/2/3/5通过，第4项把“可选且loop外”写在compaction上，未陈述subagent的对应边界。第5项按跨行语义接受fresh/fork播种/进程内外形态及返回child id/localAgent的父级发现，不要求固定catalog词语；仅局部one-shot发现的表达限制另记。附加包数量把六个provider称五个，及“未发现HTTP提供方”的穷尽性不足，单列局限。原始SHA256 `2c110186cc4c96bf57e819214ce6b6802d91580a83482d61973a0713432d5111`。
- 连续三次委派质量4/5、0/5、4/5，报告交付2/3、完整账本2/3、核心合格0/3；不能宣称稳定质量或同质量25%降幅。第二轮的null总量保留，不剔除失败后计算完整总量中位数。
- 新异常对应最小回归：`uv run pytest tests/middlewares/test_model_resilience.py tests/middlewares/test_token_budget.py tests/observability/test_usage.py tests/runtime/test_token_budget.py -k "missing or partial or interrupted or unverifiable" -q` → 5 passed、103 deselected、5 warnings（15.78s）；39个修改Python文件Ruff通过，两目录diff --check通过。这些是Phase证据，不能替代真实供应商稳定性。
- 委派采样已全部结束后，只切Pro delegation=false，逐项验证串行臂hash、公共22份源码及私有测试环境hash；仅重启所属隔离Runtime API/Worker，继续同组串行三次，结束后恢复Pro=true。未合并、提交或部署。

### 2026-10-29 v23串行首轮：低占用但预算停止（Phase）

- Thread `53f0cf01-f5eb-42c5-82ff-7b7bc1055192` / Run `6e00135a-739f-48f1-9816-d824270f0ab5`在454.29s后安全终态，最终仅交回55字符预算停止通知，无研究报告、无最终引用，人工核心0/5。`status=success`不代表调研成功。
- 31次primary调用，input942,096/output16,553/total958,649，完整账本、finalized、coverage complete；`token_budget_exhausted`时remaining41,351，表示下一请求的保守预留放不下，不表示恰好用满1,000,000。缓存读取731,264；价格未知。
- 主输入峰值50,735/131,072=38.7%，root running/completed观测完整、自动整理0；75份固定SHA来源hash与namespace核对通过。低占用与零整理不能替代任务交付，也不能证明无重复阅读。无最终引用时引用窗口合格项不适用，不能把空集合当作通过。
- raw及三类audit保留：隔离Worktree的`.local-stack/serial-relaxed-v23-1.json*`；不覆盖失败、不补样本。采集器已通过正式Web提交第二轮Thread `0b6bc623-2939-4215-8112-63596d3d43eb` / Run `418a92b9-08f5-4c24-8484-9612942eeab4`；冻结源码、原题、模型与配置不变。

### 2026-10-29 v23串行第二轮与后续方案评审（Phase）

- Run `418a92b9-08f5-4c24-8484-9612942eeab4`在508.76s后安全终态，33次primary完整记账：input961,399/output11,404/total972,803，缓存读取790,528。stop_code=`token_budget_exhausted`、remaining27,197，最终仍仅55字符未完成通知，核心0/5。
- 主峰值49,717/131,072=37.9%，root running/completed与自动整理0次观测完整；59份固定SHA来源hash/namespace通过，无子任务、无最终引用。raw SHA256 `75826916fc5abf8ceaf1bfb986d2c40d7df825e8b32c1dc2f7d23757749c2ffa`，三类audit及人工评分已保存。
- 采集器已正式提交第三轮Thread `1b85c791-5e8d-4046-adf4-20a5049d224f` / Run `634cf56d-6ae2-463d-b332-6b4365231e57`，不修改冻结实现。此前44个app文件重新核对：主目录均与HEAD一致、无覆盖冲突；除预登记Pro布尔值外，Worktree相对v22无源码漂移。
- 真实交付缺口与下一阶段候选范围已写入`implementation/23-evidence-handoff-review.md`：第三轮子报告含正确边界，父报告整合丢失；串行读取窗口存在重叠，但不能仅据此断言遗忘。新增结构化交接与Token预警后交付约束已向用户提出方案评审，尚未获得答复，未实施。当前五项门槛不变，Final未开始。

### 2026-10-29 v23六次完整采样结论与模式恢复（Phase）

- 第三次串行Run `634cf56d-6ae2-463d-b332-6b4365231e57`在431.38s后安全终态，31次primary完整账本：input952,409/output12,864/total965,273，缓存读取769,280。主峰值52,393/131,072=40.0%，root running/completed齐全、自动整理0；stop_code=`token_budget_exhausted`、remaining34,727。最终55字符未完成通知，核心0/5，61份来源固定SHA/hash/namespace通过，无最终引用。raw SHA256 `39554e64942c315766395a25d2db9da5d891c5774a731258a042145cc2a12d2a`。
- 六次采集全部终态，采集器exit0；每份raw均完成sample/source/citation-window三类离线审计及人工评分。全部观测调用的模型身份均为登记xiaok DeepSeek ID，Usage分页均取完，无公共源码漂移、无新增Redis OOM；每次基础设施前后快照保留。来源完整性不等于语义完整性，无最终引用的失败样本不以空集合记合格。

| 实验臂 | 三次核心评分 | 报告交付 | 完整账本 | 核心合格 | 总Token中位数 | 耗时中位数 |
|---|---|---|---|---|---|---|
| 委派 | 4/5、0/5、4/5 | 2/3 | 2/3 | 0/3 | 未知，第二次缺用量，不剔除失败重算 | 344.92s |
| 串行 | 0/5、0/5、0/5 | 0/3 | 3/3 | 0/3 | 965,273 | 454.29s |

- 串行主输入中位数952,409；委派完整组主输入保持未知，不以某一次primary已知值补齐全Run。两次交付委派的主峰值26.1%和36.3%，三次串行37.9%–40.0%；这些是实际报告输入对配置窗口的比值，不是供应商实际窗口元数据，也不是累计Token比例。两臂质量均未过，25%同质量降幅不计算。不能仅凭这组预算停止推断更高总预算绝无帮助。
- 六次可复核汇总：`implementation/22-v23-controlled-comparison.json`，含全部Run/Thread、原始hash、模型身份、用量分页、缺失状态、来源与引用审计、人工逐项理由及资源快照。v22和更早组独立保留，不混算。价格、精确部署fingerprint、原始流中断供应商/网络根因仍未知。
- 采集结束后将Pro delegation恢复True，并核对与manifest中委派臂hash完全相同；22份公共源码、私有测试配置hash均未漂移。模式/装配最小复验命令：`uv run pytest tests/services/dearflow_agent/test_modes.py tests/services/dearflow_agent/test_agent.py -k "mode or delegation_mode or standard_rejects or primary_and_children_share" -q` → 8 passed、18 deselected、5 warnings（21.31s），日志`.local-stack/phase-v23-restored-mode-tests.log`。只重启所属隔离Runtime API与Worker，无新模型Run。
- 当前判定：blocked（待后续方案人工评审），不是done。T0.R2核对已完成，T3.2验收失败，T3.3仍未完成；新增实现范围或分期边界已给出可审查选项，尚未获得答复。不自行降低五项门槛、不继续围绕单题换模型或堆提示词，未进入Final、未整合源码或提交部署。

### 2026-10-29 历史终态回放与所属环境收尾（Phase）

- 正式Web分别打开串行预算停止、委派流中断及委派交付三种历史Thread；等待实际终态文本出现后保存页面及文本锚点截图。正式`runs?limit=10`查询确认每个Thread仍只有原登记的一个终态Run，无重发。三项DOM/API断言通过；这只是历史回放证据，不替代当前未开始的Final全链路与视觉验收。
- 证据在所属Worktree：`.local-stack/v23-ui-evidence.json`、`.local-stack/v23-{serial-budget-stop,delegation-stream-error,delegation-report}{,-anchor}.png`。初版页面截图过早、没有覆盖终态文本；已在等待真实文本及元素截图稳定后重做，并人工核对三个文本锚点。历史页的下一请求模型/模式选择器不能作为既有Run身份依据，模型身份以已保存Usage为准。
- 模式恢复后再核对44个app文件：隔离源码全部匹配v22已登记hash，主目录对应文件仍与HEAD一致，无覆盖冲突；尚未复制或合并。两个目录`git diff --check`均通过。
- 仅关闭`subagent-baseline-v2`浏览器，并通过所属`scripts/local-stack.sh stop`停止`wt_bf33bcf838fd`；两个进程命令均exit0，停止日志`.local-stack/v23-owned-stack-stop.log`保留（含Redis强制结束标记，不将其隐藏）。未执行destroy、删除数据目录、提交、推送或部署；raw、audit、来源文件与数据库不主动删除。
- 新增报告交接契约按架构治理范围提交人工评审；`plan-project`要求治理改动在评审后实施。当前尚无用户对新增范围的答复，已有模型费用授权继续有效，不另设逐次费用审批。
