# Agent 效果等价与组合可靠性重审

> 2026-10-09补充：本文2026-09-28的预算/模型/工具等基线由后续专项更新，不能当作当前缺失清单。F02/E05用当前装配再次复现，详细取舍、当前依赖、任务和验证见 [15](15-f02-loop-detection.md)，前端见 [16](16-f02-frontend-handoff.md)。原7场景整脚本含已过期E06断言，不作为当前整套验收命令。

## 目标

回答三个问题：同名能力能否达到同样效果；串联后是否仍可靠；底层容错、兼容和工具优化是否完成。**当前不能认定整体等价，更不能认定整体优于参考项目。** 11的能力目录说明覆盖范围，不是效果证明；本篇补充运行机制、实际反例和验收设计。

比较基线沿用11：平台 `4f49040a5e9b2f2307bc6418321d32cb300a84ec`；参考 `cc664451f03140b376611f329ae400c313530bdb` 加本地工作树修改。这里的“上游”均指该本地参考，不冒充公开发布版。代码存在、默认开启、部署开启、测试通过、业务效果达标是五件不同的事。

## 方案设计

### 1. 如何判断等价与更优

效果需要分别衡量：任务正确率、约束满足率、来源可核验率、失败后恢复率、不实完成率、权限边界、成本与延迟。同名API、Skill目录数、middleware数量和测试通过数都不能替代这些指标。

- **已有替代机制**：官方底座或当前平台实现了相同职责，但仍须验证实际装配和边界。
- **已复现差距**：实际组合根在指定输入下没有达到目标保障，不再仅列“待核实”。
- **源码差距**：未发现等效路径，尚须故障实验确认生产影响。
- **效果未证**：有实现，但缺同条件业务对照，不能判断谁更好。

局部更严格也有代价：只读子Agent减少副作用，但处理任务类型更少；记忆人工采纳减少污染，但增加交互。不能把某一轴更强写成整体更优。

### 2. 源码定位约定

以下缩写仅压缩路径，不代表新模块：

- `S` = 从仓库根起的 `../research/deer-flow/backend/packages/harness/deerflow/`。
- `R` = `apps/runtime-service/src/runtime_service/`。
- `D` = `R/services/dearflow_agent/`。
- `O` = `apps/runtime-service/.venv/lib/python3.13/site-packages/deepagents/`，本轮实际版本0.7.8；不修改site-packages。
- 上游组合入口：`S/agents/lead_agent/agent.py:build_middlewares`；当前：`D/agent.py:get_agent`；官方：`O/graph.py:create_deep_agent`。

### 3. 同名能力的实现与实际效果

