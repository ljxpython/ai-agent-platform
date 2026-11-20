# 一次启动复杂评测与运行时兼容：验证记录

本记录对应2026-11-20用户批准的Task8–13。任务状态只维护在原tasks.md；本文件保存过程和证据，不代替进度。阶段失败原样保留；本轮后续客观任务、原六轮有效评分和独立联合Final均已完成，见末三节。平台开发验收完成不等于原六轮被测Agent质量通过，也不代表已合并或正式发布。

## 环境与源码

EvalFlow基线39d4656，分支`feat/executable-agent-evaluations-20261120`，sshmy1关联Worktree中运行所属5011后端；前端仅在Mac关联Worktree安装、测试和构建，构建产物同步到该远端Worktree。既有MLflow和DeepEval4.3.4保持，不改上游mlflow目录的跟踪源码。

用户批准扩围后，从Agent基线0d0de9a新建`fix/runtime-tool-call-compat-20261120`，未复制主仓未提交文件。环境wt_644e8a066eac使用独立依赖、双PG库、Redis及Workspace，Web27968/API25075/Runtime26631。评测通过所属临时SSH转发访问该API。原生产进程未重载，未进行Git提交、推送或合并。

## 首轮六轮与同证据重评

首任务`5264e565-2901-4c5f-b0ed-b42fe1be8a57`通过所属真实HTTP导入、发布和启动，自动提交六轮输入、初始五表及第3轮一表，6 Run／6 Trace。执行119.706秒，原件保持，四份交付缺失。逐轮断言10/12、产物0/4，不能把模型的工具调用意图视为实际执行。

原裁判因DeepEval4.3.4会话formatter不支持其枚举中的CONTEXT而报错。改用其支持的METADATA传入执行证据后，以原证据通过TaskStore核心入口重评：任务`cb6518d4-9a9e-4fee-8fb0-932ff147a746`整体failed，真实裁判调用2次、ConversationalGEval为0.0，定位第5/6轮及四个文件。无裁判错误，原6 Run和6 Trace保持，未重新执行Agent。该次不是公开HTTP重评入口全链路。

远端私有证据在`.local-stack/real-six-turn-*.json`、对应results目录及原任务目录。测试材料和标准保持；隐藏答案只交给断言与裁判，不进入被测或模拟用户输入。

## 运行时工具名丢失

生产模型真实SSE首片携带工具名，后续参数片携带`name=""`。锁定langchain-core1.6.0、langchain-openai1.6.0、langgraph1.2.11和GraphHarbor post48后回放：普通流正常，Graph v3累积用空名覆盖首片工具名，既有消息修复继而移除匿名调用。原六轮因此没有实际工具Span。

新增`test_openai_tool_streams.py`用HTTP替身提供两个交错工具流，并通过真实Graph v3和ToolNode执行。未改产品时：省略名称通过、空名称失败，1 passed／1 failed。最小修复位于`ChatOpenAIWithReasoning._convert_chunk_to_generation_chunk`，把空名称规范为None；不猜名称、不升级依赖、不改第三方包或权限。

修复后相关56项通过（7 warnings，28.10秒），覆盖并行工具实际执行、ID和参数、普通同步流、思考内容以及既有模型／中间件／计划安全。追加空/缺失/有效名称和非法JSON后，专项7项通过（2 warnings，19.48秒），异常参数仍留作invalid_tool_calls，没有自动修成有效调用。两组范围重叠，不能累加。

私有日志：`.local-stack/tool-stream-red-v2.log`、`tool-stream-green.log`、`tool-stream-boundaries.log`。首版测试harness用了未安装的asyncio插件、错误output调用；一次扩大命令引用不存在测试路径，均原样保留，不计有效红灯或通过证据。

## 扩大回归与前端

统一审批预算后的末次EvalFlow后端扩大范围744 passed／3 failed／25 warnings，25.55秒，日志`.local-stack/final-step-budget-expanded-tests.log`。三失败在未修改HEAD上同样复现：Token过期、Cookie SameSite和退出后旧认证缓存。不顺手调整安全策略，不计通过；前次740项及HEAD对照日志保留。最新哈希职责只修改样例和断言，已另跑60项关联测试，不机械重复整个扩大范围、不累加重叠数量。

