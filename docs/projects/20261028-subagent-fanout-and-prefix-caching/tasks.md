# 任务拆分与执行跟踪

> 范围：Runtime委派及前置预算/工具治理。当前有效目标：按2026-10-30用户确认回到官方`task` + 只读`general-purpose`子Agent，撤除本次自研结构化报告/合成/原文校验和专用探索器；旧真实运行数据仅作历史证据，不用于宣称当前实现通过。用户于2026-10-30验收通过并授权提交/推送、合并和清理；提交与合并、所属资源清理完成，收尾记录随main推送，见本节及67号记录。

## 当前有效任务：简化委派交接（2026-10-30）

- [x] **S1** 撤除`ResearchReport`、`ResearchSynthesis`、原文交接/逐字引用校验和`code_explorer`实现及其专属测试。
- [x] **S2** 将预算、模型容灾、PII及工具输出组合测试恢复为普通文本子任务；保留共享预算、只读权限、取消、失败隔离、并发和工具限宽验证。
- [x] **S3** 补齐通用子任务的`ls/read_file/glob/grep/github_query`工具、RuntimeConfig 和 PlanMode 白名单；回归先复现 4 项权限失败，再 5 项通过。
- [x] **S4** 主提示词改为缺口/冲突/关键条件的定向复核；最短回归53通过/2跳过，独立真实烟测与完整交付核验已执行。通用收尾提示不包含原题答案或新协议；语义缺口保留。
- [x] **S5** 修复只读子任务官方工具次数耗尽异常穿透：红测3失败/17通过→绿测20通过，额度及兄弟保留组合5通过；主级与安全异常继续传播。
- [x] **S6** 更新 Runtime 开发标准、项目状态、FEATURES、CHANGELOG和CONTEXT，明确旧方案只是历史证据，工程完成不等于语义质量全对。
- [x] **S7** 相关回归282通过/12跳过；扩大27文件回归560通过/13跳过/1项默认Docker环境失败，该项显式local后端复验通过；Ruff/diff通过。跳过不计通过，不拼成一次全绿。
- [x] **S8** 精确同步所属隔离栈、重启 Runtime API/Worker；四次正式真实烟测与全部失败已留存，最后一次success、28/28 Usage完整、主峰31.1%、root自动整理观测值0。服务曾保持启动供验收，用户确认通过后现已停止。

当前实现事实：`agent.py` 只注册一个`general-purpose`子Agent；委派通过已安装 DeepAgents 的`task`工具执行。Open SWE `agent/chat.py:_chat_general_purpose_subagent()`采用相同角色、独立只读工具白名单；本项目保留既有 Runtime 工具/中间件边界，不逐字复制外部组合根。