| 能力/用户预期 | 参考实现方式 | 当前实现与已有替代 | 效果判断与不足 |
|---|---|---|---|
| 研究：找到材料并形成可信结论 | 搜索/抓取、多角色委派、来源和回执体系；搜索支持时间与域名过滤 | `D/tools/search.py` 固定Tavily接口，有query/响应大小/超时限制；正文按hash落入sources，附URL、run/ns/toolcall来源，预览截断后可回读 | 正文持久可追溯是实质价值；参考单个Tavily工具只返片段、fetch有4096字符截断，但其上层还可能外置。当前缺时间/域名筛选，错误分类粗；引用真实不代表结论正确，未做业务A/B |
| 规划：计划全部落实才报完成 | Todo在未完成而准备退出时最多追加2次提醒；遇length/provider兜底不无限续跑 | Pro/Ultra使用官方Todo工具；能记录和显示计划 | 已复现in_progress仍直接回答全部完成；“能写计划”不等价“约束完成条件” |
| 委派：并行完成子任务并可信汇总 | 子任务有stop_reason、回执引用校验、可选确定性acceptance_checks、委派账本 | 官方SubAgent/task、researcher只读工具集、并发3、task次数限制、父取消与namespace；post37历史回放 | 有隔离和观测，不等于验收。缺对应的任务验收协议；子任务结束不能直接算目标达成；多角色/编码不能声称等价 |
| 长上下文：压缩后继续执行 | DurableContext保留目标/委派/技能证据；摘要成功后才触发记忆flush；可选摘要模型回退 | 官方摘要、旧工具参数截断、历史与多媒体外置、上下文溢出重试；现有记忆/消息队列保留测试 | 通用上下文管理已借鉴到位；未证明长链路压缩后仍保有全部约束、来源和未完成任务。不能再重造通用摘要器，也不能仅凭它声称业务连续性完成 |
| 工具失败：识别原因并换策略 | 结构化错误→进展判断→重复循环限制；回执覆盖成功和短路拒绝 | ToolMessage错误、官方工具处理、调用次数/模型超时；研究错误会简化为provider_failed | 缺统一可行动错误与无进展处理；已复现读文件失败仍接受成功声称、6次相同调用全部执行 |
| 文件编辑：正确修改当前版本 | read-before-write以内容hash和同scope/path锁检测过期读取 | `D/workspace/backend.py` 加路径/写域约束，官方write/edit；产物发布有不可变digest | 权限与成果完整性有保障；没有同等的“基于刚读版本修改”门禁。上游inspect失败也会fail-open，不能当通用文件事务 |
| 文件/命令大输出：不丢重要证据 | 工具输出预算、摘要、artifact handle、后续检索/回读协作 | 官方Filesystem约20000 token外置；ls/glob/grep/read分页；公共执行层128KiB截断 | 返回有界不等于完整日志可回查。Dear Backend不是官方BaseSandbox，不能假设capture-at-source自动保存截断前原始shell输出；需专测 |
| 记忆：记得正确、用在正确用户上 | 自动抽取/flush与摘要流程衔接 | `D/memory.py`、`memory_access.py`、`middleware/memory.py`：本人×项目、候选采纳、来源/quote验证、CAS/epoch、共享禁用与降级 | 在采纳与作用域控制上更明确，仍欠真实Run/SSE/浏览器闭环；不能宣称召回质量优于参考 |
| Skills：正确发现、选择、执行 | 激活记录、工具策略、动态上下文、按需工具发现配合 | 官方Skills加载＋`ExecutionSkillsMiddleware`执行冻结快照；存储ZIP边界/原子CAS/单份当前内容 | 快照保证恢复可重现；显式选择、使用证据、延迟工具schema尚不同。目录存在不等于模型用对技能；本轮发现vercel-deploy目录名不匹配告警 |
| 模型兼容：换provider仍稳定 | provider补丁、System合并、finish_reason检测、结构化/原始tool_call一致处理、retry/circuit/admission | `R/runtime/modeling.py`支持OpenAI兼容/DeepSeek/Anthropic、reasoning字段保留；RuntimeConfig历史配对修复，官方PatchToolCalls | 已有真实兼容工作；未形成相同异常模型响应链路。finish_reason反例已复现，其他provider需矩阵验证 |
| 审批/恢复：只执行批准内容 | 参考有自身澄清、工具策略、子任务与运行状态约定 | 官方HITL/interrupt/resume＋签名Context、运行期权限重验；澄清混批guard先挡住副作用；Chat/SSE专项承接 | 不需复制参考的运行管理器。已有撤权/混批测试；仍欠Dear产品长链路和重启验收，不能把单元测试当效果等价 |
| 媒体：可靠得到成果且不重复计费 | 媒体Skills和供应商流程；具体任务协议因工具而异 | `ExternalTaskStorage`先存意图、claim、稳定幂等键和digest；取消/不确定ACK保存unknown | 当前有防重复意图，但unknown明确提示无后台恢复；查询入口不等于恢复worker。尚未达到重启后自动对账/交付，音视频另有业务缺口 |
| 执行隔离：工具不能越权伤及平台 | sandbox、工具授权、审计、策略中间件组合 | 平台委托/作用域/工作区边界；Docker network none/PID/内存/CPU限制，Local用于开发 | 不同架构下的有效替代；Local不等价生产沙箱，仍需生产等价拓扑与资源回收测试 |

### 4. 底层保障链：触发、顺序、状态和启用条件

本地参考源码默认loop/read-before-write/safety/receipts开启；tool_progress、summarization、judge默认关闭，部署配置可覆盖。本轮未读取敏感配置来断言实际部署启用。这些机制也不是绝对正确性的证明。