Mac前端4套40项通过，类型检查exit0；增量eslint新增行错误0，ExecutionSession原有cleanup ref问题保留。默认`yarn build`因既有全局lint及首次新增curly错误失败，curly已修；`DISABLE_ESLINT_PLUGIN=true yarn build`编译成功。后者仅证明编译，不替代默认lint通过。构建日志和类型／eslint报告位于所属`.local-stack/`。

## 真实交互准备、失败与正向续跑

新隔离连接首次导入时评测实验未先创建，产生未关联实验的草稿。核对导入回执和原生数据集后，将该合成草稿关联到实验25，复用原请求继续，不重复建数据集。该准备错误不作为平台成功证据。

首个结构化交互任务`da7a0fab-5cb2-4577-8b8b-bb2205b04623`因maomaoai供应商403、provider_access_denied失败，未到达工具验证。失败任务、Trace与原证据保留；随后选择隔离环境已有xiaok模型另建任务验证，不修改模型凭据、供应商配额或生产配置。

使用已有xiaok模型后的任务`79e1f510-ce0c-4d82-ba80-1d2d59a0de54`通过。公开HTTP完成导入、冻结发布、启动和查询；Session为`1cbca87b-9832-42c7-9d7b-fea78232e9ff`，3 Run／3 Trace，93.832秒。实际工具为request_information、enter_plan_mode、save_plan和submit_plan。平台提交预设scope答案，并绑定实际计划ID、revision1及content_hash批准，最终回答包含范围和“验收完成”，completion、turn_expectations、answer_contains均1.0。证据在隔离连接的`interaction-xiaok-ids.json`及`interaction-xiaok-result.json`。

## 修复后六轮：审批边界与样例漏配

原样例首次修复后运行`e04834d0-80c0-4179-aa5b-51e296622713`在第1轮调用execute，触发未配置审批。任务停止，1轮／5上传／1 Run／1 Trace，36.810秒；缺后轮证据明确error，四文件不存在，未自动批准命令。未扩大原有文件工具白名单；调整的是样例的环境说明，明确使用文件读取工具，不调用终端命令。

该文件工具版本任务`93a2f190-23c6-4835-8f20-fdadac76aae0`真实完成前四轮分析和第3轮补传，并进入第5轮write_file审批。5轮／6上传／5 Run／5 Trace，426.238秒，原件保持。检查发现样例构建器虽然在文字中授权交付，却没有设置预设审批，因而四文件都没有写入。平台如实判interrupted、completion失败、逐轮缺证据error和产物0/4；这次不是审批次数上限导致。

为样例增加“前四轮不批准，第五／六轮批准且仅限四条交付路径”的测试，原构建器1 failed／7 passed。补`approval=approve`及精确`approval_allow`后，原契约又拒绝workspace_write与审批混用；该失败保留，按既有协议改为review模式，而非放宽校验。参考CSV、黄金数值和原失败均保持。最新所属任务使用新冻结版本重新执行，不能修改旧任务的用例快照来续成通过。日志为`sample-approval-red.log`、`sample-approval-green.log`及`sample-approval-green-v2.log`。

修正审批后的首任务`cbc63647-a435-4924-a7f6-64dabc5f8cd9`在第2轮遇供应商HTTP/2 GOAWAY，Runtime上报model_call_failed。2 Run／2 Trace、263.835秒，EvalFlow保留执行失败、后轮及产物缺失，未将其归因于工具名修复。Worker所属日志包含原始上游连接关闭错误，未返回用量且供应商称未扣费；这不是平台核实的费用结算结论。使用相同题库、版本和hash`2b3dfcc21d19730cdb359fb54b9e2d18bdfbc26e482b57ab7394b42b41bd9406`显式重试一次，任务`8d94022b-96e6-40a4-8d21-8891fc84f054`，不隐式重试旧任务、不增加配额或改策略。