### Task Completion Card: 简化委派交接
- **改动内容：** 撤除自研结构化报告交接链，恢复普通文本回传与通用只读工具，更新当前规范。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/`、相关 Runtime 测试和项目文档。
- **预期结果：** 生产委派只依赖官方 task 与只读 general-purpose 子 Agent；安全、预算、用量和工具结果边界仍由现有中间件保障。
- **验证项：** 当前范围S1–S8的Phase记录及独立Final见[verification.md](verification.md)；扩大回归与正式链路已完成，最后一次原五项明确语义覆盖3/5，未宣称稳定性或统计收益。详见[66号](implementation/66-open-swe-delegation-simplification.md)。
- **状态：** `[x]` `done`，2026-10-30当前简化实现与工程验证完成，用户人工验收通过，服务已停止，分支推送/快进合并/所属资源清理完成。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行，失败/跳过及模型质量局限如实保留
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已同步只读子任务额度异常隔离等用户可感知修复

用户已于2026-10-30验收当前简化版本。原五项语义稳定性、跨任务泛化、25%同质量输入降幅及成本收益未证明，不因开发完成改写为通过；本轮不追加模型样本凑通过。下方已取代方向的未勾选任务保留历史状态，不是当前开发待办。

## 验收后收尾（2026-10-30）

- [x] C1 用户确认当前简化需求验收通过，授权停止服务、提交推送、合并及清理本次Worktree与测试数据库。
- [x] C2 所属Runtime API/Worker、Platform API/Web、Redis全部停止；主工作区改动已精确备份，验证材料归档在Worktree之外。
- [x] C3 将两处工作区已核对一致的功能、主目录补全的历史文档及验收记录提交到独立分支并推送远端。
- [x] C4 主工作区保留改动快照后合并，校验原有代码未被覆盖，代码提交内容与验收版本一致。
- [x] C5 删除本项目归属的两个隔离数据库/角色、Redis与Workspace，移除Worktree及登记，保留验证证据归档和其他项目数据库。
- [x] C6 最终收尾状态随main提交推送，以提交后远端SHA回查确认；机器核对记录保存在Worktree外证据目录。

> **历史方案说明：** 下方 Phase 1/5 的 `code_explorer`、`ResearchReport`、`ResearchSynthesis` 与原文交接任务按当时授权执行并保留其验证记录；自本节决策后均已被当前简化方案取代，不再作为当前实现要求。原历史结果不删除、不改写为本次新方案的证据。

## 历史 Phase 5：DSH摘要前的上下文效率与可靠交付（方向已取代）

本阶段沿用标准模板，方案依据见[plan.md的DSH源码对照](plan.md#2026-10-29借鉴dsh在摘要前完成研究的机制)。应用代码仅在所属隔离Worktree实施；下列路径以`apps/runtime-service/`为根。既有完成卡不因新增任务而重写为未完成，Phase 5未实施项不勾选。

- [x] **T5.0 源码对照与实施/验收设计**（2026-10-29，文档范围）
  - 对照固定SHA的base/standard实际组合、read/grep边界、spill、技能及指令增量装载，区分机制存在与截图因果。
  - 关联v23低占用但失败证据，明确300是剪枝门槛、4800多行限宽缺口；补齐下列代码/调用方/测试、验证及回滚要求。
  - 完成条件仅为文档和源码依据可复核；不等于T5.1–T5.6或T3质量验收通过。

- [x] **T5.1 最终请求与读取重复的组成测量**
  - **位置/调用方：** `src/runtime_service/middlewares/conversation_offloading.py:ContextBudgetMiddleware.awrap_model_call()`、`ToolOutputPruningMiddleware`、`observability/usage.py`及`dearflow_agent/agent.py`主/子装配。先复用已有trace和离线采集器；确实缺失才加私有诊断计数，不新建公共SSE/Usage字段或前端页面。
  - **行为：** 每次按run/call/scope/namespace对应最终有效请求；统计system、Schema、技能/指令注入、其他消息和工具结果的互斥估算贡献、首轮与后续增量、剪枝前后。与供应商输入实数分别保存，未知来源归未分类，差额不强行分摊；确认归一化/容灾后的Schema，不能只测最早的请求草稿。
  - **工具链计量：** 原始捕获长度、工具适配后长度、模型可见长度分别记录；spill、窗口截断、压力剪枝、LLM摘要分开计数。源读取按SHA/路径/namespace/实际行区间归并，区分定位、续读、回读和引用复核；不把所有重叠都判成浪费。
  - **验证：** `tests/middlewares/test_conversation_offloading.py`、`test_tool_output_pruning.py`、`tests/observability/test_usage.py`及`test_agent.py`的代表性主/子/容灾请求；覆盖中文、Schema变化、多模态未知估算、计量不改请求、PII/私有状态不入公共日志。旧轨迹缺数据保留unknown。
  - **交付：** 无额外LLM调用的离线v23组成审计与可重跑计量样例；已有字段够用时输出“无需改装配”及证据。

- [x] **T5.2 工具输出可恢复、有内容且严格有界**（依赖T5.1）
  - **位置/调用方：** `src/runtime_service/middlewares/filesystem.py:ResultFilesystemMiddleware`及`truncate_tool_output_text()`、`tool_output_pruning.py:_prune_tool_content()`、`conversation_offloading.py:resolve_tool_output_limit()`、`dearflow_agent/agent.py`父/子filesystem装配；现有workspace backend/knowledge的特殊结果契约及`.env.example`。
  - **行为：** 优先复用现有`/large_tool_results/`与受限来源文件保存原文，确认可读后才给预览/引用；已外置结果不再嵌套外置，read_file的页有实际内容与可用续读坐标。没有可恢复位置时不伪称全文已保存，也不返回无限原文绕过guard，应给有界、真实的失败/截断说明。
  - **剪枝：** 保持压力触发，保留最新完整工具批次及本轮有界子报告，旧大结果保留实质首尾、来源及回读引用；不把checkpoint存在等同模型可读取。只改变模型视图，已有checkpoint/来源不可破坏。
  - **参数决策：** 先修多行分支的硬上限和回读链；按有效W/O及T5.1结果校准现有三处参数，不添加第四套限额。DSH的8192/4096/1024是旧结果剪枝字符对照，12500是spill估算Token对照，不能无单位地混用。具体采用值及原因在效果组登记前写明，两臂一致；不凭截图预填结论。
  - **验证：** `tests/middlewares/test_tool_output_budget.py`、`test_tool_output_pruning.py`、`test_conversation_offloading.py`、`tests/fixtures/tool_output_budget.py`、`tests/e2e/test_tool_output_budget.py`及`test_subagents.py`；首/中/尾哨兵可回读、返回含提示后的总长度有界、CJK/长行/多块结果、保存失败、跨namespace和同call ID不串结果、PII及knowledge契约、剪枝后重测不误摘要。

- [ ] **T5.3 用已有证据收敛探索**（依赖T5.2，继续优化）
  - **位置/调用方：** `src/runtime_service/services/dearflow_agent/tools/github.py:build_github_tool()`、`prompts.py`、`subagents/code_explorer.py`、`middleware/delegation.py`与既有todo/task状态；仅在T5.1确认重复来源的适配点修正窗口/续读信息。模型可见task描述在现有委派中间件统一，原SDK执行和隔离沿用。
  - **行为：** 保持README/文档优先、搜索定位后按行补缺口；现有结论/来源/未知项用于下一轮范围判断，足以回答原问题即交付。保留冲突复核、引用核验和因截断而重读的能力，不加自动拦截所有重复读取的机制、不另建研究工作流引擎。
  - **预算调用方：** `middlewares/execution_budget.py`、`token_budget.py`与末轮撤工具规则继续复用；费用限额开启时验证预警交付机会和并发预留，关闭时不合成Token停机；已有调用次数/时间/循环约束不自动放宽。
  - **验证：** `test_research.py`、`test_execution_budget.py`、`test_token_budget.py`及现有GitHub工具测试；窗口显示行号与真实来源一致，未读中间片段不能被当全文，正确处理未解点、读取错误和最后交付轮。提示词/格式测试只证明装配，收敛收益须由T5.6证明。

- [x] **T5.4 子报告交接保留结论、限定和证据**（依赖T5.2；与T5.3共同进入效果组）
  - **位置/调用方：** `src/runtime_service/services/dearflow_agent/subagents/code_explorer.py`、`subagents/researcher.py`、`agent.py`；复用已安装SDK的`SubAgent.response_format`/`structured_response`现成回传，不新增调度器、依赖或LLM审稿层。
  - **最小报告：** 沿用每子最多5条发现，字段只含对应研究问题、结论、成立条件/边界、来源及未解点；namespace/任务身份复用现有元数据。父按原问题覆盖合并，保留行为限定与来源绑定；未经核实不得把缺失/冲突填成确定答案。
  - **先行兼容：** 先核对已安装SDK及官方文档/MCP；结构化ToolStrategy可能与末轮撤Schema/`tool_choice=none`冲突，ProviderStrategy须验证配置供应商支持。只允许已验证路径；不为JSON强行放开任意工具、不靠临时换模型或再加一个模型调用兜底。
  - **输出边界：** 禁止对结构化正文首尾截断后再当合法报告；在进入通用工具限宽前处理超长，显式失败/部分结果及受限原文引用。父不能把失败子任务记为完成，仍须能交付真实的未解点。
  - **验证：** `test_subagents.py`、`test_agent.py`、`test_delegation_budget.py`、`test_execution_budget.py`和工具输出回归；用与本题无关的限定/否定/冲突哨兵验证字段传递、序列化、父可见性和来源，不把真实题五项答案写入运行时。语义保留最终由原评分验收。

- [x] **T5.5 仅对已证实的重复装载精简**（依赖T5.1；随T5.2–T5.4复测）
  - **位置：** `src/runtime_service/services/dearflow_agent/agent.py`、`middleware/skills.py:ExecutionSkillsMiddleware`、`skill_catalog.py`、`prompts.py`和现有图表Schema按需装配；MCP仍按既有授权显式挂载。
  - **行为：** 若测到技能正文/目录重复追加或无关Schema，修正同一装配入口；若只有同一份历史随每轮重传，则不误判为重复注入。保持技能快照、恢复语义、权限和PII处理，动态日期不单凭存在就删。无证据则不改代码，记录无需优化。
  - **验证：** `test_agent.py`、`test_skill_restart.py`及现有技能/权限测试；比较正常首轮、连续调用、快照恢复、工具按需加载和明确目录变更。单列前缀相同程度和cache_read/input，缓存收益不计入窗口降幅。

- [ ] **T5.6 分层验证、冻结采样与原门槛重验**（依赖前述必要修复）
  - **离线→短链→完整任务：** 先按`verification.md`专项完成契约/回放，再用正式Web→API→Runtime做一次独立完整任务烟测，核验流、Usage、可回读证据和最终报告；烟测与旧Run均不混入正式组。
  - **冻结：** 同一SHA、原题、评分表、provider/model、窗口/输出/headroom、全部公共实现与调用/时间/循环设置；两臂仅Pro delegation不同。费用限额关闭但Usage完整；预登记顺序为委派1/2/3→串行1/2/3，逐次新Thread并等待终态；六次全部保留，不因质量失败换配置补样本。
  - **原门槛：** 五项语义与引用全对、委派3/3、权限/取消/并发及用量完整、固定短题root自动摘要0和原≤50%窗口目标均保留，不增设49%目标。无同质量串行结果不算25%降幅；T5.6通过后重新执行T3.1/Final，不用T4短探针代替。
  - **推广边界：** 固定题通过只证明该题稳定，工业级结论还需不含原评分答案的另一个公开仓库/任务回归；在运行前冻结独立问题及引用评分表，只作泛化检查，不替换原门槛，也不为追求通过继续改提示词。

**每项完成时：** 在`implementation/`留实际代码/配置差异与命令/结果，更新本任务勾选和Phase记录；未执行不写通过。回退只撤本项改动，保留其他工作、持久历史和全部失败证据；当前不提交、推送或部署。

### 已批准的交付修订（应用实施中）

- [ ] **T5.7 子概述与最终组合契约实施及验证**（新增治理范围，2026-10-29用户明确评审通过）
  - **具体方案：** [implementation/28-evidence-composition-review.md](implementation/28-evidence-composition-review.md)。已有最多5条报告调整为1条overview+最多4条补充，4800总上限不变；主级按当前Run发现引用作明确取舍，程序保留原字段并呈现最终表格，沿用SDK ToolStrategy/调用与权限边界。
  - **已完成的准备：** 固定第六次材料的7次有界供应商诊断全部保留，其中两组存在文本工具调用、不能证明格式收益；离线原型保留3份报告15条发现全部字段并拒绝5类非法决定。原型不接应用，不充当正式质量证据。
  - **当前实施：** overview+4、主级ToolStrategy、Run私有注册表、确定性表格与流式抑制、字段纠错、有界原文与短来源引句均已接线。历史失败全部保留。v50独立正式原题5/5、v51六次终态质量未过；组后只读循环隔离170 passed/1 skipped，v52独立正式原题5/5、27/27 Usage。v53六次终态已审：委派5/5、2/5、4/5，串行2/5、error无报告、2/5；质量门槛未过。当前定向回归103 passed/1 skipped，泛化和Final仍待验。见[62号](implementation/62-bounded-document-intro.md)、[63号](implementation/63-v51-controlled-validation.md)与[65号](implementation/65-v53-controlled-validation.md)。
  - **评审后实施/验收：** 概述/组合、预算/取消/状态隔离、最后单一流式答复、正式烟测→原两臂六次→nanobot→Final；每步保留失败。不扩大模型调用额度、不加审稿模型或Docker前置。
  - **边界：** 新主级交付契约不能由AI自行批准；现有T5.3/T5.6/T3.2/T3.3仍未完成。

### 已批准治理修订：实施与验证中

- [ ] **T5.8 已读原文的有界交接**（2026-10-29用户已批准）
  - 可审阅方案及代码位置、限额、验证、回退见[35号](implementation/35-source-context-handoff-review.md)。新增每子≤1600、全Run原文≤4800、封装≤6500字符；原模型报告4800及主50/子16不变。
  - 已完成授权内诊断：第十一次4/5及来源→报告遗漏落盘；固定材料两种描述各4次SDK诊断均失败，204965 Token，不入正式组、不替补。离线原文提取原型7项自检通过，三子905/899/899字符，仅证明提取/限宽，不证明语义或应用接入。
  - 应用接入及后续纠错已完成，历史51/408/420/478项与失败均留原记录；当前扩大672 passed/16 skipped、v50独立5/5，真实原文交接1785字符、去重/渲染/唯一最终流核验通过。v51六次完整保留但未通过，组后隔离修复已落地；稳定性和泛化完成前不勾选，见[62号](implementation/62-bounded-document-intro.md)与[63号](implementation/63-v51-controlled-validation.md)。
  - 用户已批准新增交接内容及原文跨上下文可见范围，继续实施/验证。既有28号批准持续有效；依赖原质量通过的T5.6/泛化/Final按顺序执行。最终按用户新要求保持所属服务启动，供人工验收。

### 当前修正与待验边界（2026-10-29）

- 当前：v50独立正式原题5/5，34/34 Usage完整，主累计输入67,880/峰20,879、root摘要0、来源及单一最终流通过；v51同版六次终态质量未过，组后精确循环隔离170 passed/1 skipped；v52独立正式原题5/5、27/27 Usage。v53六次均已终态，委派质量1/3达标、串行质量0/3达标且有一轮失败；无同质量结果，不计算25%降幅。历史失败全部保留，泛化/Final未过前不提前勾选。见62、63、65号。

- v47 委派三次 success，原五项核心语义均覆盖，固定来源与质量总门槛 2/3；第二次保留非固定提交的仓库元数据，整组不记通过。三次主峰均低于配置窗口8%，root摘要0、完整Usage。串行三次已success但核心2/5、3/5、1/5、完整质量0/3；两臂全样本已保留且无漂移，Pro已恢复。operation必填修复在组后接入，红测1 failed/2 passed、绿测3 passed。Web927 passed/1 skipped、API37 passed/266 subtests passed；扩大Runtime原9 failed/651 passed/16 skipped保留；关联夹具已修正，五文件115 passed/1 failed后完整source_quotes复验38 passed，本地执行1 passed；最终完整回归仍待执行。见59号。

- v46 正式原题独立烟测原五项 5/5、三个子 namespace，主 2 次调用/累计输入 29,719/峰值 17,570，root 自动摘要 0、22/22 用量完整；引用、真实原文交接和唯一最终流核对通过。v47 六次对照已经冻结执行，稳定性/泛化/Final 不提前勾选，见 [59号](implementation/59-delivery-convergence-controlled-validation.md)。同版原生 HTTP/PG/Redis/Worker 恢复、权限及回退 E2E 1 passed（350.13s）；API 37 passed/266 subtests passed。
- v45六次冻结终态均error，Usage每次缺1项，不计算完整总量或同质量降幅；源码无漂移、Pro已恢复，见56号。交付重试正式回归先红3项，修复后63 passed/7 warnings，Ruff通过，三份修正已同步主目录；新Run重置和旧反馈隔离已验证。xiaok Kimi独立正式原题Run `cafac200-594b-4bc6-be9c-7e60ee9d75fe`已终态5/5，预登记/实现见58号、终态见59号；不替代三次稳定性。
- T5.3/T5.7/T5.8相关确定性修正已落地：45号目录quote、真实schema字段路径、超额长度及只读单子流中断隔离；专项104 passed/1 skipped，扩大478 passed/54 skipped/1 deselected。8份修正已同步主目录并重启所属Runtime。此处记录实现完成，不提前勾选依赖真实质量的任务。
- 49号一次反馈全部无效引用字段已完成：旧实现红测3 failed；95项关联回归通过，覆盖子5/父15项在原3次模型调用内一次纠正、无额外读取、反馈不回显正文。两份改动及标准已同步并重启Runtime。50号v40 Kimi28次完整调用、主峰18075、root摘要0、三子及单一流通过，但原质量仍4/5；旧失败均保留。
- v42终态4/5，矛盾条件与引用支持缺口保留于53号。54号逐句提示词候选和两模型固定材料诊断均未改善，候选不接入；55号仅澄清探索角色执行约束不能当目标事实及摘录字段，88 passed/1 skipped，源码同步并重启后进行DeepSeek Pro独立正式检查。通过后再冻结新六次、nanobot及Final，原题/评分/额度不变。
- 合规：实施/测试/Phase及CONTEXT、FEATURES、CHANGELOG已同步，未提交、推送、合并或部署。

### Task Completion Cards: T5.1、T5.3、T5.5

| Task | 实施/核对 | 验证与边界 | 状态 |
|---|---|---|---|
| T5.1 | 私有callback组成、HTTP捕获/适配/展示计量、离线按call关联Usage；v23重复行审计 | 实际原题烟测43/43 profile与账本关联，分项均为估算；技能来源/供应商隐藏注入/多模态Token保留unknown。计量/工具101项与最新扩大600项通过 | `[x]` 2026-10-29 |
| T5.3 | 提示词移除每项强制重读；烟测发现源码页3000→12000字符适配瓶颈，并收敛委派范围/完整引用格式 | 源码页先红后GitHub组合31 passed；工具/报告/装配/剪枝/限宽108 passed；两次组装断言通过。实际收敛收益仍须新烟测及T5.6判断 | `[ ]` |
| T5.5 | 核对ExecutionSkillsMiddleware为override注入与图表按需门控，无重复追加证据，不另改装配 | 真实烟测primary每call恰1条system/17,365字符、40个Schema；子1条/2,088字符、6个Schema，未见随调用增长；技能快照重启4 passed。stable长度不等于逐字证明全部正文无冗余，来源仍unknown | `[x]` 2026-10-29 |

### Task Completion Cards: T5.2、T5.4

| Task | 改动/位置 | 验证与边界 | 状态 |
|---|---|---|---|
| T5.2 | filesystem严格总限宽、read_file避免嵌套外置、压力首尾剪枝；三个既有参数校准 | 工具/计量101项，矩阵180 cases超预算0；最新真实HTTP/PG/Redis/Worker恢复/回滚E2E 1 passed（192.11s）；质量收益由T5.6验收 | `[x]` 2026-10-29 |
| T5.4 | ToolStrategy原生报告、拒绝缺失structured_response、末轮仅报告Schema且不扩执行权限 | plain_text先红后绿；交接/权限/取消/并发/预算111 passed、1 skipped；真实短链Run 8351792f-03b1-46e3-ad8c-9ca7c9b31cfa父收到合法2789字符JSON，Usage7/7完整；不冒充原题五项语义通过 | `[x]` 2026-10-29 |

- 实施与失败证据见`implementation/25-phase5-evidence-preservation.md`。ProviderStrategy失败及ToolStrategy静默文本探针均保留；未用成功替补覆盖。
- T5.1、T5.2、T5.4、T5.5契约工作完成；T5.3/T5.7/T5.8实现及最短回归完成，仍依赖真实稳定性。v50原五项5/5，v51新六次进行中，见62/63号；另一仓库泛化和Final尚未完成。源码与最新修正已同步主目录，所属服务运行；未提交、推送、合并或部署。v30–v49历史失败不替补或混算。

## Phase 4：DSH预算对齐（2026-10-29用户授权）

- [x] **T4.1 上下文预算与累计费用限额分离**（128项预算与装配回归通过，见完成卡）
  - 普通调研不默认累计100K/1M停机；隔离环境关闭累计限额，Usage保持开启；保留显式费用限额能力，切换前排空，只验证新Run，不修改旧账本。
  - 以真实配置W/O按DSH公式计算默认触发和原文保留；小窗口显式headroom、非法配置拒绝；既有显式覆盖兼容。
  - 工具剪枝与整理共享压力水位，先剪枝重测，保留最终完整请求guard及手动/溢出路径。
  - 验证128K/1M、输出变化、小窗口与错误配置、覆写、主子装配及显式费用限额回归。
- [x] **T4.2 正式路径预算接线验证及后续优化计划**（正式Run/Usage已验证，见完成卡）
  - 用新Thread经Web→API→Runtime核对Usage和累计限额关闭，不重新解释v23旧Run。
  - 更新实现/Phase验证、CONTEXT、FEATURES、CHANGELOG；明确下一步先修证据保留再修交接，不将接线检查冒充质量对照通过。

### Task Completion Card: T4.1
- **改动内容：** DSH窗口触发/保留默认、可配置headroom、共用剪枝压力水位，普通调研关闭累计限额并独立采集Usage。
- **代码位置：** `middlewares/conversation_offloading.py`、`dearflow_agent/agent.py`、`.env.example`及所属隔离env。
- **预期结果：** 128K/8K输出对应触发57,344、保留19,660；小窗口必须配置有效预留；显式限额仍拒绝超额准入。
- **验证项：** 预算/主子装配128 passed；其他相关组合48 passed/2 skipped/1 deselected，隐私/工具矩阵56 passed、真实PG恢复/回退2 passed；Ruff通过。关闭限额组合在1,200,002 Token后仍正常返回并完整采集；不冒充真实百万消费。
- **状态：** `[x]` 2026-10-29 → `implementation/24-dsh-budget-alignment.md`。
- **合规检查：** [x] 实现完成；[x] 最短回归完成；[x] tasks已更新；[x] CONTEXT/FEATURES/CHANGELOG同步隔离验证状态。

### Task Completion Card: T4.2
- **改动内容：** 真实Web→API→Runtime预算接线，恢复Redis加载等待，记录后续信息保留/交接/对照顺序。
- **代码位置：** 正式平台页面与Run Usage；`scripts/local-stack.sh`、`scripts/tests/test_redis_startup_probe.py`。
- **预期结果：** 新Run无累计Token policy，Usage仍完整；旧数据及v23失败保留。
- **验证项：** Run `da6a1372-ff6a-4217-b02a-c891c9f298a5` success，Usage200/finalized/complete，2 observed/2 reported，`token_budget=null`；3项Redis探针及实际栈启动通过；验证后所属应用/Redis均stopped，证据保留。
- **状态：** `[x]` 2026-10-29 → `implementation/24-dsh-budget-alignment.md`。本次短探针不算T3.2质量对照，整项目仍进行中。
- **合规检查：** [x] 接线验证完成；[x] 证据与下一步边界已记录；[x] tasks已更新；[x] CONTEXT/FEATURES/CHANGELOG及工具变更记录已同步。

## Phase 0：基线与前置条件

- [x] **T0.R 人工确认基线门禁修订**
  - 2026-10-29 用户明确答复“同意修订，保留失败基线”，`plan.md` 第 6 节生效。
  - 完整保留三次串行预算停止；后续用户授权放宽总预算（见 T0.R2）；五项证据仍全对；不同质量结果不声称 25% 输入降幅。

- [x] **T0.B 修复真实基线暴露的预算准入与公开投影**
  - 调用前预留估算输入 + 最大输出；并发共享预留，结束/失败/取消释放，未知用量拒绝继续。
  - 保留 usage 实际用量语义；API/Web 允许有剩余额度的准入拒绝通知及历史停止原因。
  - 用同一隔离栈验证正式 Usage 不再返回 502，再执行新的串行样本。
  - 2026-10-28 Phase 验证：Runtime 73 passed；API 37 passed、266 subtests passed；Web 31 passed；Ruff passed。原 Subagent/上下文回归 93 passed、1 skipped。真实链路复验待进行。

- [x] **T0.G 修复 GitHub 目录与源码读取边界**
  - 递归全树 4,337,791 bytes 超过 HTTP 2MiB 限制，改为按目录读取与分页；验证 path，禁止全树下载后才截断。
  - 源码按真实行号返回有限窗口及 next_line，完整源码保留在哈希证据路径，禁止模型通过 evidence 路径读回巨量正文。
  - 固定 SHA 公开 GitHub 实测：根目录、packages/compaction、生命周期文档行范围均成功，证据 hash 与 namespace 一致。

- [x] **T0.S 减少无关图表 Schema 固定开销**
  - 真实串行 Run 每次基础输入约 27k；离线观测确认 26 个图表 Schema 占约 50k 字符。
  - 复用现有技能流程：只有成功读取对应 chart-visualization/references/{tool}.md 后才向模型展示该图表 Schema；保持原工具注册、权限与审批。
  - 覆盖首次隐藏、逐项加载、权限拒绝及重建后历史恢复。两组共同使用此修复，重新建立全部基线，不与旧样本混算。

- [x] **T0.1 核对上下文治理改动归属**
  - 检查 ToolOutputPruning、ConversationOffloading、工具输出限额相关文件是否在目标分支。
  - 运行现有 subagent、TokenBudget、tool output 和 conversation offloading 测试。
  - 记录实际测试命令、提交版本及未提交文件；未能定位或复测失败时暂停实施。
- [x] **T0.2 建立串行基线**
  - 2026-10-29：完整采集连续三次同配置串行，任务完成率 0/3，中位主输入 77,806、总 Token 79,534；Usage/SSE 齐全。用户批准后作为失败基线保留，不记为任务成功；见 verification.md 第 6 节。
  - 使用 verification.md 固定的 deepseek-harness 提交 SHA、原样任务提示词与 5 项答案表；GitHub 工具请求必须显式传该 SHA 作为 ref。
  - 通过 Platform Web 的正式 `dearflow_agent` Run 路径，选择 Pro 和固定模型配置执行 3 次；每次新建 Thread，保持上下文策略一致。此阶段的 Pro 没有 task 工具，作为串行组。
  - 在隔离 Runtime API/Worker 配置 RUNTIME_USAGE_ENABLED=1、RUNTIME_TOKEN_BUDGET_ENABLED=1、RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000（旧组；新组见 T0.R2）；串行和委派组使用同一额度。
  - 保存每次 Run ID、Thread ID、模型 provider/model、仓库 SHA、prompt hash、完整用量查询、主/子/辅助 Token、缓存 Token、成本、耗时、root custom 整理事件和答案评分。
- [x] **T0.3 固定验收样例**
  - 直接使用 verification.md 中预登记的 5 条答案与不可变 GitHub 行号链接，不在观察委派组结果后改评分口径。
  - 模型 ID、配置、prompt hash、三次串行结果与中位数均在委派前记录；五项事实与来源表未变，验收修订在委派结果出现前取得人工批准。

### Task Completion Card: T0.1
- **改动内容：** 确认上下文治理实现已进入 `main`，工作区干净；按方案重跑既有 subagent、预算、工具输出与会话整理测试。
- **代码位置：** `78aa1717`（上下文治理基线提交）。
- **预期结果：** 在已提交基线上复现相关现有行为，为后续委派改动建立可重复的本地门禁。
- **验证项：** `PYTHONPATH=. .venv/bin/pytest tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py tests/middlewares/test_token_budget.py tests/middlewares/test_tool_output_budget.py tests/middlewares/test_tool_output_pruning.py tests/middlewares/test_conversation_offloading.py -q` → ✅ 122 passed, 1 skipped, 19 warnings（33.04s；工作目录 `apps/runtime-service`）。
- **状态：** `[x]` 已完成 2026-10-28。
- **合规检查：**
  - [x] 基线改动已提交并核对分支
  - [x] 验证命令已执行并记录
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 项目状态已同步
  - [x] T0.2 外部模型测试已持续授权；Phase 1 仍以有效基线和预算门禁为前提

### Task Completion Card: T0.B
- **改动内容：** 调用前共享预留及准入失败的 Runtime/API/Web 投影修复。
- **代码位置：** `runtime/token_budget.py`、`observability/usage.py`、`runtime/modeling.py`；API Usage 与 Web budget 解析。
- **预期结果：** 实际剩余额度放不下下一次调用时拒绝派发，Usage 仍返回完整账本。
- **验证项：** 已记录的定向测试通过；正式 Web Run `ca2e6fd2-38ea-43e0-b93a-40701cc9a168` 与 `a0a83cac-804c-4caa-94df-aa056ff21dda` 的 Usage HTTP 200、finalized、coverage complete，缺失与未完成调用均为 0；预算拒绝准确投影。它们任务未完成，仍不算有效调研基线。
- **状态：** `[x]` 已完成 2026-10-28 → `implementation/01-budget-and-source-bounds.md`。
- **合规检查：**
  - [x] 代码与最短链路验证完成，tasks.md 已更新
  - [x] CONTEXT/FEATURES/CHANGELOG 已同步隔离验证状态

### Task Completion Card: T0.G
- **改动内容：** 有界目录分页、源码行分页和不可变证据返回。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` → `build_github_tool()`。
- **预期结果：** 大仓库目录发现不会先下载整个递归树；长文件后段无需读取整份 evidence。
- **验证项：** GitHub 工具定向测试通过；固定 SHA 只读实测根目录 30 entries/2345 chars、compaction 8 entries/1269 chars、生命周期文档 L80-L93/1511 chars；三份证据哈希校验通过。
- **状态：** `[x]` 已完成 2026-10-28 → `implementation/01-budget-and-source-bounds.md`。
- **合规检查：**
  - [x] 代码与验证完成，tasks.md 已更新
  - [x] CONTEXT/FEATURES/CHANGELOG 已同步隔离验证状态