| 机制 | 参考的关键行为与源码（相对S） | 当前借鉴情况与缺口 |
|---|---|---|
| 输入和工具结果清理 | `agents/middlewares/{input_sanitization,tool_result_sanitization,pii_redaction}_middleware.py`，PII可选 | 平台授权/路径校验已有；不等同非可信内容/PII策略。需合法内容误伤与注入负例，不能靠正则声称完成 |
| 历史工具调用兼容 | `dangling_tool_call_middleware.py`修补未配对调用 | `R/middlewares/runtime_config.py:sanitize_tool_call_messages`移除孤立/重复结果、重排连续配对、补错误回执；官方PatchToolCalls也覆盖部分。职责已覆盖但需组合兼容测试 |
| provider失败恢复 | `llm_error_handling_middleware.py`分类重试/backoff、stream timeout预算、并发admission、熔断半开与迟到探针保护 | 当前SDK默认重试＋模型调用超时不等价这套策略；按真实故障先选必要部分，不先照搬熔断框架 |
| length终止保护 | `model_length_finish_reason_middleware.py`清除结构化/raw/内容块工具调用并保留停止信息 | 当前可解析调用继续到HITL，批准后执行，见E01；历史消息修复不处理此问题 |
| safety终止保护 | `safety_finish_reason_middleware.py`处理content_filter/refusal/SAFETY，清潜在调用和空assistant | 当前content_filter调用仍可执行，见E02；不代表绕过了HITL |
| 工具后终态空响应 | `terminal_response_middleware.py`给可见兜底；LLM层可先有限重试 | 当前可直接结束为空字符串，见E03；兜底需诚实说明结果，不能填“成功” |
| 调用结果分类 | `tool_error_handling_middleware.py`、`tool_result_meta.py`提供结构化事实 | 当前不同工具错误格式不一；403/429合并妨碍决定是否重试/换策略 |
| 无进展判断 | `tool_progress_middleware.py`区分无结果/可改参数、限流/瞬态、认证/配置/内部错误，逐步warn/block | 当前未见等效装配；参考该能力默认关闭，不能写为部署效果已证 |
| 重复调用 | `loop_detection_middleware.py`相同工具参数滑窗warn3/hard5；thread/run隔离；配对完整后再提示 | 当前只有总次数限制，6次完全相同调用仍执行（E05）；总预算不能替代无进展检测 |
| token与轮次预算 | `token_budget_middleware.py`与子执行器区分token/loop/turn capped | 当前Model/ToolCallLimit已有，但主run取max(mode,env)，低env不收紧（E06）；次数限额不等于token/金额限额 |
| 计划完成门禁 | `todo_middleware.py:after_model`有限提醒，特殊终止不续跑 | 当前Todo仅记录，E07显示状态与完成声称冲突 |
| 工具回执 | `tool_receipt_middleware.py`包住可能短路的guard，真实调用结果形成稳定账本 | 当前消息/trace/来源记录存在，但无同等的业务证据协议；日志可见≠主Agent已核验 |
| 引用验真 | `receipt_verification.py`核对[rN]，citation_resolved为advisory，零引用动作声称可标UNVERIFIED | 当前未见子结果同等规则。上游也不能保证拦住所有自然语言谎报，E04仅证明本地缺口，不证明上游一定阻断 |
| 子任务验收 | `subagents/`任务工具/执行器支持acceptance_checks、结构化stop_reason；无法核验为unknown | 当前researcher工具受限、可追踪，但缺完成状态和目标验收的区分 |
| 摘要后证据连续 | `durable_context_middleware.py`、`delegation_ledger.py`保留业务账本；回执编号绑定模型所见snapshot | 当前官方摘要有历史外置，不自动等价业务账本保留；需跨压缩核验 |
| 摘要失败无错误副作用 | `summarization_middleware.py`候选模型、非空验证、成功后memory flush | 官方已有压缩与overflow恢复；当前业务记忆是另一条流程，必须按当前架构测失败原子性而非照抄hook |
| 并行编辑保护 | `read_before_write_middleware.py`路径锁＋读hash；写后失效，inspect失败fail-open | 当前路径授权与审批不是并发内容一致性控制；先验证实际编辑场景再补最小条件写 |
| 结果外置与句柄解析 | `artifact_capture_middleware.py`、`artifact_resolution_middleware.py`及输出预算 | 当前官方外置＋业务artifact refs可复用；核实底层先截断造成的信息不可恢复 |
| 工具按需发现/授权 | `mcp_routing_middleware.py`在`deferred_tool_filter_middleware.py`之前；Skill策略只收紧工具面 | 当前MCP装配/授权已有，尚无同等发现链；只有测出schema成本再加延迟发现 |
| 中间件组合约束 | `extensions/ordering.py`约束回执在短路guard外、progress在错误分类外、句柄解析先于参数授权；after_model反序需特别处理Safety/Loop | 当前官方按名替换/插入自定义middleware，不是简单append；未来补guard必须验证真实执行顺序、HITL和子Agent覆盖，不能只测类本身 |
| 引擎兼容补丁 | provider/执行器有各自兼容处理 | `R/patches.py`处理GraphBubbleUp/ToolNode，失败可能只warning；升级后必须检查实际生效，不把“存在monkeypatch”当兼容证明 |