已通过原取消协议停止e04834d0与93a2f190所属测试会话；两个回执均为no_active_run、execution_stopped=true、resource_cleanup=not_required。清理回执另存在隔离连接`acceptance-stop-receipts.json`，没有改写原评分或证据、没有删除数据库。

同版本有界重试8d94022b已结束：完成前四轮，进入第5轮后实际写入四份文件，artifact_correct为1.0（4/4），protected_unchanged为1.0。随后Agent调用未授权的present_artifacts展示工具，执行器按既有白名单报approval_tool_not_authorized并停止，第6轮没有执行；整体error、逐轮与会话指标明确缺证据。所属取消回执确认execution_stopped=true，没有把“文件正确”冒充完整六轮通过。

本次只调整样例环境说明：第五／六轮交付及读回后用普通文字列出路径，不调用present_artifacts，评测器直接通过工作区接口读取。不扩展原write_file／edit_file审批白名单，不修改六份CSV、数值参考或评分阈值。新增约束测试先1 failed／7 passed，修正后关联56 passed、4 warnings、3.20秒；日志sample-presentation-red.log、sample-presentation-green.log。新冻结用例经公开HTTP导入、发布并启动任务45be951b-85a1-4b12-a546-17a79e7c4c92，题库d-5d14549651994e57847d4215ea305982版本1，hash为f71528bef05f298bfcf3c4df2ad0930ad472db0ed42bbd2ce6cfed1b111986cb；这是环境说明变化后的新样本，不计为原版本自动重试或隐去旧失败。

### 三次审批上限与统一执行预算

45be951b最终停于第5轮：Agent逐个写入四文件，每轮固定3次恢复审批只完成前三份，报告未写入。8 Run／8 Trace，518.721秒，artifact_correct为0.0（3/4），原件保护为1.0，缺第6轮明确报证据不足，整体error。此前93a2f190是样例漏配，不能将两次不同原因混为同一个问题。所属会话已按取消协议确认no_active_run／execution_stopped=true；首次脚本把异步取消回执当作即时完成而断言失败，读取原stop_id后确认完成，没有重复发起取消或改写原评分。

先增加四个独立写入、额外请求停止与长交互编号测试，旧产品3项失败；按文件数量推导预算后59项通过。但再次检查发现，文件数量也会卡住合法修订，新增第五次已授权修订回归在该中间版失败。因此最终只复用现有连接配置max_steps作为工具审批预算，代码默认20、本次任务快照为60；不增加必填字段，不从文件数推导上限。工具与路径仍逐次校验，预算耗尽明确tool_approval_limit_exceeded。前9个恢复步骤保留旧标识，之后使用轮次与恢复序号组成独立标识，避免撞上下一轮输入。

统一预算后，固定交互／六轮样例／证据／结果接口60 passed、4 warnings、2.81秒；测试包含四文件逐个写入、合法第五次修订、配置4步时第五次停止，以及6个结构化回应加4次文件审批后进入下一轮的编号唯一性。日志approval-capacity-red.log、approval-capacity-green.log、approval-step-budget-red.log、approval-step-budget-green.log。中间版真实任务e17f610f-c3bf-4ddf-80c7-f9849fa4fcfd已主动取消，原回执phase=stopped、execution_stopped=true，未在其执行中替换产品源码。

同时，本环境多次长测的事件回放流触及Redis默认512MiB，出现event transport unavailable；只读确认实例为wt_644e8a066eac所属24878、noeviction，原OOM计数42202。核对32GiB宿主机和实例PID后，先仅将私有redis.conf及所属实例临时调至1GiB；新任务运行期间缓存接近上限，再将同一PID64197实例调至2GiB。两次均不删除键、不改变1小时过期规则，不修改源码默认值或生产。容量回执为.local-stack/redis-acceptance-capacity.json和redis-acceptance-capacity-2g.json，最终另核对新增OOM。第二次调整脚本首次引用错误的PID文件路径，在写入前退出；核对pids/redis.pid与Redis自身PID后完成，没有盲目重试写入。