### Task Completion Card: T0.S
- **改动内容：** 成功读取对应图表规格后才展示该图表工具 Schema，复用现有技能中间件及预注册工具。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/skills.py` → `ExecutionSkillsMiddleware.awrap_model_call()`；图表技能与系统提示词同步。
- **预期结果：** 普通研究请求不重复携带 26 项图表 Schema，权限与审批仍由原机制执行。
- **验证项：** 图级按需加载、历史恢复与策略拒绝 2 passed；真实首轮输入由 27,061 降至 12,402 Token。两次 Run 均未完成任务，此观测不作为有效基线，也不归功于委派。
- **状态：** `[x]` 已完成 2026-10-29 → `implementation/01-budget-and-source-bounds.md`。
- **合规检查：**
  - [x] 实现、测试与 tasks.md 更新完成
  - [x] CONTEXT/FEATURES/CHANGELOG 已同步隔离验证状态

### T0.R2：总预算与窗口指标分离

- [x] 用户于 2026-10-29 授权放宽 100,000；预登记 1,000,000 隔离测试兜底，产品默认不变，旧失败保留。
- [x] 以同额度重新采集串行三次、委派三次：v22同配置六次终态及完整账本已保留，未通过质量门槛；原题/SHA不变。v23沿用冻结应用实现作独立DeepSeek组，不与Kimi混算。
- [x] 核对全部事实、immutable引用、root自动整理与输入峰值/配置窗口：v23六次均已审计，缺用量保持未知；委派4/5、0/5、4/5，串行0/5、0/5、0/5，核心合格均0/3，不计算同质量降幅。供应商实际窗口与部署fingerprint未报告，不将配置分母当作供应商精确元数据。

## Phase 0 补充：真实放宽额度后暴露的重复错误

- [x] **T0.L GitHub错误可恢复性与既有循环保护覆盖**（95项定向通过；v2真实对照继续）
  - 保留新额度首样本a36a405c的失败，模型错把repo改为deepseek-ai后反复请求；人工停止，不作为有效成功样本。
  - 工具对不可访问公开位置给出安全、可执行的owner/repo/ref/path核对提示；不暴露HTTP正文或凭据，不猜测仓库是否私有。
  - 复用现有LoopDetectionMiddleware，将github_query纳入只读检测；错误三次预警、五次停止，不把不同页/行范围当重复。仅隔离测试显式开启已有开关，不改全局默认。
  - 增加回归测试并重建新版本的两组三次，之前样本全部保留。

### T0.C：整理判定使用实际折叠视图

- [x] 将DearFlow的整理计数、输入保护与最终工具折叠共用同一个策略实例；摘要与归档继续使用原文，不改变手动整理和供应商溢出恢复。
- [x] 将隐藏摘要调用明确标为auxiliary/summarization，避免被算进primary峰值和主输入。
- [x] 保留v2首轮工具上限失败与第二轮诊断中断；修复后登记v3公共源码，后续在T0.R2/T3.2重新采集同配置两组，不混算版本。

### Task Completion Card: T0.C
- **改动内容：** 共用实际折叠视图计数；摘要/归档保留原文，隐藏摘要正确归类辅助用量。
- **代码位置：** `middlewares/conversation_offloading.py`、`tool_output_pruning.py`、`dearflow_agent/agent.py`及上下文测试。
- **预期结果：** 不因原始Checkpoint历史大而误触发整理；手动与真实溢出恢复仍有效。
- **验证项：** 先红1 failed/2 passed；修复后上下文/Usage/装配/PII组合 → ✅105 passed、5 warnings（57.20s）；Ruff及diff检查通过。
- **状态：** `[x]` 已完成2026-10-29；真实效果仍在T3.2验收，见`implementation/04-pruned-context-accounting.md`。
- **合规检查：**
  - [x] 实现、回归与tasks/Phase/implementation记录完成
  - [x] CONTEXT/FEATURES维持隔离验证中，CHANGELOG已有上下文输入治理修复说明；未宣称实际对照通过

### T0.P：防止折叠尚未消费的并行结果和本轮委派摘要

- [x] 回归复现：同一 AIMessage 发出超过 keep=4 个读取时，最早结果在第一次送入模型前就被折叠；本轮 task 短报告在父级继续读取后也被折叠。先红2 failed。
- [x] 最小修复：保留最近完整工具调用批次及当前用户回合的受限 task 摘要，历史原文与旧回合仍使用既有折叠；整理计数沿用同一实例。pruning/offloading组合43 passed。
- [x] v3 Run 已自然终态并保留完整账本；未自动启动后续样本。v3为诊断组，修复后另登记v4；禁止混算或替换失败。

### T0.W：低压力时保留证据，超过水位再折叠

- [x] 复核v4子任务在低窗口占用下仍重复读取：固定最近四条会在形成最终结论前丢失前轮证据，不能只靠保护最新批次解决。
- [x] 折叠前按包含system/tool schemas的实际请求投影估算压力；未达安全输入预算40%时完整保留证据，达到后才使用既有折叠策略。主/子图、整理计数及最终请求共用实例；不新增摘要调用，不改持久历史。pruning/offloading/agent组合68 passed，额外factory接线1 passed。
- [x] v4停止后保留全部已知用量与118份来源，标为诊断中断；修复/验证通过后另登记v5，不混入最终两组三次。

### T0.D：为有界子任务保留实际交付轮次

- [x] 保留v5首轮失败：969,120 Token，主输入峰值16,801，三个子任务仅一个返回长报告，最终为预算提示；后续样本未启动。
- [x] 复用ExecutionBudgetMiddleware：Run或Thread最后一次模型调用关闭工具，只用现有证据交付；前面的预警保持软收尾，不改Token准入/权限/持久历史。
- [x] DearFlow子任务模型上限由24缩至8、提前2次预警；父级额度保持不变。委派范围不得扩出原问题，报告仍最多5条、短证据摘要。
- [x] 新回归先红6/通过4；修复后53项预算/装配组合通过，先前其余组合97 passed/1 skipped。v6已预登记并启动首轮；完整真实质量由T3.2继续验收，未与v5混算。

### Task Completion Card: T0.D
- **改动内容：** 最后模型调用关闭工具，为报告保留轮次；子任务模型上限8、提前2次预警，委派只拆原问题。
- **代码位置：** `middlewares/execution_budget.py` → `ExecutionBudgetMiddleware._delivery_request()`；`dearflow_agent/agent.py`与父/代码探索提示词。
- **预期结果：** 子任务在有限探索后实际返回已有证据，避免耗尽额度只剩停止提示；不保证模型补齐未读取事实。
- **验证项：** 先红6 failed/4 passed；修复后相关组合97 passed/1 skipped，旧循环白名单组合断言已同步，预算/装配复测53 passed（47.70s）；修改文件Ruff通过。完整关联回归与真实模型仍在执行。
- **状态：** `[x]` 2026-10-29 → `implementation/07-reserved-delivery-call.md`；真实验收在T3.2。
- **合规检查：**
  - [x] 实现、最小回归、tasks/Phase/implementation记录完成
  - [x] CONTEXT/FEATURES同步隔离验证中；CHANGELOG同步收敛改动，未宣称对照通过

### T0.Q：按行为闭环验证研究交付质量

- [x] v6首轮已交付报告但人工验收仅3/5：默认装配和完整重试条件遗漏，另有未证实依赖断言与后端数量矛盾。保存完整291,599 Token与来源/账本，后续样本不启动，不混作成功。
- [x] 通用研究约束补齐：组织问题说明契约/实现/默认装配，流程问题说明触发、执行顺序、状态变化与重试/停止条件；截断窗口不当全文，删除引用不能直接支持的推断。不提供目标文件路径或答案。
- [x] 最小装配/角色3项通过后登记v7，首轮已启动；原题、SHA、模型、8次子模型上限、预算/窗口策略及五项门槛不变，同版本两组三次由T3.2验收。

### Task Completion Card: T0.Q
- **改动内容：** 通用组织/流程问题要求行为证据闭环、截断边界与无证据推断剔除，不改变评分。
- **代码位置：** `dearflow_agent/prompts.py`、`subagents/code_explorer.py`。
- **预期结果：** 最终交付覆盖问题中的关键行为，而非以参数表和次要细节替代核心流程。
- **验证项：** 装配及角色3 passed（12.75s），Ruff通过；v6人工评分3/5保留，v7已按原题预登记执行。源文件不含目标路径或标准答案。
- **状态：** `[x]` 2026-10-29 → `implementation/08-behavior-evidence-review.md`；真实质量继续在T3.2验证。
- **合规检查：**
  - [x] 实现、最小回归、任务/Phase/implementation记录完成
  - [x] CONTEXT/FEATURES维持隔离验证中；CHANGELOG已有收敛条目，不宣称真实对照完成

### T0.F：收尾请求协议与完整报告

- [x] 保留v7首轮失败：492,336 Token、主峰值25.1%、整理0，但最终finish_reason=length，第三部分未完成；子响应出现DSML调用文本并导致第四次委派。
- [x] 最后模型轮次保留工具Schema并显式禁止调用，覆盖OpenAI-compatible与Anthropic原生参数，以及模型容灾切换；不解析/执行正文中的调用标记。
- [x] 研究报告先覆盖全部原问题再展开，控制短表格篇幅；不向模型提供标准答案、目标路径或额外任务。
- [x] 协议/装配组合70 passed、5 warnings（47.33s），Ruff通过；v8预登记22份公共源码，两组真实验收仍在T3.2。v7后两轮不启动，失败不覆盖。

### Task Completion Card: T0.F
- **改动内容：** 显式禁止最后轮工具调用并保留Schema；跨供应商容灾规范化参数；原问题委派与完整短报告。
- **代码位置：** `middlewares/execution_budget.py` → `disable_tool_calls()`；`model_resilience.py` → `_observed_request()`；父/子研究提示词。
- **预期结果：** 收尾轮发送供应商原生禁止调用参数，减少损坏报告和输出截断；模型行为仍需真实验证。
- **验证项：** 先红6 failed/4 passed，修复后同步/异步协议、四组容灾及装配组合70 passed，Ruff通过；v8已登记，真实三次对照未完成。
- **状态：** `[x]` 2026-10-29 → `implementation/09-delivery-protocol-and-output.md`；真实效果在T3.2。
- **合规检查：**
  - [x] 实现、最小回归、tasks/Phase/implementation记录完成
  - [x] CONTEXT/FEATURES维持隔离验证中，CHANGELOG已有研究收敛修复行，未宣称交付完成

### T0.H：目录README定位不再忽略path

- [x] 保留v8首轮完整交付但质量失败：338,340 Token、主峰值20.4%、整理0、三个子任务。源码轨迹确认readme子目录参数被工具忽略，错误返回根README。
- [x] 复用GitHub目录README接口，保留固定ref、原文hash和namespace，根README行为不变；先红测试，再真实固定SHA验证。
- [x] 修复后登记v9，同版本两组三次由T3.2继续验收；不追加标准答案、评分点或目标文档路径。

### Task Completion Card: T0.H
- **改动内容：** readme按目录path取实际README，空path保留根行为，固定ref/证据/权限不变。
- **代码位置：** `dearflow_agent/tools/github.py` → `build_github_tool()`；GitHub工具组合测试。
- **预期结果：** 子目录读取不会静默得到根README，减少错误证据位置与重读。
- **验证项：** 先红3 failed；修复后135 passed、2 skipped、40 warnings（101.29s），Ruff通过；固定SHA根与两个能力目录的真实HTTP、原文hash/namespace全部通过。
- **状态：** `[x]` 2026-10-29 → `implementation/10-directory-readme-routing.md`；真实模型质量仍在T3.2。
- **合规检查：**
  - [x] 实现、最小回归、tasks/Phase/implementation记录完成
  - [x] CONTEXT/FEATURES维持隔离验证中；CHANGELOG同步目录读取修复

### T0.O：能力概述先于配置和类型清单

- [x] 保留v9质量失败：490,202 Token、主峰值25.8%、整理0，来源目录正确；核心2/5，缺概述/默认装配及完整provider比较。
- [x] 父子统一通用研究顺序：每能力先概述用途/契约与装配边界，提供方按上下文来源/运行位置/父级生命周期控制比较；调参和类型细节后置，不新增目标路径或答案。
- [x] 最小角色/装配回归后登记v10，同模型、原题与其余配置重新建立两组三次。

### Task Completion Card: T0.O
- **改动内容：** 父子统一概述优先、默认装配与职责边界、提供方比较维度；删去替代概述的配置和类型清单要求。
- **代码位置：** `dearflow_agent/prompts.py`、`subagents/code_explorer.py`。
- **预期结果：** 原题有限轮次先覆盖核心事实，再补必要细节；不注入目标路径或答案。
- **验证项：** 角色/装配选择4 passed、20 deselected、5 warnings（16.24s），两文件Ruff通过；真实质量仍在T3.2验收。
- **状态：** `[x]` 2026-10-29；见implementation/11-overview-first-research.md。
- **合规检查：**
  - [x] 实现、定向验证与任务/Phase记录已更新
  - [x] CONTEXT/FEATURES保留进行中；CHANGELOG既有研究交付行覆盖，不宣称验收完成

### T0.J：收尾时撤除Schema并保留显式协议禁用

- [x] 保留v10首轮：465,260 Token、主峰值26.8%、整理0，但第三子最后一轮返回DSML正文，父报告finish_reason=length，质量3/5。
- [x] 最后一次调用撤除工具Schema，使用model_settings显式传协议原生none；容灾切换保留相同语义。用真实SDK HTTP载荷回归先红后绿验证。
- [x] 两组单次输出统一从4096调至8192，给reasoning与正文留空间；不改产品默认、原题或评分，v11重新登记，不与v10混算。

### Task Completion Card: T0.J
- **改动内容：** 收尾撤除工具Schema，ModelRequest.model_settings传显式none；既有容灾规范化同步覆盖。
- **代码位置：** `middlewares/execution_budget.py:disable_tool_calls`，对应ExecutionBudget与跨协议容灾测试。
- **预期结果：** 最后调用无可用工具声明、显式禁止调用、其他model_settings保留，原始请求不修改。
- **验证项：** 先红8 failed/4 passed（14.06s）；修复后协议/预算/装配70 passed、5 warnings（59.08s），Ruff通过。真实v11效果仍在T3.2。
- **状态：** `[x]` 2026-10-29；见implementation/12-schema-free-delivery.md。
- **合规检查：**
  - [x] 实现、红绿测试与任务/Phase记录已更新
  - [x] CONTEXT/FEATURES仍为进行中；CHANGELOG补充收尾与输出修复，不宣称真实质量验收

### T0.N：子任务调用额度与全局预算分离

- [x] 核对 v12 的第 8 次硬收尾及缺失证据；保留质量失败和来源元数据审计更正。
- [x] 子模型上限从 8 调整为 16，预警仍为 2，工具 48 / Run 总预算不变；同步角色说明和装配测试，先红后绿。
- [x] 登记 v13 独立组；真实结果继续由T3.2核验，不注入评分答案或路径。

### Task Completion Card: T0.N
- **改动内容：** 子模型调用8→16，避免全局仍有余量时过早硬收尾；保留两次预警与最后交付轮。
- **代码位置：** `dearflow_agent/agent.py`、`subagents/code_explorer.py`及装配测试。
- **预期结果：** 有界研究允许读取完整关键文档，仍受全局共享准入限制。
- **验证项：** 先红2 failed；组合34 passed/1 skipped/33 warnings（74.15s），Ruff通过；真实改善另由T3.2验证。
- **状态：** `[x]` 2026-10-29 → `implementation/13-child-call-budget.md`。
- **合规检查：**
  - [x] 代码、最小验证、tasks/Phase/implementation已更新
  - [x] CONTEXT/FEATURES保持v13真实验证中；CHANGELOG沿用既有预算收尾修复条目，不宣称研究质量已通过

### T0.V：证据交接保留限定并核对原文
- [x] 子报告将概述纳入有引用的结论，不在无证据前言中交付核心信息；压缩报告时保留条件、作用对象与先后关系。
- [x] 父级表格保留关键限定与准确行号；最终答复前批量核对各原问题的一处关键来源，缺证据才追加读取，不展开审计。
- [x] 装配/提示词回归通过后冻结v17；同模型/原题/SHA/预算/输出/窗口重建两组，v16失败不替补、不混算。

### Task Completion Card: T0.V
- **改动内容：** 子报告自包含证据与限定；父批量核对原文后整合。
- **代码位置：** `dearflow_agent/prompts.py`、`subagents/code_explorer.py`及`test_agent.py`。
- **预期结果：** 不用可选类型细节挤掉核心限定，不挪用行号；真实质量另验。
- **验证项：** 先红2 failed；组合34 passed/1 skipped/33 warnings（54.68s），Ruff通过。
- **状态：** `[x]` 2026-10-29；v17真实对照继续T3.2。
- **合规检查：**
  - [x] 实现、最小回归、任务与Phase记录完成
  - [x] CONTEXT/FEATURES保留独立隔离验证中；CHANGELOG沿用已有研究治理修复行，不宣称质量已过

### T0.X：比较问题使用一致维度表格
- [x] 对提供方比较直接要求按初始上下文/历史、运行位置、父级发现/生命周期控制列成表格，未知单元格明示；不得用flags清单替代。
- [x] 父整合保留比较维度与已证实差异，取消与多提供方比较冲突的六行软限制；不增加答案、仓库路径或模型层。
- [x] 最小装配回归后登记v18，同Kimi/预算/原题重建两臂，所有失败保留。

### Task Completion Card: T0.X
- **改动内容：** 一致维度比较表格，移除冲突的六行软限制。
- **代码位置：** `dearflow_agent/prompts.py`、`subagents/code_explorer.py`、`test_agent.py`。
- **预期结果：** 比较不退化为名称/flags清单，保留历史/位置/父级控制的已证实差异。
- **验证项：** 最小装配2 passed/22 deselected/5 warnings（11.03s），Ruff通过；真实质量仍T3.2。
- **状态：** `[x]` 2026-10-29。
- **合规检查：**
  - [x] 实现、最小测试、任务/Phase记录完成
  - [x] CONTEXT/FEATURES保留隔离验证中，CHANGELOG沿用既有修复行，不宣称质量通过

### T0.I：拒绝收尾越权工具并隔离子额度失败
- [x] 末次模型响应即使违背tool_choice返回tool_calls，也不得执行工具或再发模型请求；保持error/end既有行为。
- [x] 只有获准只读委派的ModelCallLimitExceededError转为已有task失败反馈；主额度、共享Token停止、鉴权、取消与未知异常保持传播。
- [x] 增加同步/异步对抗模型及四子并发预算失败回归，确认其他子与父可收尾；真实失败与用量未知如实保留。

### T0.A：固定提交文件内文字定位
- [x] GitHub file/readme支持有界、忽略大小写的字面query，返回首次匹配附近行、matched_line与原行号；不匹配明确标出，不扩大内容上限。
- [x] query仅定位已有固定ref内容，不作网络代码搜索；无query保持原分页语义，路径/公开仓库/原文hash/namespace校验保留。
- [x] 覆盖Unicode、未命中、后续匹配、参数拒绝与原分页回归；父子工具说明使用此能力，不注入目标路径或词语。

### Task Completion Card: T0.I
- **改动内容：** 末次原生工具响应强制拦截，仅隔离批准只读子任务的模型额度失败。
- **代码位置：** `middlewares/execution_budget.py` → `ExecutionBudgetMiddleware.after_model()`；`tools/errors.py` → `on_tool_error()`。
- **预期结果：** 不依赖供应商遵从tool_choice；子额度失败反馈父，主预算/安全/取消仍传播。
- **验证项：** 对抗/四子并发/真实装配/错误分类/重试/GitHub联合159 passed、1 skipped、62 warnings（53.15s），Ruff通过；v18失败及unknown账本保留。
- **状态：** `[x]` 已完成2026-10-29 → `implementation/16-readonly-child-budget-isolation.md`。
- **合规检查：** [x] 代码与验证完成；[x] tasks已更新；[x] CONTEXT/FEATURES/CHANGELOG已同步隔离验证状态。

### Task Completion Card: T0.A
- **改动内容：** GitHub file/readme新增有界忽略大小写字面定位，保留原始来源与行号。
- **代码位置：** `dearflow_agent/tools/github.py` → `build_github_tool()`；`subagents/code_explorer.py`。
- **预期结果：** 长文件无需顺次翻读；未命中明示，固定ref/公开仓库/证据hash/namespace与输出上限不变。
- **验证项：** Unicode/后续匹配/未命中/参数拒绝/短窗口/长前文与原分页纳入159 passed组合；Ruff通过。真实质量由T3.2核验。
- **状态：** `[x]` 已完成2026-10-29 → `implementation/17-github-file-literal-query.md`。
- **合规检查：** [x] 代码与验证完成；[x] tasks已更新；[x] CONTEXT/FEATURES/CHANGELOG已同步隔离验证状态。

### T0.SHA：内容读取显式版本边界
- [x] file/readme/tree缺少ref时在网络请求前返回可修正输入错误；不回退默认分支，info等元数据查询保持不变。
- [x] 工具说明和错误提示明确提交/标签/分支及用户指定SHA须原样使用；仍复用既有公开错误码，不注入具体目标。
- [x] 覆盖参数前置拒绝、旧分页/README/证据契约及所有直接调用者，保留v19默认分支内容漂移失败。

### Task Completion Card: T0.SHA
- **改动内容：** 内容读取必须显式ref，缺失时网络前拒绝并反馈可修正输入错误；技能示例同步。
- **代码位置：** `dearflow_agent/tools/github.py` → `build_github_tool()`；`tools/errors.py` → `tool_error_content()`。
- **预期结果：** 不把默认分支内容混作用户指定提交；普通元数据查询保持既有行为。
- **验证项：** 先红7 failed；GitHub/错误/子隔离/研究/装配组合136 passed、2 skipped、44 warnings（115.48s），Ruff通过。
- **状态：** `[x]` 已完成2026-10-29 → `implementation/18-explicit-github-ref.md`。
- **合规检查：** [x] 代码与验证完成；[x] tasks已更新；[x] CONTEXT/FEATURES/CHANGELOG已同步隔离验证状态。

### T0.Y：能力概述使用显式字段交接

- [x] 保留v21六次连续终态：委派核心2/3，串行首轮漏默认启用，后两轮缺用量；不补样本或计算同质量降幅。
- [x] 将已要求的职责分层、默认装配、主循环关系固定为父/子概述表的独立列；每格直接写有证据结论或未知，流程子题不强加无关概述。删去重复提示，不加入仓库路径、事实答案、新模型层或新协议。
- [x] 装配断言先红后绿（35 passed/1 skipped）；v22冻结同配置两臂各三次，全部原始数据保留，核心质量委派4/5、4/5、4/5，串行3/5、4/5、3/5，未通过质量门槛。格式装配已验证，不能当作真实质量通过；见`implementation/20-capability-overview-table.md`与`21-v22-controlled-comparison.json`。T3.2继续用同实现DeepSeek独立组核验。

## Phase 1：受限委派能力


- [x] **T1.1 为 Pro 开放 task**（模式/角色离线门禁已通过；v23采样结束已恢复预登记True，仅在隔离Worktree；真实质量门禁仍未过）
  - 修改 dearflow_agent/modes.py，使 Pro 与 Ultra 开放 delegation；Flash 与 Standard 保持关闭。
  - 在 test_agent.py 验证各模式暴露的 task 工具集合。
- [x] **T1.2 增加受限 code_explorer**（离线实现与 Ultra 图级验证完成；Pro 开放仍由 T1.1 单独把关）
  - 在 dearflow_agent/subagents/ 注册 code_explorer。
  - 只提供 ls、read_file、glob、grep，不提供用户文件写入；固定公开仓库对照还依赖 github_query，只有验证其来源证据写入被限制在 content-addressed sources 路径且带正确 namespace 后才可加入。
  - 明确禁止 execute、write_file、edit_file 和递归委派；共享 backend 不得描述成物理沙箱。
  - 测试子 Agent 的工具 Schema 中不包含禁止工具。
  - 若 github_query 的来源证据写入无法满足上述边界，暂停真实委派对照，先修复隔离或准备经过哈希校验的本地固定快照。
- [x] **T1.3 补充委派触发和汇报约束**（确定性图级验证完成，真实模型依从性在 T3.2 验收）
  - 只有两个以上可并行的研究方向才使用 task；单点问题不委派。
  - 子 Agent 最多返回 5 条带 URL 或 path:line 的结论，并注明置信度和未解决点。
  - 在测试中验证报告不超过当前有效工具输出上限，且超限时不会静默丢失必需证据。

### Task Completion Card: T1.1
- **改动内容：** Pro 与 Ultra 开放受限 task，Flash/Standard 不变；新增模式和角色边界测试。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/modes.py`、`tests/services/dearflow_agent/test_modes.py`、`test_agent.py`。
- **预期结果：** Pro 编译图有 task 与只读 code_explorer；输出、权限、取消、预算约束保持有效。
- **验证项：** Pro开启的模式/研究/角色/Subagent/共享预算组合 → ✅63 passed、2 skipped（152.19s）；Ultra权限定向 → ✅8 passed。暂关仅用于新额度串行采样，非最终交付状态。
- **状态：** `[x]` 已完成 2026-10-29；真实模型依从性仍由T3.2验收。
- **合规检查：**
  - [x] 实现、最短测试与tasks.md状态已更新
  - [x] CONTEXT/FEATURES已同步隔离验证状态，CHANGELOG已有本项目待验说明