### 5. 能力串联后的三个真实旅程

**旅程A：研究两个主题→并行子Agent→搜索限流→上下文压缩→带来源报告。**

1. 委派阶段：我们有只读和并发上限；参考进一步记录任务目标与子终止原因。缺口是收到一段文字时能否区分“做完/预算耗尽/仅部分输出”。
2. 工具阶段：我们能保存来源正文；参考错误分类、可选progress、loop可配合决定换参数或停止。当前粗粒度错误＋总次数限制容易把预算花在同一失败上。
3. 压缩阶段：我们有官方外置和摘要；参考额外保留委派/技能/回执事实。需证明压缩后来源仍对应原结论，用户追加限制和未完成项没有丢失。
4. 汇总阶段：参考回执解析和可验acceptance_checks可以降低无证据完成；不是判断全部内容正确。当前缺对应核验，而且E04/E07已给出错误完成反例。

**旅程B：上传文件→读/编辑→审批→断流或进程重启→下载。**

1. 当前平台委托、线程作用域、工作区只写域、HITL是必须保留的边界，不迁参考Gateway。
2. provider返回length/content_filter时，应在工具/HITL前处理终止语义；当前E01/E02显示此环断开。人工批准本身不能把被截断调用变成可靠调用。
3. 两个操作基于同一旧内容并行编辑：审批内容正确不代表读版本仍新；当前无同等read-hash保护。参考也不是所有shell写入的事务防护。
4. 重启恢复同时校验审批digest、授权、Skill快照和checkpoint namespace；下载验证产物digest与内容。通用SSE已修不代表Dear旅程自动验收完成。

**旅程C：检索素材→生成图片→写PPT→远端ACK丢失→恢复。**

1. 先验证图片工具真实返回且PPT引用真实文件，不能以模型说“已生成”算成功。
2. 我们已有幂等意图和unknown持久化，能避免简单重试带来的重复计费风险；未知不等于供应商已取消。
3. 当前没有自动后台恢复；重启后不能只靠前端不停查询就承诺最终交付。需要先确定供应商查询/幂等能力，再设计最小对账流程；无此能力则诚实保持unknown与人工处理。
4. 文件存在仍不足以验PPT：须打开解析、图片数量/页内容断言、下载字节一致。音视频未迁移与此可靠性缺口分别列账。

### 6. 最小补齐方向和次序

沿用12的T编号，不增第二套施工状态表。**T07中的关键可靠性切片提前并入B1**，不能等新媒体或完整Skill验收后再做。下面是T03/T07的实现验收细化，不表示已批准实施。