统一预算的真实验收使用同一冻结题库d-2a543dde728349889bc5f9772339376f版本1、hash为989193e5b55d0966554279af4f899cf54d362b2adc7ca75ced55fc59d2500343，显式启动新任务820fafee-0007-4230-8ad5-6a4f2e9ff04c。移除样例第一轮强迫模型合并调用／最多3次的环境提示，附件、业务规则、四文件参考及评分阈值保持。中间失败和取消任务均保留，不记为成功样本。

### 文件工具与哈希核对职责

820fafee已结束：6次输入、5次输出，8 Run／8 Trace，394.218秒。四文件4/4正确、六原件保持，但第6轮为计算SHA256申请execute而被白名单正确拦截，整体error、后轮及会话指标缺证据；所属停止回执execution_stopped=true。不能把提交第6轮算成完成六轮。

问题是自动化样例保留了手工版本“由Agent计算原件SHA256”，同时又只授权文件工具。文件工具无法计算密码学哈希，不能靠反复提示模型解决能力矛盾。本次将哈希职责交还独立评测器：上传时记录实际字节SHA，结束时读回比较；Agent仍实际读取原件和交付文件核对业务内容，不开放终端、不降低原件保护或业务标准。

新增样例约束断言在修正前1 failed／7 passed；修正后关联60 passed、4 warnings、2.97秒，生成器及测试Ruff通过。结构化比较确认仅turns[0]、turns[2]、turns[5]的content变化，fixture、expectations、turn_expectations、metrics及审批白名单完全一致。JSONL文件SHA256为e350305c66693c7c74c283a6d305987a8a5bd811fa42f1408116202977fe1d96；日志sample-hash-responsibility-red.log、sample-hash-responsibility-green.log及sample-hash-responsibility-freeze.json保留。

新用例经公开HTTP导入题库d-82be9c78662d446e83d72992bf574c9e、发布版本1，内容hash为48efcbc523a6921c1676cc71db8258e0064073821876ca4ab3545560b6886390，启动任务2ff899ef-d91a-400a-b44b-380228c2c619。已完整执行6输入／6输出、19 Run、75次工具调用及13次审批恢复，1485.051秒。三份CSV逐行符合26／3／4行冻结参考，报告齐全，completion、turn_expectations、artifact_correct、protected_unchanged均1.0；但原Trace批量查询失败，会话指标因缺工具证据报error，整体error。旧冻结版本和失败结果均不改写。

### 复杂会话的Trace批量明细查询

19条Trace元数据均存在，单条完整明细可读取；SDK批量batchGet在当前跟踪服务失败。原任务与修复前同证据重评521ea8c8均因trace_query_failed／trace_collection_timeout报error，没有将缺证据伪装成低业务分。原生任务没有直接HTTP重评接口，521ea8c8使用现有TaskStore核心入口创建，保留原Session／Run，没有重新执行Agent。发布阶段只观察到耗时，原任务没有publication-error.json；不能将其写成已证实的发布失败。

按原方案补取证回归，修复前2 failed；改为先查询元数据，按本次Run归属逐条读取全部明细，元数据不能代替Span。首批135项通过；扩大回归744 passed／4 failed，其中3项为既有认证失败，另一项是旧测试替身没有模拟新增的单条读取。补齐该替身后，含Trace完整性的6套关联测试140 passed、4 warnings、3.63秒；再次扩大为745 passed／3 failed／25 warnings、26.12秒，仅余上述3项HEAD既有认证失败。日志trace-details-read-red.log、trace-details-read-green.log、final-trace-details-expanded-tests.log、trace-details-read-green-v2.log及final-trace-details-expanded-tests-v2.log保留，不累加范围重叠的测试数量。

取证修复后的真实同证据重评任务为af13283b-da94-41dd-af44-3b475035d0b0。正常HTTP回读已取得19份完整Trace，complete=true、query_complete=true、missing为空；与原2ff899ef逐项比较，Session及19个Run完全一致，没有重新执行Agent。四项事实指标仍为1.0，原任务取证失败保持，不改写历史结果。