## Phase 2：并发、上下文与预算契约

- [x] **T2.1 保留现有并发机制**
  - 复用 DelegationConcurrencyMiddleware 的每父图 3 路限制，不新增 asyncio.gather 调度器。
  - 扩展 test_subagents.py：提交 4 个子任务，证明前 3 个可并发启动、第 4 个在有空位前不启动；释放一个槽位后第 4 个继续，峰值活动数始终不超过 3。
- [x] **T2.2 验证隔离和取消**
  - 断言子任务输入不包含父会话私有内容，子工具原始消息不会进入父 messages，事件归属到不同 namespace。
  - 父任务取消时所有运行中子任务都收到取消；一个子任务失败时其他结果仍可被安全汇总。
- [x] **T2.3 验证 Run 级 Token 预算**（输入预留是估算，不承诺供应商账单绝对硬封顶）
  - 使用确定性模型：先让父模型调用消耗已知额度并返回 3 个 task 分发，再用屏障让 3 个子模型调用在接近预算边界时同时进入，返回已知 input/output Token。
  - 断言所有 namespace 共用同一 RunTokenBudget 与 RuntimeUsageCallback；并发在途用量已纳入准入或安全预留，Run 总用量不能超过配置上限，额度耗尽后不能再开始模型调用。
  - 若当前实现只能在响应后登记用量、导致在途调用可能超调，先补齐并发预算控制并新增竞态回归测试；未通过前不得开放 Pro 委派。