| 顺序/归属 | 最小改动与代码位置 | 应达到的效果/验收 |
|---|---|---|
| 1 / T07 响应终止 | `D/middleware/`拟定单一响应保护模块，由`D/agent.py:get_agent`装配；复用当前历史消息清理，不另写Agent循环 | length/safety结构化与raw调用一致清理；不进入写工具；空终态可见且不伪称成功；主/子Agent及HITL顺序组合测 |
| 2 / T03 预算语义 | `D/agent.py:get_agent`、limits配置及模式解析 | 区分默认预算/硬上限；获批后真实低上限可收紧，跨graph重建不重置；因预算结束明确partial，避免无限补Todo |
| 3 / T07 失败与停滞 | `D/tools/search.py`等现有工具边界保留错误码/可重试信息；`D/middleware/`最小重复检测 | 认证错误不重试，429有界退避，空结果允许换查询；跨run不误伤；合法重复/轮询例外按工具事实判定，不仅比较字符串 |
| 4 / T07 完成证据 | `D/subagents/researcher.py`、工具返回与`D/workspace/artifact_refs.py`；先复用已有来源/产物记录 | 文件/hash/格式/测试事实确定性验收；子运行结束≠完成；无法核实标unverified；待办未完成有限续跑或明确partial，不先建judge LLM |
| 5 / T07 压缩连续性 | 官方摘要保持，`D/agent.py`及业务state/现有memory、message middleware只补经实测丢失的必要事实 | 多次压缩+恢复后保留用户约束、待办、来源、子任务停止原因；不把全文塞回prompt抵消摘要 |
| 6 / T02,T07 文件/恢复 | `D/workspace/backend.py`、`R/workspace/`现有执行/产物路径、Chat恢复链路 | 验证读版本冲突与截断日志可回读；真实重启/撤权恢复和不可变成果；需要契约变化才联动API/Web |
| 7 / T06 外部任务 | `D/external_task_storage.py`、`D/tools/media.py`和既有运行生命周期 | 同幂等键重复请求最多一个外部意图；ACK丢失/取消/重启后对账，无法对账保持unknown；先获批供应商与成本范围 |
| 8 / T08 优化 | `D/middleware/skills.py`、`D/tools/mcp.py`、模型配置 | 根据tokens/耗时测量决定延迟工具发现、缓存或provider策略，不能以复制中间件数量算完成 |

前三项互有关联：模型因安全/预算终止后，Todo/loop不能又把它强行送回无限执行。新增机制都要测主/子Agent真实组合，验证顺序与状态隔离；各middleware单测全绿不足以验收。

## 任务拆分

- [x] 从源码追踪同名能力、官方替代、组合顺序与默认开关。
- [x] 用真实Dear组合根执行7个离线故障特征探针，保留复现脚本。
- [x] 运行参考项目相关5文件测试，限定证据适用范围。
- [x] 更新12任务优先级、13阶段证据以及本篇效果验收设计。
- [ ] T03/T07按批准的行为语义实施并反转缺口断言；状态统一维护在12。
- [ ] T01/T02/T04/T10执行同条件真实模型与产品旅程对照，之后才判断等价/更优。

## 验证要求与记录

### Phase：2026-09-28 本地故障特征实验

命令（仓库根）：

```bash
"apps/runtime-service/.venv/bin/python" "docs/projects/20260913-dearflow-agent/evidence/effect_probe.py"
```

脚本：[effect_probe.py](evidence/effect_probe.py)。使用既有test_agent的build fixture，真实`get_agent`、Graph、文件工具、内存checkpoint；模型响应受控，工作区为TemporaryDirectory，MCP空配置、治理关闭，无外部模型/供应商/数据库调用。断言**当前缺口存在**，exit0表示复现成功，不是修复验收通过。