该次重评整体仍为error：ConversationalGEval先生成评审步骤，再读取约6.78万输入Token的完整材料；两次正式评分请求均使用8192 Token输出额度、60秒请求超时，分别约42.69秒和41.51秒返回finish_reason=length，输出Token均8192，因截断抛ValueError，score为空。这是裁判输出截断，不是业务低分或Trace仍缺失；尚不能据此认定是哪类输出耗尽额度。两次步骤生成正常结束，完整四次调用及用量均保留。结果在私有连接six-turn-individual-traces-result.json，原Session／Run对比已回读；后续应在保持标准和原执行证据的条件下取得有效会话评分，再做联合Final。

独立AI业务核对发现第2／3轮把O007误算为按时发货，V1／V2原答33.33%／22.22%，冻结参考为38.89%／27.78%。Agent在第6轮自行订正报告并保留原发布值；V3为25.00%，最终CSV正确。后续评分须同时保留早期错误与最终修复事实，不修改标准迎合结果。任务配置快照max_steps实际为60，代码默认值20；此前文档混淆两者，已据实更正，配置未改。

## 真实浏览器：编辑、发布、一次启动与证据展开

使用browser-skill所属后台窗口，打开本轮9138开发入口、runtime-fixed连接。合成工作项`801f6532-51d4-46f1-874b-86df22b854ea`实际编辑信息补充字段、要求修改的计划反馈并保存为草稿v1，回读完整JSON确认保留；历史评分模式下自动回应字段组禁用。随后按已验证的澄清加批准用例保存v2，正常授权、发布题库v1；发布完成时没有自动运行，再点击一次运行。

任务`ee7a8040-5413-486b-b4ac-b065e3192d7a`通过：Session`aa37d26a-7608-44f5-97b4-1f49f9acdceb`，3 Run／3 Trace，38.012秒，三项规则指标1.0，无执行错误。页面实际展开“按轮附件与自动回应记录”及计划绑定，展示两个回应、触发／恢复Run、revision1／hash、耗时和评分；业务轮次为1，执行Run为3，未混算。Trace时间线可见实际request_information、submit_plan及最终回答。

截图`.local-stack/browser-interaction-page.png`已实际查看，文字与计划绑定可读；VOM和JSON回读保存在`browser-saved-proposal-v1.json`、`browser-historical.json`、`browser-plan-binding.json`，远端有`browser-acceptance-result.json`。起初授权回调沿用了生产receiver而报错，修正的仅是所属私有连接回调并重启所属platform-api，失败保留。两次CLI参数／隐藏详情定位错误均先sync后纠正，没有盲目重复发布或运行。

## 最终静态检查与并行工作区边界

该阶段远端11份Python语法、diff空白及上游零改动核对通过。Ruff首次发现新增测试一处导入排序，局部修正后31条既有诊断、新增或修改行0条。当时Mac与远端28份源码／测试／文档SHA256一致，不含私有配置或构建缓存；后续最终19份AST和37份同步清单见下文。该阶段主仓由其他工作推进至`7d3cb7f`，生产PID由基线3053902变为3105454、NRestarts0／active，不能声称全程身份未变。本轮未调用生产重载或覆盖主仓产品代码，不把并行状态回退到旧快照。Worktree基线仍为39d4656，后续合并须正常处理主分支新变化。

本节是当时的阶段证据；下文另记新增客观任务、有效评分及独立Final，不覆盖这些失败和阶段统计。

## 仅规则指标与一次性客观基线

用户批准默认客观验收后，核对制作提示、Proposal／Case、编辑发布、执行及结果消费者。实际限制来自contracts.py无逐轮断言时强制ConversationalGEval的兜底；只移除该兜底，保留已声明断言的覆盖、指标配对、业务标准和动态模拟约束。evaluation_assistant.py、work_items.py及agent/prompts.py同步说明完整输入优先、交互与模型评分按需，未增加字段或依赖，复用已有无裁判的规则路径。