- [x] **T2.4 验证结果大小与上下文治理**
  - 验证 task ToolMessage 不超过当前输出上限，子工具长输出不会进入父会话。
  - 运行现有 ToolOutputPruning 与 ConversationOffloading 测试；不得破坏 Checkpoint 原始历史。

### Task Completion Cards: T1.2、T1.3、T2.1–T2.4

以下为各 Task 的离线完成卡，均不代表 T1.1/真实模型门禁已通过。

| Task | 改动内容与代码位置 | 预期结果与验证项 | 状态 |
|---|---|---|---|
| T1.2 | `subagents/code_explorer.py`、`agent.py` 注册只读角色 | 实际编译 Ultra 图的最终 Schema 恰为 ls/read_file/glob/grep/github_query；四份来源哈希、namespace 和用户文件 sentinel 均校验通过 | `[x]` 2026-10-29 |
| T1.3 | `prompts.py` 及角色提示词要求独立方向、最多三子/每子五结论；`test_subagents.py` 覆盖报告 | 合格短报告保留不可变引用，超长报告被明确截断；真实模型是否遵循最多五条仍在 T3.2 检查 | `[x]` 2026-10-29 |
| T2.1 | 复用 `DelegationConcurrencyMiddleware`；扩展完整图测试 | 四任务中仅三活动，释放实际先启动的一槽后第四启动，峰值为三；不假设 FIFO | `[x]` 2026-10-29 |
| T2.2 | `test_subagents.py` 隔离、父取消及单子溢出 | 父私有输入不进子、子原始正文不进父；三个活动子均收到取消；单子失败明确 error，其余结果仍成功 | `[x]` 2026-10-29 |
| T2.3 | `test_delegation_budget.py`，`runtime/token_budget.py` 与 `observability/usage.py` | 父已用 10、三子并发预留 90，实际合计 100、最终预留零，后续父模型不派发；三子账本 namespace 不同；相关 57 项通过 | `[x]` 2026-10-29 |
| T2.4 | `test_subagents.py` 超长报告与既有工具输出/剪枝/整理测试 | task 返回≤4,800 字符、明确截断且尾部来源保留；相关组合 97 passed/1 skipped；最新 Subagent+Usage 27 passed/1 skipped | `[x]` 2026-10-29 |