| 证据 | 注入输入 | 实际观察 | 可得结论与边界 |
|---|---|---|---|
| E01 | finish_reason=length且write_file参数可解析 | 进入审批；模拟approve后临时文件真实写入，最终done | 当前没有对应的length工具终止保护；未绕过审批，不推断真实provider频率 |
| E02 | finish_reason=content_filter且同样write_file | 进入审批；approve后真实写入 | 当前没有对应的安全终止保护；不是实际违规内容测试 |
| E03 | ls成功后模型空字符串 | 最终空回答 | 缺工具后终态空响应兜底 |
| E04 | read_file不存在文件后声称读取验证成功 | ToolMessage为error，最终成功声称原样接受 | 缺该场景完成核验；未证明参考对此主回答一定拦截 |
| E05 | 连续6次相同ls工具和参数 | 6次工具结果、7条AI消息 | 没有在此次数内发生重复调用短路；不代表所有任务必循环 |
| E06 | env模型run限1，模型返回两次ls再结束 | 3条AI消息、2次工具 | max(mode,env)不把env当硬上限；须评审语义，不擅改成本策略 |
| E07 | Pro写入in_progress Todo后声称全部完成 | Todo仍in_progress，最终All work is complete. | 当前Todo不是完成门禁 |

执行退出码0；7个场景均命中上述断言。出现Skill名称`vercel-deploy`与目录`vercel-deploy-claimable`不匹配告警，列T05兼容收尾。脚本未覆盖真实模型质量、生产并发、持久重启和完整前端链路。

### Phase：2026-09-28 参考机制测试

在参考项目backend目录执行：

```bash
.venv/bin/python -m pytest \
  "tests/test_model_length_finish_reason_middleware.py" \
  "tests/test_safety_finish_reason_graph_integration.py" \
  "tests/test_terminal_response_middleware.py" \
  "tests/test_todo_middleware.py" \
  "tests/test_receipt_verification.py" -q -p no:cacheprovider
```

实际 **104 passed in 7.19s，exit0**。包括受控模型的safety小graph集成；conftest预mock子执行器以打断依赖，不能算真实子Agent端到端。与本地28项抽测不是同一测试集，不能比较通过数量得出质量结论。

### 后续效果验收：同条件比较，而非仅跑单元测试

1. **固定比较条件**：同模型/版本/推理参数、同材料、同允许工具/权限、同任务预算、同供应商返回fixture。先比较共同能力；只读与可执行角色分组，平台特有治理单列，不能放开参考权限后再比较成功率。
2. **固定场景和答案约束**：研究需时间/域名限定与来源对应；数据分析需可复算数字；代码/文件需执行证据与产物解析；规划需每项状态；长任务需追加约束和两次以上压缩。每类预先冻结正常、边界、故障样本，保留原始输入与工具事实，防止看答案改判定。
3. **先确定性故障配对**：length/safety/empty、429/403/timeout、无结果、错误JSON、重复调用、并行编辑、预算耗尽、摘要失败、断流/重启/撤权、ACK丢失。按两边真实装配分别注入，记录是否调用工具、是否重复副作用、最终状态与用户所见，不仅核对文案。
4. **再真实模型多次运行**：同一任务重复、交错两系统运行以减小供应商时段偏差；按任务配对报告成功率、差值及置信区间，人工盲评报告引用与约束，不用单个漂亮demo认定更优。样本量先由小批波动和允许差距评审确定，不编造统计把握。
5. **同时统计质量与代价**：完整/部分/合法拒绝/失败分别计数；不实完成单列；记录主子调用、token、费用、P50/P95耗时、恢复时间。未知usage记unknown，不能填0；合法拒绝不能一律当失败。
6. **批准门槛后冻结**：建议边界用例越权/未经批准副作用为零、受控失败不得伪称成功；效果等价采用预先批准的非劣差距，且不能以安全退步换成功率。只有质量不劣且某项成本/延迟/可控性有可靠改善，才能限定地称该项更优。具体数值与样本量待人审，不是现有已生效SLO。
7. **最后走真实三服务**：Dear页面→API→Runtime→工具→审批/子任务→成果→刷新/恢复，覆盖同一输入和产物hash；再做生产等价Docker/持久库恢复。离线探针和上游测试均不替代这一步。

与13的V09/V11/V12结合保存配置、每阶段事件、工具事实、最终内容、判定理由和失败分类。先确保保护机制组合正确，再评价模型能否完成任务。

## 状态

**分析与故障复现完成；效果等价未证明；迁移仍partial。** 本轮只增加规划与离线诊断证据，未实施业务修复。已确认的缺口进入12的T03/T07，不能继续以“有官方middleware/已有A能力”标记完成。Final仍由13独立记录。