`test_rule_only_cases.py`在改产品前6 failed；初次green命令引用不存在的test_simulation.py而0项执行，保留不计通过。修正命令85 passed；加入客观基线保真测试后88 passed、3.86秒。单／多轮最终文件断言、工作项编辑授权发布、正负数值、零裁判及既有模拟兼容均覆盖。日志为rule-only-red.log、rule-only-green-v2.log、rule-only-and-baseline-tests.log。

新增`reference/build_objective_case.py`复用六份实际原件及最终CSV冻结参考，生成独立`objective-case.jsonl`：六表全为初态，只给一次完整任务及最终排除测试门店口径，要求生成三CSV和summary.json；没有simulation、turn_expectations或会话指标。隐藏黄金只进断言，Agent题面不泄露答案。审批只允许write_file／edit_file及四条产物路径，不增加终端权限，六轮原用例不变。

通过正常HTTP导入、发布和一次启动得到任务`842be548-0906-4fc6-9e70-6f0d70b4fe62`，题库`d-a2ce02467e8245c383f410534a4450e8` v1、hash`80b1597a14862bd88463ac64c00c2e528c37fdb42d8acb0c5d8a16d890c39faa`，Session`da34d4bc-b885-49cc-97a9-0c4bacfdb46c`。真实1输入／1输出、4 Run／4 Trace、16次工具调用及3审批恢复，219.083秒，最终passed。completion、artifact_correct和protected_unchanged均1.0；四产物4/4正确、六原件保持。CSV分别26／3／4行；汇总16单、5066.50元、四分类8／2／4／2、超时金额871.49元、主比例25.00%、到期分母13和辅助比例30.77%。judge_calls／requests均0、simulation为空、interaction_responses为空；被测Agent仍使用真实模型。

私有驱动为live-objective-acceptance.py，结果为objective-final-rules-ids.json／objective-final-rules-result.json；真实证据在results/842be54809064fc69e706f0d70b4fe62/fulfillment-objective/evidence.json。执行期间70份产品源码冻结核对，未在运行中换源码。两类用例分别发布、统计，不比较不同输入和指标下的原始分数／成本。

## 原六轮取得有效评分，正常判为未达标

继续沿用2ff899ef的原题库、v1／hash、Session、19 Run及六轮输入输出。scorers/agent_platform.py新增按required证据类别组织语义上下文：完全相同的重复工具参数引用同ID的tools项，逐轮文件与最终同路径内容完全相同才引用artifacts项；不同历史内容、不同实参、None和Trace／Span／Run来源保留。原证据不改、不抽样、不用模型摘要代替程序断言。

含会话指标的评分使用现有XiaokJudge(disable_thinking=True)适配，只有支持的deepseek-v4加该请求参数，不修改被测Agent、出题或模拟模式。指标版本2→3、PROMPT_VERSION3→4区分评分身份；原阈值、8192输出、60秒和预算保持。新增精确保真及结构化低分测试先2 failed／2 passed；修复后关联114 passed、20 warnings、3.62秒，新测试Ruff检查与格式通过。

重评任务`c80efddf-9307-49eb-b2b2-afde895ae38c`取得19份完整Trace，错误空，Session`77761538-99f1-4da8-b0bf-ceb9d2e8cd17`、19 Run和六轮输入输出与原任务逐项一致，没有重跑Agent。真实裁判2次均finish_reason=stop：生成步骤891输入／365输出Token，正式评分52282输入／139输出Token。ConversationalGEval=0.7，低于原threshold=0.8，status=fail；四规则仍1.0，整体failed，无error。

裁判指出第2／3轮O007被误算为on_time，V1／V2原答33.33%／22.22%，参考38.89%／27.78%，随后沿用错误说明，第6轮才订正。独立复核确认：第4轮V3最终25.00%本身正确，但其对V2的O007／O008历史分类说明仍错；第6轮说明V3不受O007影响并修正V1／V2。这里保留早期错误与最终修复，不将V3正确数值误记为错误，也不为取得passed降低标准或追加抽样。