- **合规检查（逐 Task 均适用）：**
  - [x] 实现或既有机制验证完成；代码位置与最小验证结果列明
  - [x] tasks.md、Phase 验证和 implementation/01 更新完成
  - [x] CONTEXT.md / FEATURES.md已同步：早期离线阶段Pro关闭；v23采样结束后恢复预登记True，仅在隔离Worktree，主目录未整合
  - [x] CHANGELOG 仅列已发生的输入/预算修复，不提前宣称委派交付

## Phase 3：对照验收

- [x] **T3.1 自动化门禁**
  - 执行 verification.md 列出的 Dear Agent、subagent、TokenBudget、工具输出与上下文整理测试。
  - 对修改文件执行 Ruff 检查。
  - 2026-10-29 Pro=True最新扩大Runtime门禁665 passed、42 skipped、4 deselected（372.77s），其后目录README路由135 passed/2 skipped及真实来源探针通过；收尾协议70 passed；子额度与证据交接34 passed/1 skipped，比较格式装配2 passed。Final需对当前完整实现重新回归。API37 passed/266 subtests、Web预算21 passed、类型及修改文件lint通过。当前均为Phase证据，Final在真实质量完成后另执行。
- [ ] **T3.2 公开仓库真实模型对照**
  - 2026-10-29：采集及离线核对已完成，验收失败，故任务不勾选完成。v23同实现xiaok DeepSeek两臂各三次连续终态全部保留：委派核心4/5、0/5、4/5，串行0/5、0/5、0/5；委派交付2/3、账本完整2/3，串行交付0/3、账本完整3/3。串行总Token中位数965,273；委派整组总量未知，不剔除失败计算中位数。完整数据见`implementation/22-v23-controlled-comparison.json`；v22及更早组不混算。
  - 经用户明确授权后，在隔离本地栈执行 3 次串行基线和 3 次委派运行；两组按 verification.md 固定模型、提示词、上下文和 Run 额度，以中位数比较。记录时间戳，模型部署版本有变化时该对照无效。
  - 若使用关联 Worktree，按 docs/standards/worktree-development.md 执行 local-stack.sh init、deps、doctor、start、status；用 status 返回的实际地址，不假定端口。将预算/用量变量仅配置在该环境的 `.local-stack/runtime.env`。
  - 仅使用固定 SHA 的公开仓库内容；记录 Run ID 和全部指标，不发送平台私有源码。