结果为six-turn-scoped-structured-judge-ids.json／six-turn-scoped-structured-judge-result.json，驱动live-scoped-rescore-acceptance.py，产品冻结scoped-judge-source-freeze.json。原2ff899ef、521ea8c8及af13283b的error、原发布快照与输入输出保持，未覆盖历史。

最新扩大回归753 passed／3 failed／27 warnings、26.32秒，日志objective-final-expanded-tests-v2.log；三失败在未改HEAD亦复现，涉及过期Token、SameSite及旧浏览器认证缓存，未计通过。首轮752／4中的旧制作提示断言已更新并复验，其失败日志保留。19份Python AST通过，54条Ruff既有诊断中修改行0条，git diff --check通过，mlflow上游跟踪／未跟踪变更均0；末次采用Git原生检查，没有调用不存在的guard脚本。私有静态回执objective-final-static.json。之后无产品源码变化，不重复前端40项和类型检查；默认全局lint构建失败仍保留。

## 独立联合Final及页面、服务复核

阶段任务结束后，另执行私有final-objective-joint-readback.py，报告final-objective-joint-readback.json共57项全部true。通过正常HTTP读回四个任务，向Agent直接读取实际原件／产物及绑定Run，核对客观基线和原六轮的CSV精确值、JSON／报告、上传SHA和时点、真实读写工具、Session／Trace完整归属。客观任务无模拟裁判；原六轮低分与原0.8门槛不变、两裁判正常stop；同证据重评Session／Run／输入／输出一致、旧error和冻结标准保持；结构化交互79e1f510与页面任务ee7a8040的决策和恢复绑定一致；当前70份产品源码与冻结清单一致。该核对不声称独立盲评或裁判重复稳定性。

浏览器再次登录9138工作台并展开原ee7a8040结果：通过标识、1业务轮次／3次运行、三规则1.0及内嵌Trace可见。首次直接打开5011原生实验25／Run结果404；只读API核对确认新结果写入配置指定的5000跟踪服务、5011自身MLflow库没有实验25。随后在9128实际跟踪服务只读打开六轮重评原生页，实验25、Run71a4e46b2977475591ce23a91e02534c、会话0.7、四规则1.0及未通过提示均可见。不是结果丢失，也不能称5011相对链接通过；未改共享库或生产配置。原生导入页面的浏览器全流程仍未覆盖。回执为final-browser-result-expanded.json、final-native-readonly-result.json及final-native-readonly-case.json；两scope均已关闭。CLI的save-full参数误用于sync和观察过期拒绝均先同步，未重复发布／运行。

末次服务健康：API25075、Runtime26631、所属5011及生产5000均200，远端37211转发正常。Redis仍属环境wt_644e8a066eac、PID64197，maxmemory2GiB／noeviction、OOM42202，与容量调整后记录相同，新增0；最新使用约147MB，未删键。首次在系统Python读取因没有redis依赖退出，改用所属Runtime虚拟环境后只读核对，回执final-objective-redis-readback.json。

远端主仓已由并行工作推进至0a5b89b，正式服务PID3167539／NRestarts0／active；不能声称全程身份未变。本轮仅重启所属Worktree后端，最新PID3242357，未重载生产、迁移或覆盖主仓产品代码。主仓已有功能、AGENTS.md未提交内容与其他Worktree保持。服务和两条所属转发保留供验收，尚未进行本轮commit／push／merge、生产发布或数据库／Worktree清理。

收尾先回写Agent主仓唯一任务源及摘要，精确同步15份本轮文档／材料到Runtime修复Worktree；EvalFlow只同步8份共用手册／材料／实施记录，保留本仓README、任务映射、验证和CONTEXT的结构。两端37份交付源码／测试／文档清单逐份SHA256一致，主仓原有AGENTS.md未提交内容未复制。Agent主仓与修复Worktree的check_docs.py及各工作区git diff --check通过，Task8–13回读均done、当前未勾选项0；文档检查不计产品测试。

本轮批准的开发与必要验证已完成；被测Agent原六轮未达到会话门槛。正式合并发布后的整合验收、独立真人／盲评、大规模压测、全新动态用户模拟不在本轮已通过结论内。