- [ ] **T3.3 判定与收尾**
  - 当前：v50独立正式原题5/5；v51六次终态质量未过；组后只读循环隔离修复并通过170项回归；v52独立正式原题5/5、27/27 Usage；v53六次均已终态，委派质量1/3达标、串行0/3达标且有一次执行失败。v53定向回归103 passed/1 skipped，但质量门槛未通过、无同质量降幅结论。泛化/Final尚未开始；完整应用源码已同步主目录，所属隔离栈五服务运行。下列v23记录为当时Phase历史，已被当前顶部状态取代。
  - 2026-10-29用户授权DSH预算调整并同意故障分析，T4已完成预算及正式接线验证；随后用户要求分析DSH摘要前的效率并补齐文档，T5.0已完成，Phase 5已批准并实施中，T5.2/T5.4契约与短链接线通过，原题/冻结对照待验。现行五项质量门槛不变，T3.2仍未过，Final未开始；未整合源码、未提交或部署。
  - 当前授权内已完成v23六次采样与三类审计、人工评分、全样本模型与分页核对、源码/环境hash复核；采集器exit0后恢复Pro=True到预登记hash，最小模式/装配回归8 passed、18 deselected、5 warnings（21.31s）。停止所属隔离栈时保留全部数据与证据。
  - 按 verification.md 的全部功能和效果门槛判定 done。
  - 若没有真实模型凭据或用户未授权外部调用，保持 partial，不将回放或单元测试记成真实模型验收。

### Task Completion Card: T3.1
- **改动内容：** 执行模式、预算、上下文、来源、委派及收尾协议相关自动化门禁。
- **代码位置：** Runtime关联集合、API Usage/budget契约、Web预算解析及聊天组件。
- **预期结果：** 当前实现通过必要组合回归与静态检查，真实模型质量另验。
- **验证项：** Runtime扩大665 passed/42 skipped，目录修复后135 passed/2 skipped；API37 passed/266 subtests，Web21 passed、vue-tsc退出0、ESLint退出0/8既有警告，Ruff通过。跳过项不计通过。
- **状态：** `[x]` 2026-10-29；Final仍未开始。
- **合规检查：**
  - [x] 门禁、Phase与任务状态已更新
  - [x] CONTEXT/FEATURES维持真实对照中，CHANGELOG沿用已发生修复，不宣称完成

### Task Completion Card: T0.L
- **改动内容：** 公开来源失败可执行提示；已有循环保护纳入GitHub错误，隔离环境开启，重登记v2两组。
- **代码位置：** `middlewares/loop_detection.py`、`tools/errors.py`、`dearflow_agent/tools/github.py`及对应测试。
- **预期结果：** 不泄密地核对仓库定位参数；相同错误重复三次预警、五次拦截，分页继续。
- **验证项：** 红测5失败；修复后错误/循环/GitHub组合 → ✅95 passed；实际模型改善仍由T3.2核验。
- **状态：** `[x]` 2026-10-29。
- **合规检查：**
  - [x] 代码、回归测试、tasks/Phase/implementation记录已更新
  - [x] CONTEXT/FEATURES保留隔离验证中；CHANGELOG当前修复行覆盖该输入治理，未宣称真实委派完成
